import os
import re
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse as FastFileResponse
from datetime import datetime

from .auth import get_current_user
from ..schemas.responses import FileResponse
from bot.database.engine import get_session
from bot.database import crud
from bot.database.models import File as DBFile
from bot.config import get_settings
from bot.processors import get_processor
from bot.processors.converter import FileConverter
from bot.processors.word_processor import WordProcessor
from bot.utils.helpers import sanitize_filename, generate_unique_filename

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
converter = FileConverter()
word_processor = WordProcessor()


async def send_file_to_telegram(telegram_id: int, file_path: str, caption: str = ""):
    """Tayyor bo'lgan faylni foydalanuvchining Telegram chatiga to'g'ridan-to'g'ri yuborish."""
    if not settings.BOT_TOKEN or not telegram_id:
        return
    import httpx
    try:
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendDocument"
        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(file_path, "rb") as f:
                files = {"document": (os.path.basename(file_path), f)}
                data = {"chat_id": telegram_id, "caption": caption}
                await client.post(url, data=data, files=files)
    except Exception as e:
        logger.warning(f"Telegramga fayl yuborishda xatolik: {e}")


@router.get("", response_model=List[FileResponse])
async def list_files(user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        return [
            FileResponse(
                id=f.id,
                file_name=f.file_name,
                file_type=f.file_type,
                file_size=f.file_size,
                uploaded_at=f.uploaded_at
            ) for f in files
        ]


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    try:
        user_id_str = str(user["telegram_id"])
        user_dir = os.path.join(settings.upload_dir, user_id_str)
        os.makedirs(user_dir, exist_ok=True)
        
        safe_name = generate_unique_filename(file.filename)
        dest_path = os.path.join(user_dir, safe_name)
        
        content = await file.read()
        file_size = len(content)
        with open(dest_path, "wb") as f:
            f.write(content)
            
        ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
        
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            record = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=file.filename,
                file_type=ext,
                telegram_file_id="",
                local_path=dest_path,
                file_size=file_size
            )
            await crud.log_usage(session, db_user.id, "upload_web", f"Uploaded {file.filename}")
            
            return {
                "message": "Fayl muvaffaqiyatli yuklandi",
                "file_id": record.id,
                "file_name": record.file_name,
                "file_size": file_size
            }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_id}/convert")
