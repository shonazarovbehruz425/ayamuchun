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
from bot.processors.pdf_processor import PDFProcessor
from bot.processors.image_processor import ImageProcessor
from bot.utils.helpers import sanitize_filename, generate_unique_filename
from PIL import Image

# Prevent decompression bomb attacks globally in files.py
Image.MAX_IMAGE_PIXELS = 25_000_000

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
converter = FileConverter()
word_processor = WordProcessor()
pdf_processor = PDFProcessor()
image_processor = ImageProcessor()

MAX_UPLOAD_SIZE = 35 * 1024 * 1024  # 35 MB

async def save_upload_stream_safely(upload_file: UploadFile, dest_path: str, max_bytes: int = MAX_UPLOAD_SIZE) -> int:
    """Stream chunks to disk without loading entire file into RAM, enforcing maximum size limit."""
    total_written = 0
    chunk_size = 1024 * 512  # 512KB chunks
    with open(dest_path, "wb") as out_f:
        while True:
            chunk = await upload_file.read(chunk_size)
            if not chunk:
                break
            total_written += len(chunk)
            if total_written > max_bytes:
                out_f.close()
                if os.path.exists(dest_path):
                    try: os.remove(dest_path)
                    except Exception: pass
                raise HTTPException(
                    status_code=413,
                    detail=f"Fayl hajmi ruxsat etilgan limitdan ({max_bytes // (1024*1024)} MB) oshib ketdi."
                )
            out_f.write(chunk)
    return total_written


def format_file_size_human(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} GB"

def build_file_caption(file_name: str, tool_name: str, details: list = None, file_size: int = None) -> str:
    """Yuborilayotgan hujjat tagiga tushunarli, chiroyli va aniq ma'lumotli caption yasash."""
    now_str = datetime.now().strftime("%d.%m.%Y, %H:%M")
    lines = [
        f"🎯 <b>{tool_name}</b>",
        f"📄 <b>Fayl:</b> <code>{file_name}</code>"
    ]
    if file_size and file_size > 0:
        lines.append(f"📦 <b>Hajmi:</b> {format_file_size_human(file_size)}")
    if details:
        for d in details:
            lines.append(f"ℹ️ {d}")
    lines.append(f"⏰ <b>Vaqt:</b> {now_str}")
    lines.append("🤖 <i>EduBot Pro orqali tayyorlandi</i>")
    return "\n".join(lines)

async def send_file_to_telegram(telegram_id: int, file_path: str, caption: str = "", file_id: str = None):
    """Tayyor bo'lgan faylni foydalanuvchining Telegram chatiga to'g'ridan-to'g'ri (kanal nomisiz, hide name) yuborish."""
    if not settings.BOT_TOKEN or not telegram_id or settings.BOT_TOKEN in ("local_dev_preview_token", "your_bot_token_here"):
        logger.warning(f"Telegramga yuborilmadi: bot_token={bool(settings.BOT_TOKEN)}, tg_id={telegram_id}")
        return
    import httpx
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendDocument"
    try:
        # 1. Fast direct sending via telegram_file_id (100% clean, no channel info)
        if file_id:
            async with httpx.AsyncClient(timeout=60.0) as client:
                data = {"chat_id": telegram_id, "document": file_id, "caption": caption, "parse_mode": "HTML"}
                resp = await client.post(url, data=data)
                if resp.status_code == 200:
                    logger.info(f"Fayl file_id orqali user {telegram_id} chatiga yuborildi (Kanal nomi yashirin)")
                    return

        # 2. Send via fresh document stream
        if file_path and os.path.exists(file_path):
            async with httpx.AsyncClient(timeout=90.0) as client:
                with open(file_path, "rb") as f:
                    files = {"document": (os.path.basename(file_path), f)}
                    data = {"chat_id": telegram_id, "caption": caption, "parse_mode": "HTML"}
                    resp = await client.post(url, data=data, files=files)
                    if resp.status_code == 200:
                        logger.info(f"Fayl stream orqali user {telegram_id} chatiga yuborildi (Kanal nomi yashirin)")
    except Exception as e:
        logger.warning(f"Telegramga fayl yuborishda xatolik: {e}")

async def save_and_backup_user_file(
    session,
    db_user,
    user_dict: dict,
    local_path: str,
    file_name: str,
    file_type: str,
    tool_name: str = "Hujjat"
):
    """Faylni Telegram kanalga (-1003745209875) doimiy zaxiralash va bazaga saqlash."""
    from bot.services.cloud_storage import get_cloud_storage
    cloud_storage = get_cloud_storage()
    tg_id = user_dict.get("telegram_id")
    full_name = f"{user_dict.get('first_name', '')} {user_dict.get('last_name', '')}".strip() or "Foydalanuvchi"
    username = user_dict.get("username", "")

    file_id, msg_id = await cloud_storage.backup_file_to_channel(
        file_path=local_path,
        file_name=file_name,
        telegram_id=tg_id,
        user_full_name=full_name,
        username=username,
        tool_name=tool_name
    )
    rec = await crud.save_file_record(
        session=session,
        user_id=db_user.id,
        file_name=file_name,
        file_type=file_type,
        telegram_file_id=file_id or "",
        local_path=local_path,
        file_size=os.path.getsize(local_path),
        channel_message_id=msg_id
    )
    return rec


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
        
        file_size = await save_upload_stream_safely(file, dest_path)
            
        ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
        
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            record = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=dest_path,
                file_name=file.filename,
                file_type=ext,
                tool_name="Yuklangan_Fayl"
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
            tool_title = "Word ➔ PDF Konvertatsiyasi" if new_ext == "pdf" else "PDF ➔ Word (DOCX) Konvertatsiyasi"
            new_record = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=out_path,
                file_name=os.path.basename(out_path),
                file_type=new_ext,
                tool_name=tool_title
            )

            # Auto-send to Telegram chat with rich caption
            extra_info = ["Asl matn, shrift va jadvallar to'liq saqlab qolindi"]
            caption = build_file_caption(
                file_name=new_record.file_name,
                tool_name=tool_title,
                details=extra_info,
                file_size=os.path.getsize(out_path)
            )
            await send_file_to_telegram(user["telegram_id"], out_path, caption, file_id=new_record.telegram_file_id)

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
        
        if not target:
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
            
        # Ensure local file exists on disk, auto-restoring from Telegram Cloud (-1003745209875) if wiped
        from bot.services.cloud_storage import get_cloud_storage
        cloud_storage = get_cloud_storage()
        valid_path = await cloud_storage.ensure_local_file(target)
        if not valid_path or not os.path.exists(valid_path):
            raise HTTPException(status_code=404, detail="Fayl serverda topilmadi")
            
        return FastFileResponse(
            path=valid_path,
            filename=target.file_name,
            media_type="application/octet-stream"
        )


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

        new_record = await save_and_backup_user_file(
            session=session,
            db_user=db_user,
            user_dict=user,
            local_path=out_path,
            file_name=out_name,
            file_type=ext.lstrip("."),
            tool_name="Tahrirlangan_Fayl"
        )

        # Auto-send to Telegram chat
        await send_file_to_telegram(
            user["telegram_id"],
            out_path,
            f"📝 {out_name} tahrirlangan faylingiz tayyor bo'ldi!",
            file_id=new_record.telegram_file_id
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
    First attempts pdf2docx for native paragraph/table reconstruction.
    If pdf2docx fails or produces empty output, falls back to high-fidelity structured PyMuPDF text & table extraction
    preserving font sizes, bold styles, and page margins without text overlapping.
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

    # High-fidelity PyMuPDF structured text flow (avoids overlapping and preserves typography)
    try:
        doc = fitz.open(pdf_path)
        total_p = len(doc)
        pages_html = []
        for idx, page in enumerate(doc):
            p_num = idx + 1
            break_tag = ""
            if idx > 0:
                break_tag = f'<div class="doc-page-break" data-page="{p_num}"><span class="page-tag">Sahifa {p_num}</span></div>'
            
            page_dict = page.get_text("dict")
            page_content = []
            
            for block in page_dict.get("blocks", []):
                b_type = block.get("type", 0)
                if b_type == 0:  # Text block
                    for line in block.get("lines", []):
                        spans_html = []
                        line_text_raw = ""
                        for s in line.get("spans", []):
                            txt = s.get("text", "")
                            line_text_raw += txt
                            if not txt:
                                continue
                            esc_txt = html.escape(txt).replace("  ", "&nbsp;&nbsp;")
                            size = round(s.get("size", 11.5), 1)
                            flags = s.get("flags", 0)
                            is_bold = bool(flags & 2)
                            is_italic = bool(flags & 1)
                            style_parts = [f"font-size: {size}pt;"]
                            if is_bold:
                                style_parts.append("font-weight: bold;")
                            if is_italic:
                                style_parts.append("font-style: italic;")
                            span_css = " ".join(style_parts)
                            spans_html.append(f'<span style="{span_css}">{esc_txt}</span>')
                        
                        if line_text_raw.strip():
                            p_html = "".join(spans_html)
                            page_content.append(f'<p style="margin: 3px 0; line-height: 1.38; text-align: left;">{p_html}</p>')
            
            rendered_page_body = "".join(page_content) if page_content else "<p>&nbsp;</p>"
            pages_html.append(f"{break_tag}<div class='pdf-page' style='padding: 8px 0;'>{rendered_page_body}</div>")
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


class _HTMLDocxParser(HTMLParser):
    """Clean standard library HTML to python-docx builder for 100% platform-independent Word generation."""
    def __init__(self):
        super().__init__()
        from docx import Document
        self.doc = Document()
        self.current_p = None
        self.tag_stack = []
        self.in_table = False
        self.table_rows = []
        self.current_row = []
        self.current_cell = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        style_str = attr_dict.get('style', '')
        tag_lower = tag.lower()
        
        is_bold = ('b' == tag_lower or 'strong' == tag_lower or 'font-weight: bold' in style_str.lower() or 'font-weight:bold' in style_str.lower())
        is_italic = ('i' == tag_lower or 'em' == tag_lower or 'font-style: italic' in style_str.lower() or 'font-style:italic' in style_str.lower())
        is_underline = ('u' == tag_lower or 'underline' in style_str.lower())
        
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        align = None
        if 'text-align: center' in style_str.lower() or 'text-align:center' in style_str.lower():
            align = WD_ALIGN_PARAGRAPH.CENTER
        elif 'text-align: right' in style_str.lower() or 'text-align:right' in style_str.lower():
            align = WD_ALIGN_PARAGRAPH.RIGHT
        elif 'text-align: justify' in style_str.lower() or 'text-align:justify' in style_str.lower():
            align = WD_ALIGN_PARAGRAPH.JUSTIFY

        font_size = None
        sz_match = re.search(r'font-size:\s*([\d\.]+)pt', style_str, re.IGNORECASE)
        if sz_match:
            try:
                font_size = float(sz_match.group(1))
            except Exception:
                pass

        self.tag_stack.append({
            'tag': tag_lower,
            'bold': is_bold,
            'italic': is_italic,
            'underline': is_underline,
            'font_size': font_size,
            'align': align
        })

        if tag_lower in ('p', 'h1', 'h2', 'h3', 'h4', 'div'):
            if not self.in_table:
                self.current_p = self.doc.add_paragraph()
                if align:
                    self.current_p.alignment = align
        elif tag_lower == 'table':
            self.in_table = True
            self.table_rows = []
        elif tag_lower in ('td', 'th'):
            self.current_cell = []

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == 'table':
            self.in_table = False
            if self.table_rows:
                max_cols = max(len(r) for r in self.table_rows) if self.table_rows else 1
                tbl = self.doc.add_table(rows=len(self.table_rows), cols=max_cols)
                tbl.style = 'Table Grid'
                for r_i, r in enumerate(self.table_rows):
                    for c_i, cell_text in enumerate(r):
                        if c_i < max_cols:
                            tbl.cell(r_i, c_i).text = cell_text
                self.doc.add_paragraph()
        elif tag_lower == 'tr':
            if self.in_table and self.current_row:
                self.table_rows.append(self.current_row)
                self.current_row = []
        elif tag_lower in ('td', 'th'):
            if self.in_table:
                self.current_row.append(''.join(self.current_cell).strip())
                self.current_cell = []
        
        for i in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[i]['tag'] == tag_lower:
                self.tag_stack.pop(i)
                break

    def handle_data(self, data):
        txt = data
        if not txt:
            return
        if self.in_table:
            self.current_cell.append(txt)
            return

        if self.current_p is None:
            self.current_p = self.doc.add_paragraph()

        from docx.shared import Pt
        eff_bold = any(item.get('bold') for item in self.tag_stack)
        eff_italic = any(item.get('italic') for item in self.tag_stack)
        eff_underline = any(item.get('underline') for item in self.tag_stack)
        
        eff_font_size = 11.5
        for item in reversed(self.tag_stack):
            if item.get('font_size'):
                eff_font_size = item['font_size']
                break

        run = self.current_p.add_run(txt)
        run.font.name = 'Times New Roman'
        run.font.size = Pt(eff_font_size)
        if eff_bold: run.bold = True
        if eff_italic: run.italic = True
        if eff_underline: run.underline = True


def save_html_to_office_documents(html_str: str, base_name: str, target_dir: str, save_format: str = "both") -> dict:
    """
    Saves edited HTML back to native DOCX and PDF across all platforms (Linux/Docker/Windows).
    Guarantees clean execution without crashing on missing pythoncom or LibreOffice.
    """
    import subprocess
    import fitz
    from docx import Document

    # Clean out internal page divider rows & styles that shouldn't appear in printable Word/PDF
    clean_html = re.sub(r'<tr class="page-divider-row">[\s\S]*?</tr>', '', html_str)
    clean_html = re.sub(r'<div class="doc-page-break"[\s\S]*?</div>', '', clean_html)
    clean_html = re.sub(r'<style id="edubot-injected-style">[\s\S]*?<\/style>', '', clean_html)
    
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

    # Strategy 1: Word COM (Only on Windows if pywin32 is installed and Word is active)
    converted_via_com = False
    if os.name == 'nt':
        try:
            import pythoncom
            import win32com.client
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
                converted_via_com = True
            finally:
                if doc:
                    try: doc.Close(SaveChanges=0)
                    except Exception: pass
                if word:
                    try: word.Quit(SaveChanges=0)
                    except Exception: pass
                pythoncom.CoUninitialize()
        except Exception as e:
            logger.info(f"Word COM not available or skipped ({e}), proceeding with cross-platform converters...")

    # Strategy 2: LibreOffice headless (Available on Linux/Docker and servers)
    if not converted_via_com:
        for cmd_name in ('soffice', 'libreoffice'):
            try:
                # Convert HTML to DOCX via LibreOffice
                cmd_docx = [cmd_name, '--headless', '--convert-to', 'docx', '--outdir', target_dir, temp_html]
                res_docx = subprocess.run(cmd_docx, capture_output=True, timeout=30)
                temp_gen_docx = os.path.join(target_dir, f"temp_save_{timestamp}_{os.getpid()}.docx")
                if os.path.exists(temp_gen_docx):
                    if os.path.exists(docx_path):
                        try: os.remove(docx_path)
                        except Exception: pass
                    os.rename(temp_gen_docx, docx_path)

                # Convert HTML to PDF via LibreOffice
                cmd_pdf = [cmd_name, '--headless', '--convert-to', 'pdf', '--outdir', target_dir, temp_html]
                res_pdf = subprocess.run(cmd_pdf, capture_output=True, timeout=30)
                temp_gen_pdf = os.path.join(target_dir, f"temp_save_{timestamp}_{os.getpid()}.pdf")
                if os.path.exists(temp_gen_pdf):
                    if os.path.exists(pdf_path):
                        try: os.remove(pdf_path)
                        except Exception: pass
                    os.rename(temp_gen_pdf, pdf_path)
                break
            except Exception as lo_err:
                logger.debug(f"LibreOffice command {cmd_name} attempt failed: {lo_err}")

    # Strategy 3: Pure Python-native fallback (python-docx + PyMuPDF)
    # Guarantees valid DOCX and PDF files even on environments with zero external binaries!
    if not os.path.exists(docx_path) or os.path.getsize(docx_path) == 0:
        try:
            parser = _HTMLDocxParser()
            clean_text_for_parser = re.sub(r'<style[\s\S]*?<\/style>', '', clean_html, flags=re.IGNORECASE)
            clean_text_for_parser = re.sub(r'<script[\s\S]*?<\/script>', '', clean_text_for_parser, flags=re.IGNORECASE)
            parser.feed(clean_text_for_parser)
            parser.doc.save(docx_path)
            logger.info(f"Generated DOCX via pure python-docx fallback: {docx_path}")
        except Exception as py_docx_err:
            logger.error(f"python-docx fallback error: {py_docx_err}")

    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        try:
            if os.path.exists(docx_path) and os.path.getsize(docx_path) > 0:
                doc_mupdf = Document(docx_path)
                pdf_doc = fitz.open()
                pdf_page = pdf_doc.new_page(width=595, height=842) # A4
                rect = fitz.Rect(45, 45, 550, 797)
                
                pdf_lines = []
                for p in doc_mupdf.paragraphs:
                    if p.text.strip():
                        pdf_lines.append(p.text.strip())
                for t in doc_mupdf.tables:
                    for r in t.rows:
                        row_txt = " | ".join(c.text.strip() for c in r.cells if c.text.strip())
                        if row_txt:
                            pdf_lines.append(row_txt)
                
                full_text = "\n\n".join(pdf_lines)
                pdf_page.insert_textbox(rect, full_text, fontsize=11, fontname="helv")
                pdf_doc.save(pdf_path)
                pdf_doc.close()
                logger.info(f"Generated PDF via PyMuPDF fallback: {pdf_path}")
        except Exception as py_pdf_err:
            logger.error(f"PyMuPDF fallback error: {py_pdf_err}")

    # Clean temp html
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
                import html as py_html
                with open(target.local_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                escaped_content = py_html.escape(content)
                html = f"<html><head><meta charset='utf-8'></head><body><pre style='white-space: pre-wrap; font-family: monospace;'>{escaped_content}</pre></body></html>"

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
            docx_rec = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=result["docx_path"],
                file_name=result["docx_name"],
                file_type="docx",
                tool_name="Tahrirlangan_Word_Hujjati"
            )
            docx_caption = build_file_caption(
                file_name=result["docx_name"],
                tool_name="Tahrirlangan Word Hujjati",
                details=["Kiritilgan o'zgarishlar bilan saqlangan Word (DOCX) formati"],
                file_size=os.path.getsize(result["docx_path"])
            )
            await send_file_to_telegram(user["telegram_id"], result["docx_path"], docx_caption, file_id=docx_rec.telegram_file_id)

        if result.get("pdf_path") and os.path.exists(result["pdf_path"]):
            pdf_rec = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=result["pdf_path"],
                file_name=result["pdf_name"],
                file_type="pdf",
                tool_name="Tahrirlangan_PDF_Hujjati"
            )
            pdf_caption = build_file_caption(
                file_name=result["pdf_name"],
                tool_name="Tahrirlangan PDF Hujjati",
                details=["Kiritilgan o'zgarishlar bilan saqlangan A4 PDF formati"],
                file_size=os.path.getsize(result["pdf_path"])
            )
            await send_file_to_telegram(user["telegram_id"], result["pdf_path"], pdf_caption, file_id=pdf_rec.telegram_file_id)

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
            await save_upload_stream_safely(uploaded, temp_path)
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
            record = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=out_path,
                file_name=clean_title,
                file_type="pdf",
                tool_name="Rasmlardan_Yaratilgan_PDF"
            )

            # Auto-send to Telegram chat
            img_caption = build_file_caption(
                file_name=clean_title,
                tool_name="Rasmlardan Yaratilgan PDF",
                details=[f"Sahifalar soni: {len(processed_pages)} ta", f"Varaq o'lchami: {page_size.upper()}"],
                file_size=os.path.getsize(out_path)
            )
            await send_file_to_telegram(user["telegram_id"], out_path, img_caption, file_id=record.telegram_file_id)

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

        record = await save_and_backup_user_file(
            session=session,
            db_user=db_user,
            user_dict=user,
            local_path=zip_path,
            file_name=zip_name,
            file_type="zip",
            tool_name="PDF_Rasmlari_Arxivi"
        )

        # Auto-send to Telegram chat
        zip_caption = build_file_caption(
            file_name=zip_name,
            tool_name="PDF Rasmlari Arxivi",
            details=[f"Ajratib olingan rasmlar: {img_count} ta", "Asl sifatdagi ZIP arxiv"],
            file_size=os.path.getsize(zip_path)
        )
        await send_file_to_telegram(user["telegram_id"], zip_path, zip_caption, file_id=record.telegram_file_id)

        return {"status": "ok", "new_file_id": record.id, "new_file_name": zip_name, "images_count": img_count}