async def convert_file(
    file_id: int,
    format: str = "pdf",
    user: dict = Depends(get_current_user)
):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
            
        try:
            target_ext = format.lower()
            if target_ext == "pdf":
                out_path = await converter.convert_to_pdf(target.local_path, settings.processed_dir)
            elif target_ext in ("docx", "word"):
                out_path = os.path.join(settings.processed_dir, f"{os.path.splitext(target.file_name)[0]}.docx")
                await converter.pdf_to_word(target.local_path, out_path)
            elif target_ext == "csv":
                out_path = os.path.join(settings.processed_dir, f"{os.path.splitext(target.file_name)[0]}.csv")
                await converter.excel_to_csv(target.local_path, out_path)
            else:
                raise HTTPException(status_code=400, detail=f"{format} formatiga konvertatsiya mavjud emas")
                
            new_ext = os.path.splitext(out_path)[1].lstrip(".").lower()
            new_record = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=os.path.basename(out_path),
                file_type=new_ext,
                telegram_file_id="",
                local_path=out_path,
                file_size=os.path.getsize(out_path)
            )

            # Auto-send to Telegram chat
            await send_file_to_telegram(
                user["telegram_id"],
                out_path,
                f"✅ {os.path.basename(out_path)} faylingiz tayyor bo'ldi!"
            )

            return {
                "message": "Konvertatsiya muvaffaqiyatli yakunlandi",
                "new_file_id": new_record.id,
                "new_file_name": new_record.file_name
            }
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}/download")
async def download_file(file_id: int, user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
            
        return FastFileResponse(
            path=target.local_path,
            filename=target.file_name,
            media_type="application/octet-stream"
        )


@router.delete("/{file_id}")
async def delete_file(file_id: int, user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        
        if not target:
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
            
        if os.path.exists(target.local_path):
            try:
                os.remove(target.local_path)
            except Exception as e:
                logger.warning(f"Could not delete physical file: {e}")
                
        await crud.delete_file_record(session, file_id)
        return {"message": "Fayl muvaffaqiyatli o'chirildi"}


@router.delete("/clear-all")
async def clear_all_files(user: dict = Depends(get_current_user)):
    """Foydalanuvchining barcha fayllarini (ham diskdan, ham DB dan) tozalaydi."""
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        for f in files:
            if f.local_path and os.path.exists(f.local_path):
                try:
                    os.remove(f.local_path)
                except Exception as e:
                    logger.warning(f"Could not delete physical file: {e}")
            await crud.delete_file_record(session, f.id)
        return {"status": "ok", "message": "Barcha fayllar tozalandi"}


@router.get("/{file_id}/content")
async def get_file_content(file_id: int, user: dict = Depends(get_current_user)):
    """Fayl matnini tahrirlash uchun olib beradi (DOCX yoki PDF)."""
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")

        ext = os.path.splitext(target.file_name)[1].lower()
        if ext in ('.docx', '.doc'):
            from docx import Document
            doc = Document(target.local_path)
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            content = "\n\n".join(paras)
        elif ext == '.pdf':
            import fitz
            doc = fitz.open(target.local_path)
            paras = [page.get_text() for page in doc]
            content = "\n\n".join(paras)
            doc.close()
        else:
            with open(target.local_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

        return {"file_id": target.id, "file_name": target.file_name, "content": content}


@router.post("/{file_id}/save-content")
async def save_file_content(
    file_id: int,
    data: dict,
    user: dict = Depends(get_current_user)
):
    """Tahrirlangan matnni yangi fayl sifatida saqlaydi (DOCX yoki PDF)."""
    new_text = data.get("content", "")
    replacements = data.get("replacements")  # dict of {"old_word": "new_word"}

    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")

        ext = os.path.splitext(target.file_name)[1].lower()
        base = os.path.splitext(target.file_name)[0]
        out_name = f"{base}_tahrirlangan{ext}"
        out_path = os.path.join(settings.processed_dir, out_name)

        if ext in ('.docx', '.doc'):
            if replacements:
                await word_processor.find_and_replace(target.local_path, replacements, out_path)
            else:
                from docx import Document
                doc = Document(target.local_path)
                paras = [p.strip() for p in new_text.split("\n\n") if p.strip()]
                # Update existing paragraphs in place to preserve formatting
                for idx in range(min(len(doc.paragraphs), len(paras))):
                    doc.paragraphs[idx].text = paras[idx]
                # If there are extra paragraphs
                if len(paras) > len(doc.paragraphs):
                    for extra_p in paras[len(doc.paragraphs):]:
                        doc.add_paragraph(extra_p)
                doc.save(out_path)

        elif ext == '.pdf':
            import fitz
            if replacements:
                doc = fitz.open(target.local_path)
                for page in doc:
                    for old_w, new_w in replacements.items():
                        rects = page.search_for(old_w)
                        for r in rects:
                            page.add_redact_annot(r, fill=(1, 1, 1))
                            page.apply_redactions()
                            page.insert_text((r.x0, r.y1 - 2), new_w, fontsize=10, fontname="helv")
                doc.save(out_path)
                doc.close()
            else:
                doc = fitz.open()
                page = doc.new_page(width=595, height=842)
                rect = fitz.Rect(50, 50, 545, 792)
                page.insert_textbox(rect, new_text, fontsize=11, fontname="helv")
                doc.save(out_path)
                doc.close()
        else:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(new_text)

        new_record = await crud.save_file_record(
            session=session,
            user_id=db_user.id,
            file_name=out_name,
            file_type=ext.lstrip("."),
            telegram_file_id="",
            local_path=out_path,
            file_size=os.path.getsize(out_path)
        )

        # Auto-send to Telegram chat
        await send_file_to_telegram(
            user["telegram_id"],
            out_path,
            f"📝 {out_name} tahrirlangan faylingiz tayyor bo'ldi!"
        )

        return {"status": "ok", "new_file_id": new_record.id, "new_file_name": out_name}



def embed_images_and_fix_charset(temp_html_path: str) -> str:
    """Fixes charset to UTF-8 and converts all extracted images into inline Base64 data URIs."""
    import base64
    import shutil
    
    with open(temp_html_path, 'r', encoding='utf-8', errors='ignore') as f:
        html = f.read()

    # 1. Force UTF-8 charset
    html = html.replace('charset=windows-1252', 'charset=utf-8').replace('charset="windows-1252"', 'charset="utf-8"')
    if '<head>' in html.lower() and 'charset=' not in html.lower():
        html = re.sub(r'(<head[^>]*>)', r'\1\n<meta charset="utf-8">', html, count=1, flags=re.IGNORECASE)

    # 2. Embed images as Base64 data URIs
    base_dir = os.path.dirname(temp_html_path)
    base_name = os.path.splitext(os.path.basename(temp_html_path))[0]
    folder1 = os.path.join(base_dir, f"{base_name}_files")
    folder2 = os.path.join(base_dir, f"{base_name}.files")

    def img_replacer(match):
        full_tag = match.group(0)
        src = match.group(1)
        if src.startswith('data:'):
            return full_tag
        candidates = [
            os.path.join(base_dir, src),
            os.path.join(folder1, os.path.basename(src)),
            os.path.join(folder2, os.path.basename(src))
        ]
        for c in candidates:
            if os.path.exists(c):
                ext = os.path.splitext(c)[1].lower().lstrip('.')
                mime = 'image/jpeg' if ext in ('jpg', 'jpeg') else ('image/png' if ext == 'png' else f'image/{ext}')
                try:
                    with open(c, 'rb') as img_f:
                        b64 = base64.b64encode(img_f.read()).decode('utf-8')
                    return f'src="data:{mime};base64,{b64}"'
                except Exception:
                    pass
        return full_tag

    html = re.sub(r"""src=["']([^"']+\.(?:png|jpg|jpeg|gif|bmp|webp))["']""", img_replacer, html, flags=re.IGNORECASE)

    # Clean up image folders
    if os.path.exists(folder1):
        try:
            shutil.rmtree(folder1)
        except Exception:
            pass
    if os.path.exists(folder2):
        try:
            shutil.rmtree(folder2)
        except Exception:
            pass

    return html


def docx_to_filtered_html(docx_path: str, temp_dir: str) -> str:
    """
    Converts a DOCX file into high-fidelity structured HTML preserving exact font sizes,
    text alignments, indentation, full tables, borders, and page breaks.
    """
    import docx
    import html
    
    doc = docx.Document(docx_path)
    parts = []
    page_count = 1

    for el in doc.element.body:
        tag = el.tag.split('}')[-1]
        if tag == 'p':
            p = docx.text.paragraph.Paragraph(el, doc)
            text = p.text
            align = p.alignment
            align_css = 'text-align: left;'
            if align == docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER:
                align_css = 'text-align: center;'
            elif align == docx.enum.text.WD_ALIGN_PARAGRAPH.RIGHT:
                align_css = 'text-align: right;'
            elif align == docx.enum.text.WD_ALIGN_PARAGRAPH.JUSTIFY:
                align_css = 'text-align: justify;'
            
            runs_html = []
            for r in p.runs:
                t = html.escape(r.text)
                t = t.replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;')
                t = t.replace('  ', '&nbsp;&nbsp;')
                t = t.replace('\n', '<br>')
                style = []
                if r.bold: style.append('font-weight: bold;')
                if r.italic: style.append('font-style: italic;')
                if r.underline: style.append('text-decoration: underline;')
                if r.font.size:
                    style.append(f'font-size: {r.font.size.pt:.1f}pt;')
                else:
                    style.append('font-size: 11.5pt;')
                if r.font.name:
                    style.append(f'font-family: "{r.font.name}", Times New Roman, serif;')
                else:
                    style.append('font-family: "Times New Roman", serif;')
                span_style = ' '.join(style)
                runs_html.append(f'<span style="{span_style}">{t}</span>' if span_style else t)
            
            p_content = ''.join(runs_html) if runs_html else '&nbsp;'
            parts.append(f'<p style="margin: 3px 0; line-height: 1.35; {align_css}">{p_content}</p>')
            
        elif tag == 'tbl':
            tbl = docx.table.Table(el, doc)
            col_count = len(tbl.columns) if tbl.columns else 1
            tbl_html = ['<table style="width: 100%; border-collapse: collapse; margin: 12px 0;">']
            for r_idx, row in enumerate(tbl.rows):
                xml = row._tr.xml
                is_break = 'lastrenderedpagebreak' in xml.lower()
                if is_break:
                    page_count += 1
                    tbl_html.append(f'<tr class="page-divider-row"><td colspan="{col_count}" style="padding:0; border:none;"><div class="doc-page-break" data-page="{page_count}"><div class="page-divider-line"></div><span class="page-tag">Sahifa {page_count}</span></div></td></tr>')
                
                tbl_html.append('<tr>')
                # Iterate over true XML tc cells to eliminate python-docx cell duplication on merged/grid columns
                tc_nodes = row._tr.tc_lst
                for tc in tc_nodes:
                    is_header = (r_idx == 0)
                    tag_name = 'th' if is_header else 'td'
                    
                    # Colspan from gridSpan
                    grid_span = tc.xpath('./w:tcPr/w:gridSpan/@w:val')
                    colspan = int(grid_span[0]) if grid_span else 1
                    colspan_attr = f' colspan="{colspan}"' if colspan > 1 else ''
                    
                    # Skip if vertically merged secondary cell
                    v_merge = tc.xpath('./w:tcPr/w:vMerge')
                    if v_merge:
                        v_val = tc.xpath('./w:tcPr/w:vMerge/@w:val')
                        if not v_val or v_val[0] != 'restart':
                            continue
                    
                    # Extract paragraphs and formatting inside cell
                    p_nodes = tc.xpath('./w:p')
                    cell_p_list = []
                    for p_node in p_nodes:
                        t_parts = p_node.xpath('.//w:t/text()')
                        p_txt = ''.join(t_parts).strip()
                        if p_txt:
                            jc = p_node.xpath('./w:pPr/w:jc/@w:val')
                            p_align = jc[0] if jc else ('center' if is_header else 'left')
                            bolds = bool(p_node.xpath('.//w:rPr/w:b')) or is_header
                            bold_css = ' font-weight: bold;' if bolds else ''
                            cell_p_list.append(f'<div style="text-align: {p_align};{bold_css}">{html.escape(p_txt)}</div>')
                    
                    cell_content = ''.join(cell_p_list) if cell_p_list else '&nbsp;'
                    style = 'border: 1px solid #334155; padding: 5px 8px; font-size: 10pt; font-family: "Times New Roman", serif; vertical-align: middle;'
                    if is_header:
                        style += ' font-weight: bold; background-color: #f1f5f9; text-align: center;'
                    tbl_html.append(f'<{tag_name}{colspan_attr} style="{style}">{cell_content}</{tag_name}>')
                tbl_html.append('</tr>')
            tbl_html.append('</table>')
            parts.append(''.join(tbl_html))

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {{
    font-family: 'Times New Roman', serif;
    background: #ffffff;
    color: #0f172a;
    padding: 35px 45px;
    margin: 0;
    overflow: hidden !important;
    scrollbar-width: none !important;
    -ms-overflow-style: none !important;
}}
::-webkit-scrollbar {{
    display: none !important;
    width: 0 !important;
    height: 0 !important;
}}
.doc-page-break {{
    margin: 30px -45px;
    padding: 10px 0;
    background: #f8fafc;
    border-top: 2px dashed #94a3b8;
    border-bottom: 2px dashed #94a3b8;
    text-align: center;
    position: relative;
    user-select: none;
}}
.page-tag {{
    display: inline-block;
    padding: 3px 12px;
    background: #4f46e5;
    color: #ffffff;
    font-size: 11px;
    font-family: system-ui, sans-serif;
    font-weight: 700;
    border-radius: 9999px;
    box-shadow: 0 2px 6px rgba(79, 70, 229, 0.25);
}}
</style>
</head>
<body data-total-pages="{page_count}">
{''.join(parts)}
</body>
</html>"""
    return full_html


def pdf_to_filtered_html(pdf_path: str, temp_dir: str) -> str:
    """
    Converts a PDF file to clean, high-fidelity editable HTML.
    Uses pdf2docx to accurately rebuild text flow, paragraphs, tables, alignments and fonts,
    eliminating absolute positioning bugs and overlapping text.
    """
    import tempfile
    import os
    import fitz
    
    timestamp = int(datetime.now().timestamp())
    temp_docx = os.path.join(temp_dir, f"temp_pdf_render_{timestamp}_{os.getpid()}.docx")
    
    try:
        from pdf2docx import Converter
        cv = Converter(pdf_path)
        cv.convert(temp_docx, start=0, end=None)
        cv.close()

        if os.path.exists(temp_docx) and os.path.getsize(temp_docx) > 0:
            html = docx_to_filtered_html(temp_docx, temp_dir)
            return html
    except Exception as conv_err:
        logger.warning(f"pdf2docx parsing encountered error: {conv_err}. Falling back to structured PyMuPDF text flow...")
    finally:
        if os.path.exists(temp_docx):
            try:
                os.remove(temp_docx)
            except Exception:
                pass

    # Fallback: PyMuPDF clean structured text flow (avoids overlapping absolute coordinates)
    try:
        doc = fitz.open(pdf_path)
        total_p = len(doc)
        pages_html = []
        for idx, page in enumerate(doc):
            p_num = idx + 1
            break_tag = ""
            if idx > 0:
                break_tag = f'<div class="doc-page-break" data-page="{p_num}"><span class="page-tag">Sahifa {p_num}</span></div>'
            
            blocks = page.get_text("blocks")
            page_content = []
            for b in blocks:
                # b = (x0, y0, x1, y1, text, block_no, block_type)
                if len(b) >= 5 and b[4].strip():
                    block_text = html.escape(b[4].strip()).replace('\n', '<br>')
                    page_content.append(f'<p style="margin: 6px 0; line-height: 1.4; font-size: 11.5pt;">{block_text}</p>')
            
            pages_html.append(f"{break_tag}<div class='pdf-page' style='padding: 10px 0;'>{''.join(page_content)}</div>")
        doc.close()

        return f"""<!DOCTYPE html><html><head><meta charset='utf-8'><style>
html, body {{ font-family: 'Times New Roman', Arial, sans-serif; padding: 25px 35px; margin: 0; background: #ffffff; color: #0f172a; overflow: hidden !important; scrollbar-width: none !important; -ms-overflow-style: none !important; }}
::-webkit-scrollbar {{ display: none !important; width: 0 !important; height: 0 !important; }}
.doc-page-break {{ margin: 30px -35px; padding: 10px 0; background: #f8fafc; border-top: 2px dashed #94a3b8; border-bottom: 2px dashed #94a3b8; text-align: center; }}
.page-tag {{ display: inline-block; padding: 3px 12px; background: #4f46e5; color: #ffffff; font-size: 11px; font-weight: 700; border-radius: 9999px; }}
</style></head><body data-total-pages="{total_p}">{''.join(pages_html)}</body></html>"""
    except Exception as e:
        logger.error(f"PyMuPDF structured fallback failed: {e}")
        raise e


def save_html_to_office_documents(html_str: str, base_name: str, target_dir: str, save_format: str = "both") -> dict:
    """
    Saves edited HTML back to native DOCX and PDF using Word COM with python-docx fallback.
    Guarantees clean execution and no hanging.
    """
    import pythoncom
    import win32com.client
    
    # Clean out internal page divider rows & styles that shouldn't appear in printable Word/PDF
    clean_html = re.sub(r'<tr class="page-divider-row">[\s\S]*?</tr>', '', html_str)
    clean_html = re.sub(r'<div class="doc-page-break"[\s\S]*?</div>', '', clean_html)
    clean_html = re.sub(r'<style id="edubot-injected-style">[\s\S]*?<\/style>', '', clean_html)
    
    # 1. Ensure UTF-8 charset
    clean_html = clean_html.replace('charset=windows-1252', 'charset=utf-8').replace('charset="windows-1252"', 'charset="utf-8"')
    if '<head>' in clean_html.lower() and 'charset=' not in clean_html.lower():
        clean_html = re.sub(r'(<head[^>]*>)', r'\1\n<meta charset="utf-8">', clean_html, count=1, flags=re.IGNORECASE)

    clean_base = re.sub(r'(_tahrirlangan.*|_converted.*)', '', base_name)
    docx_name = f"{clean_base}_tahrirlangan.docx"
    docx_path = os.path.abspath(os.path.join(target_dir, docx_name))
    pdf_name = f"{clean_base}_tahrirlangan.pdf"
    pdf_path = os.path.abspath(os.path.join(target_dir, pdf_name))

    timestamp = int(datetime.now().timestamp())
    temp_html = os.path.abspath(os.path.join(target_dir, f"temp_save_{timestamp}_{os.getpid()}.html"))
    with open(temp_html, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(clean_html)

    # Convert with Word COM
    pythoncom.CoInitialize()
    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx('Word.Application')
        word.Visible = False
        word.DisplayAlerts = 0
        word.Options.SaveInterval = 0
        
        doc = word.Documents.Open(FileName=temp_html, ReadOnly=True, ConfirmConversions=False, AddToRecentFiles=False)
        doc.SaveAs(docx_path, FileFormat=16) # FileFormat=16 wdFormatXMLDocument (DOCX)
        doc.SaveAs(pdf_path, FileFormat=17)  # FileFormat=17 wdFormatPDF
        doc.Close(SaveChanges=0)
        doc = None
        word.Quit(SaveChanges=0)
        word = None
    except Exception as e:
        logger.warning(f"Word COM save encountered error: {e}. Checking if files were produced...")
        if not os.path.exists(docx_path) or not os.path.exists(pdf_path):
            raise e
    finally:
        if doc:
            try: doc.Close(SaveChanges=0)
            except Exception: pass
        if word:
            try: word.Quit(SaveChanges=0)
            except Exception: pass
        pythoncom.CoUninitialize()
        if os.path.exists(temp_html):
            try: os.remove(temp_html)
            except Exception: pass

    return {
        "docx_path": docx_path,
        "docx_name": docx_name,
        "pdf_path": pdf_path,
        "pdf_name": pdf_name
    }


@router.get("/{file_id}/html")
async def get_file_html(
    file_id: int,
    user: dict = Depends(get_current_user)
):
    """Faylni (DOCX yoki PDF) asl formati, jadvallari va shriftlari bilan to'liq HTML ga aylantirib beradi."""
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")

        ext = os.path.splitext(target.file_name)[1].lower()
        
        try:
            import asyncio
            if ext in ('.docx', '.doc'):
                html = await asyncio.to_thread(docx_to_filtered_html, target.local_path, settings.processed_dir)
            elif ext == '.pdf':
                html = await asyncio.to_thread(pdf_to_filtered_html, target.local_path, settings.processed_dir)
            else:
                with open(target.local_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                html = f"<html><head><meta charset='utf-8'></head><body><pre style='white-space: pre-wrap; font-family: monospace;'>{content}</pre></body></html>"

            return {
                "file_id": target.id,
                "file_name": target.file_name,
                "file_type": ext.lstrip("."),
                "html": html
            }
        except Exception as e:
            logger.error(f"Error converting document {file_id} to HTML: {e}")
            raise HTTPException(status_code=500, detail=f"Hujjatni ochishda xatolik: {str(e)}")


@router.post("/{file_id}/save-html")
async def save_file_html(
    file_id: int,
    data: dict,
    user: dict = Depends(get_current_user)
):
    """Tahrirlangan HTML hujjatni yangi DOCX va PDF formatda saqlaydi va Telegramga yuboradi."""
    html_content = data.get("html", "")
    format_type = data.get("format", "both")
    
    if not html_content or not html_content.strip():
        raise HTTPException(status_code=400, detail="Hujjat bo'sh bo'lishi mumkin emas")

    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Asosiy fayl topilmadi")

        base_name = os.path.splitext(target.file_name)[0]
        
        import asyncio
        try:
            result = await asyncio.to_thread(
                save_html_to_office_documents,
                html_content,
                base_name,
                settings.processed_dir,
                format_type
            )
        except Exception as e:
            logger.error(f"Error saving HTML to office docs: {e}")
            raise HTTPException(status_code=500, detail=f"Faylni saqlashda xatolik: {str(e)}")

        docx_rec = None
        pdf_rec = None
        
        if result.get("docx_path") and os.path.exists(result["docx_path"]):
            docx_rec = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=result["docx_name"],
                file_type="docx",
                telegram_file_id="",
                local_path=result["docx_path"],
                file_size=os.path.getsize(result["docx_path"]),
                upsert=True
            )
            await send_file_to_telegram(
                user["telegram_id"],
                result["docx_path"],
                f"📝 {result['docx_name']} tahrirlangan Word hujjatingiz tayyor bo'ldi!"
            )

        if result.get("pdf_path") and os.path.exists(result["pdf_path"]):
            pdf_rec = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=result["pdf_name"],
                file_type="pdf",
                telegram_file_id="",
                local_path=result["pdf_path"],
                file_size=os.path.getsize(result["pdf_path"]),
                upsert=True
            )
            await send_file_to_telegram(
                user["telegram_id"],
                result["pdf_path"],
                f"📕 {result['pdf_name']} tahrirlangan PDF hujjatingiz tayyor bo'ldi!"
            )

        primary_rec = docx_rec if format_type == "docx" else (pdf_rec if format_type == "pdf" else (docx_rec or pdf_rec))

        return {
            "status": "ok",
            "message": "Hujjat muvaffaqiyatli saqlandi va Telegramingizga yuborildi!",
            "new_file_id": primary_rec.id if primary_rec else target.id,
            "new_file_name": primary_rec.file_name if primary_rec else target.file_name,
            "docx_file_id": docx_rec.id if docx_rec else None,
            "docx_file_name": docx_rec.file_name if docx_rec else None,
            "pdf_file_id": pdf_rec.id if pdf_rec else None,
            "pdf_file_name": pdf_rec.file_name if pdf_rec else None
        }



@router.post("/images-to-pdf")
async def images_to_pdf(
    files: List[UploadFile] = File(...),
    page_size: str = Form("A4"),
    orientation: str = Form("portrait"),
    fit_mode: str = Form("fit"),
    margin: int = Form(20),
    title: str = Form(""),
    user: dict = Depends(get_current_user)
):
    """Bir nechta rasmlarni tanlangan format (A4, A3, Original) va yo'nalishda sifatli PDF ga birlashtirish."""
    try:
        from PIL import Image, ImageOps
        images = []
        user_dir = os.path.join(settings.upload_dir, str(user["telegram_id"]))
        os.makedirs(user_dir, exist_ok=True)
        os.makedirs(settings.processed_dir, exist_ok=True)

        for uploaded in files:
            temp_path = os.path.join(user_dir, sanitize_filename(uploaded.filename))
            content = await uploaded.read()
            with open(temp_path, "wb") as f:
                f.write(content)
            img = Image.open(temp_path)
            
            # EXIF rotation auto-correction
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass

            if img.mode != 'RGB':
                img = img.convert('RGB')
            images.append(img)

        if not images:
            raise HTTPException(status_code=400, detail="Kamida 1 ta rasm yuklang")

        processed_pages = []
        target_size = page_size.upper()

        if target_size == "ORIGINAL":
            # Har bir rasm o'zining asl o'lchamida
            for img in images:
                processed_pages.append(img)
        else:
            # Standart A4 yoki A3 (150 DPI)
            if target_size == "A3":
                base_w, base_h = 1754, 2480
            else: # A4 default
                base_w, base_h = 1240, 1754

            # Orientation check
            if orientation.lower() == "landscape":
                page_w, page_h = max(base_w, base_h), min(base_w, base_h)
            elif orientation.lower() == "portrait":
                page_w, page_h = min(base_w, base_h), max(base_w, base_h)
            else: # auto orientation per image
                page_w, page_h = min(base_w, base_h), max(base_w, base_h)

            margin_px = max(0, min(100, int(margin))) * 2 # scale margin for 150dpi

            for img in images:
                cur_w, cur_h = page_w, page_h
                if orientation.lower() == "auto":
                    if img.width > img.height:
                        cur_w, cur_h = max(base_w, base_h), min(base_w, base_h)
                    else:
                        cur_w, cur_h = min(base_w, base_h), max(base_w, base_h)

                canvas = Image.new('RGB', (cur_w, cur_h), (255, 255, 255))
                avail_w = max(10, cur_w - (margin_px * 2))
                avail_h = max(10, cur_h - (margin_px * 2))

                if fit_mode == "fill":
                    # Rasmni sahifaga to'liq moslab proporsiyasiz cho'zish
                    resized = img.resize((avail_w, avail_h), Image.Resampling.LANCZOS)
                    canvas.paste(resized, (margin_px, margin_px))
                else:
                    # Proporsiyasini saqlagan holda markazlashtirish (fit)
                    ratio = min(avail_w / img.width, avail_h / img.height)
                    new_w = max(1, int(img.width * ratio))
                    new_h = max(1, int(img.height * ratio))
                    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    paste_x = (cur_w - new_w) // 2
                    paste_y = (cur_h - new_h) // 2
                    canvas.paste(resized, (paste_x, paste_y))

                processed_pages.append(canvas)

        clean_title = sanitize_filename(title.strip()) if title and title.strip() else ""
        if not clean_title:
            clean_title = "Rasmlar_PDF"
        if not clean_title.lower().endswith(".pdf"):
            clean_title = f"{clean_title}.pdf"

        out_path = os.path.join(settings.processed_dir, clean_title)
        
        processed_pages[0].save(
            out_path, 
            save_all=True, 
            append_images=processed_pages[1:], 
            resolution=150.0,
            quality=95
        )

        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            record = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=clean_title,
                file_type="pdf",
                telegram_file_id="",
                local_path=out_path,
                file_size=os.path.getsize(out_path),
                upsert=True
            )

            # Auto-send to Telegram chat
            await send_file_to_telegram(
                user["telegram_id"],
                out_path,
                f"🖼️ {len(processed_pages)} ta rasmdan tayyorlangan PDF: {clean_title}"
            )

            return {"status": "ok", "new_file_id": record.id, "new_file_name": clean_title}
    except Exception as e:
        logger.error(f"Images to PDF error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{file_id}/extract-images")
async def extract_images_from_pdf(
    file_id: int,
    user: dict = Depends(get_current_user)
):
    """PDF fayl ichidagi barcha rasmlarni ajratib oladi va ZIP arxivda beradi."""
    import fitz
    import zipfile
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")

        doc = fitz.open(target.local_path)
        base = os.path.splitext(target.file_name)[0]
        zip_name = f"{base}_rasmlar.zip"
        zip_path = os.path.join(settings.processed_dir, zip_name)

        img_count = 0
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                image_list = page.get_images(full=True)
                for img_idx, img_info in enumerate(image_list):
                    xref = img_info[0]
                    try:
                        base_image = doc.extract_image(xref)
                        if base_image and "image" in base_image:
                            image_bytes = base_image["image"]
                            image_ext = base_image["ext"]
                            img_filename = f"sahifa_{page_idx+1}_rasm_{img_idx+1}.{image_ext}"
                            zipf.writestr(img_filename, image_bytes)
                            img_count += 1
                    except Exception:
                        pass
        doc.close()

        if img_count == 0:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            raise HTTPException(status_code=400, detail="Ushbu PDF ichida rasm topilmadi")

        record = await crud.save_file_record(
            session=session,
            user_id=db_user.id,
            file_name=zip_name,
            file_type="zip",
            telegram_file_id="",
            local_path=zip_path,
            file_size=os.path.getsize(zip_path)
        )

        # Auto-send to Telegram chat
        await send_file_to_telegram(
            user["telegram_id"],
            zip_path,
            f"🖼️ PDF dan ajratilgan {img_count} ta fotosurat arxivi (ZIP)!"
        )

        return {"status": "ok", "new_file_id": record.id, "new_file_name": zip_name, "images_count": img_count}