# ── New PDF Power Tools: Merge, Split, Compress, Watermark ───────────────────

@router.post("/merge-pdfs")
async def merge_pdfs_endpoint(
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user)
):
    """Bir nechta PDF fayllarni bitta hujjatga birlashtirish."""
    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="Kamida 2 ta PDF fayl tanlanishi shart")

    temp_paths = []
    try:
        timestamp = int(datetime.now().timestamp())
        for idx, file in enumerate(files):
            ext = os.path.splitext(file.filename)[1].lower()
            if ext != '.pdf':
                raise HTTPException(status_code=400, detail=f"'{file.filename}' PDF formatida emas")
            t_path = os.path.join(settings.upload_dir, f"merge_in_{timestamp}_{idx}.pdf")
            await save_upload_stream_safely(file, t_path)
            temp_paths.append(t_path)

        out_name = f"birlashtirilgan_hujjat_{timestamp}.pdf"
        out_path = os.path.join(settings.processed_dir, out_name)
        await pdf_processor.merge_pdfs(temp_paths, out_path)

        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            record = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=out_path,
                file_name=out_name,
                file_type="pdf",
                tool_name="Birlashtirilgan_PDF"
            )

        if user.get("telegram_id"):
            try:
                m_caption = build_file_caption(
                    file_name=out_name,
                    tool_name="Birlashtirilgan PDF Hujjati",
                    details=[f"Birlashtirilgan fayllar soni: {len(files)} ta"],
                    file_size=os.path.getsize(out_path)
                )
                await send_file_to_telegram(telegram_id=user["telegram_id"], file_path=out_path, caption=m_caption, file_id=record.telegram_file_id)
            except Exception:
                pass

        return {
            "success": True,
            "file_id": record.id,
            "file_name": out_name,
            "download_url": f"/api/files/{record.id}/download",
            "merged_count": len(files)
        }
    finally:
        for p in temp_paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@router.post("/split-pdf")
async def split_pdf_endpoint(
    file: UploadFile = File(None),
    file_id: int = Form(None),
    split_mode: str = Form("range"),
    page_range: str = Form("1"),
    user: dict = Depends(get_current_user)
):
    """PDF'ni alohida sahifalarga yoki qismlarga ajratish."""
    src_path = None
    is_temp = False
    timestamp = int(datetime.now().timestamp())

    try:
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            if file and file.filename:
                src_path = os.path.join(settings.upload_dir, f"split_in_{timestamp}.pdf")
                await save_upload_stream_safely(file, src_path)
                is_temp = True
            elif file_id:
                files = await crud.get_user_files(session, db_user.id)
                target = next((f for f in files if f.id == file_id), None)
                if not target or not os.path.exists(target.local_path):
                    raise HTTPException(status_code=404, detail="Fayl topilmadi")
                src_path = target.local_path
            else:
                raise HTTPException(status_code=400, detail="PDF fayl yuklanishi kerak")

            split_res = await pdf_processor.split_pdf_advanced(
                file_path=src_path,
                output_dir=settings.processed_dir,
                split_mode=split_mode,
                page_range_str=page_range
            )

            out_path = split_res["file_path"]
            out_name = split_res["file_name"]
            f_type = "zip" if split_res["is_zip"] else "pdf"

            record = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=out_path,
                file_name=out_name,
                file_type=f_type,
                tool_name="PDF_Ajratilgan_Sahifalar"
            )

            if user.get("telegram_id"):
                try:
                    if split_res["is_zip"]:
                        s_caption = build_file_caption(
                            file_name=out_name,
                            tool_name="PDF Sahifalari (Alohida ZIP)",
                            details=[f"Jami sahifalar: {split_res['total_pages']} ta", f"Arxivlangan fayllar: {split_res['extracted_count']} ta"],
                            file_size=os.path.getsize(out_path)
                        )
                    else:
                        s_caption = build_file_caption(
                            file_name=out_name,
                            tool_name="PDF Ajratilgan Qismi",
                            details=[f"Ajratilgan sahifalar: {page_range}", f"Sahifalar soni: {split_res['extracted_count']} ta"],
                            file_size=os.path.getsize(out_path)
                        )
                    await send_file_to_telegram(user["telegram_id"], out_path, caption=s_caption, file_id=record.telegram_file_id)
                except Exception:
                    pass

            return {
                "success": True,
                "file_id": record.id,
                "file_name": out_name,
                "download_url": f"/api/files/{record.id}/download",
                "is_zip": split_res["is_zip"],
                "total_pages": split_res["total_pages"],
                "extracted_count": split_res["extracted_count"]
            }
    finally:
        if is_temp and src_path and os.path.exists(src_path):
            try:
                os.remove(src_path)
            except Exception:
                pass


@router.post("/compress-pdf")
async def compress_pdf_endpoint(
    file: UploadFile = File(None),
    file_id: int = Form(None),
    quality_level: str = Form("medium"),
    user: dict = Depends(get_current_user)
):
    """PDF hajmini siqib, 50-80% gacha kamaytirish."""
    src_path = None
    is_temp = False
    timestamp = int(datetime.now().timestamp())

    try:
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            orig_name = "document.pdf"
            if file and file.filename:
                orig_name = file.filename
                src_path = os.path.join(settings.upload_dir, f"compress_in_{timestamp}.pdf")
                await save_upload_stream_safely(file, src_path)
                is_temp = True
            elif file_id:
                files = await crud.get_user_files(session, db_user.id)
                target = next((f for f in files if f.id == file_id), None)
                if not target or not os.path.exists(target.local_path):
                    raise HTTPException(status_code=404, detail="Fayl topilmadi")
                src_path = target.local_path
                orig_name = target.file_name
            else:
                raise HTTPException(status_code=400, detail="PDF fayl yuklanishi kerak")

            base = os.path.splitext(orig_name)[0]
            clean_base = re.sub(r'(_siqilgan.*|_tahrirlangan.*)', '', base)
            out_name = f"{clean_base}_siqilgan_{timestamp}.pdf"
            out_path = os.path.join(settings.processed_dir, out_name)

            stats = await pdf_processor.compress_pdf(
                file_path=src_path,
                output_path=out_path,
                quality_level=quality_level
            )

            record = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=out_path,
                file_name=out_name,
                file_type="pdf",
                tool_name="Siqilgan_PDF"
            )

            if user.get("telegram_id"):
                try:
                    init_str = format_file_size_human(stats["initial_size"])
                    fin_str = format_file_size_human(stats["final_size"])
                    c_caption = build_file_caption(
                        file_name=out_name,
                        tool_name="Siqilgan PDF Hujjati",
                        details=[
                            f"Oldingi hajm: {init_str}",
                            f"Yangi hajm: {fin_str}",
                            f"Tejalgan joy: {stats['saved_percent']}%"
                        ],
                        file_size=stats["final_size"]
                    )
                    await send_file_to_telegram(user["telegram_id"], out_path, caption=c_caption, file_id=record.telegram_file_id)
                except Exception:
                    pass

            return {
                "success": True,
                "file_id": record.id,
                "file_name": out_name,
                "download_url": f"/api/files/{record.id}/download",
                "initial_size": stats["initial_size"],
                "final_size": stats["final_size"],
                "saved_percent": stats["saved_percent"]
            }
    finally:
        if is_temp and src_path and os.path.exists(src_path):
            try:
                os.remove(src_path)
            except Exception:
                pass


@router.post("/watermark-pdf")
async def watermark_pdf_endpoint(
    file: UploadFile = File(None),
    file_id: int = Form(None),
    mode: str = Form("text"),
    text: str = Form("EduBot"),
    font_size: int = Form(36),
    opacity: float = Form(0.35),
    angle: int = Form(45),
    color: str = Form("#6366f1"),
    logo: UploadFile = File(None),
    user: dict = Depends(get_current_user)
):
    """PDF sahifalariga matn yoki logo watermark qo'yish."""
    src_path = None
    is_temp = False
    temp_logo_path = None
    timestamp = int(datetime.now().timestamp())

    try:
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            orig_name = "document.pdf"
            if file and file.filename:
                orig_name = file.filename
                src_path = os.path.join(settings.upload_dir, f"wm_in_{timestamp}.pdf")
                await save_upload_stream_safely(file, src_path)
                is_temp = True
            elif file_id:
                files = await crud.get_user_files(session, db_user.id)
                target = next((f for f in files if f.id == file_id), None)
                if not target or not os.path.exists(target.local_path):
                    raise HTTPException(status_code=404, detail="Fayl topilmadi")
                src_path = target.local_path
                orig_name = target.file_name
            else:
                raise HTTPException(status_code=400, detail="PDF fayl yuklanishi kerak")

            if mode == "image" and logo and logo.filename:
                logo_ext = os.path.splitext(logo.filename)[1].lower()
                temp_logo_path = os.path.join(settings.upload_dir, f"logo_{timestamp}{logo_ext}")
                await save_upload_stream_safely(logo, temp_logo_path)

            base = os.path.splitext(orig_name)[0]
            clean_base = re.sub(r'(_watermark.*|_tahrirlangan.*)', '', base)
            out_name = f"{clean_base}_watermark_{timestamp}.pdf"
            out_path = os.path.join(settings.processed_dir, out_name)

            await pdf_processor.watermark_pdf(
                file_path=src_path,
                output_path=out_path,
                mode=mode,
                text=text or "EduBot",
                font_size=int(font_size),
                opacity=float(opacity),
                angle=int(angle),
                color_hex=color or "#6366f1",
                logo_path=temp_logo_path
            )

            record = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=out_path,
                file_name=out_name,
                file_type="pdf",
                tool_name="Watermark_PDF"
            )

            if user.get("telegram_id"):
                try:
                    wm_info = f"Matn: '{text}'" if mode == "text" else "Shaxsiy logotip"
                    wm_caption = build_file_caption(
                        file_name=out_name,
                        tool_name="Suv Belgisi (Watermark) Qo'yilgan PDF",
                        details=[f"Belgi turi: {wm_info}", f"Shaffoflik: {int(float(opacity)*100)}%"],
                        file_size=os.path.getsize(out_path)
                    )
                    await send_file_to_telegram(telegram_id=user["telegram_id"], file_path=out_path, caption=wm_caption, file_id=record.telegram_file_id)
                except Exception:
                    pass

            return {
                "success": True,
                "file_id": record.id,
                "file_name": out_name,
                "download_url": f"/api/files/{record.id}/download"
            }
    finally:
        if is_temp and src_path and os.path.exists(src_path):
            try:
                os.remove(src_path)
            except Exception:
                pass
        if temp_logo_path and os.path.exists(temp_logo_path):
            try:
                os.remove(temp_logo_path)
            except Exception:
                pass


@router.post("/photo-3x4")
async def create_photo_3x4_endpoint(
    file: UploadFile = File(None),
    file_id: int = Form(None),
    bg_color: str = Form("#FFFFFF"),
    change_bg: str = Form("false"),
    add_corner: str = Form("false"),
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    user: dict = Depends(get_current_user)
):
    """Pasport, viza, haydovchilik guvohnomasi uchun 3x4 sm rasm va 10x15 sm 6 talik varaq yaratish."""
    src_path = None
    is_temp = False
    timestamp = int(datetime.now().timestamp())

    try:
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            orig_name = "photo.jpg"

            if file and file.filename:
                orig_name = file.filename
                ext = os.path.splitext(orig_name)[1].lower() or ".jpg"
                src_path = os.path.join(settings.upload_dir, f"photo3x4_in_{timestamp}{ext}")
                await save_upload_stream_safely(file, src_path)
                is_temp = True
            elif file_id:
                files = await crud.get_user_files(session, db_user.id)
                target = next((f for f in files if f.id == file_id), None)
                if not target or not os.path.exists(target.local_path):
                    raise HTTPException(status_code=404, detail="Fayl topilmadi")
                src_path = target.local_path
                orig_name = target.file_name
            else:
                raise HTTPException(status_code=400, detail="Surat fayli yuklanishi kerak")

            base = os.path.splitext(orig_name)[0]
            clean_base = re.sub(r'(_3x4.*|_sheet.*)', '', base)

            single_name = f"{clean_base}_foto_3x4_{timestamp}.jpg"
            sheet_name = f"{clean_base}_foto_3x4_varaq_{timestamp}.jpg"

            single_path = os.path.join(settings.processed_dir, single_name)
            sheet_path = os.path.join(settings.processed_dir, sheet_name)

            should_change_bg = change_bg.lower() in ("true", "1", "yes")
            should_add_corner = add_corner.lower() in ("true", "1", "yes")

            stats = await image_processor.process_photo_3x4(
                input_path=src_path,
                output_single_path=single_path,
                output_sheet_path=sheet_path,
                bg_color_hex=bg_color or "#FFFFFF",
                change_bg=should_change_bg,
                add_corner=should_add_corner,
                brightness=float(brightness),
                contrast=float(contrast),
                dpi=300
            )

            # Save and backup both files to channel -1003745209875
            single_rec = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=single_path,
                file_name=single_name,
                file_type="jpg",
                tool_name="Hujjat_Foto_3x4"
            )

            sheet_rec = await save_and_backup_user_file(
                session=session,
                db_user=db_user,
                user_dict=user,
                local_path=sheet_path,
                file_name=sheet_name,
                file_type="jpg",
                tool_name="Foto_10x15_Varaq"
            )

            # Send both to Telegram chat (completely hidden channel name)
            if user.get("telegram_id"):
                try:
                    single_caption = build_file_caption(
                        file_name=single_name,
                        tool_name="Hujjat Foto (3×4 cm)",
                        details=["Standart 30×40 mm (300 DPI bosma sifat)", "Pasport, viza, talaba hujjatlari uchun"],
                        file_size=os.path.getsize(single_path)
                    )
                    await send_file_to_telegram(
                        telegram_id=user["telegram_id"],
                        file_path=single_path,
                        caption=single_caption,
                        file_id=single_rec.telegram_file_id
                    )

                    sheet_caption = build_file_caption(
                        file_name=sheet_name,
                        tool_name="10×15 sm Chop Etish Varaqasi",
                        details=["6 ta 3×4 fotosurat", "Qaychi bilan to'g'ri kesish chiziqlari bilan"],
                        file_size=os.path.getsize(sheet_path)
                    )
                    await send_file_to_telegram(
                        telegram_id=user["telegram_id"],
                        file_path=sheet_path,
                        caption=sheet_caption,
                        file_id=sheet_rec.telegram_file_id
                    )
                except Exception as tg_err:
                    logger.warning(f"Telegram photo 3x4 send error: {tg_err}")

            return {
                "success": True,
                "single_file_id": single_rec.id,
                "single_file_name": single_name,
                "single_download_url": f"/api/files/{single_rec.id}/download",
                "sheet_file_id": sheet_rec.id,
                "sheet_file_name": sheet_name,
                "sheet_download_url": f"/api/files/{sheet_rec.id}/download",
                "dimensions": "30x40 mm (354x472 px)",
                "sheet_info": "10x15 cm (6 ta foto)"
            }
    finally:
        if is_temp and src_path and os.path.exists(src_path):
            try:
                os.remove(src_path)
            except Exception:
                pass


@router.post("/{file_id}/send-to-telegram")
async def resend_file_to_telegram_endpoint(
    file_id: int,
    user: dict = Depends(get_current_user)
):
    """Mavjud faylni foydalanuvchining Telegram chatiga qayta yuborish (kanal nomisiz, hide name)."""
    tg_id = user.get("telegram_id")
    if not tg_id:
        raise HTTPException(status_code=400, detail="Telegram ID aniqlanmadi")

    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, tg_id, user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Fayl topilmadi")

        from bot.services.cloud_storage import get_cloud_storage
        cloud_storage = get_cloud_storage()
        valid_path = await cloud_storage.ensure_local_file(target)

        caption = build_file_caption(
            file_name=target.file_name,
            tool_name="EduBot Hujjati",
            details=["Mening tayyor fayllarim ro'yxatidan yuborildi"],
            file_size=target.file_size
        )
        await send_file_to_telegram(
            telegram_id=tg_id,
            file_path=valid_path,
            caption=caption,
            file_id=target.telegram_file_id
        )
        return {"success": True, "message": "Fayl Telegram chatiga yuborildi!"}
