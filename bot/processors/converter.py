import asyncio
import os
import subprocess
import csv
import logging
from pdf2docx import Converter
from openpyxl import load_workbook, Workbook

logger = logging.getLogger(__name__)

class FileConverter:
    """
    Turli formatdagi fayllarni konvertatsiya qilish uchun sinf.
    """
    
    async def _convert_with_libreoffice(self, input_path: str, output_dir: str, output_format: str = 'pdf') -> str:
        """LibreOffice orqali hujjatni PDF formatiga o'tkazish (umumiy funksiya)."""
        def _run_cmd():
            # LibreOffice headless ishga tushirish uchun buyruq (Windows/Linux/Mac)
            # Windows da "soffice" asosan tizim o'zgaruvchilari orasida bo'lishi kerak.
            cmd = ['soffice', '--headless', '--convert-to', output_format, '--outdir', output_dir, input_path]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Natijaviy fayl manzilini topish
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                expected_output = os.path.join(output_dir, f"{base_name}.{output_format}")
                
                if os.path.exists(expected_output):
                    return expected_output
                else:
                    raise FileNotFoundError("Konvertatsiya qilingan fayl topilmadi.")
            except FileNotFoundError:
                raise Exception("LibreOffice o'rnatilmagan yoki tizim PATH ro'yxatida yo'q. Iltimos, o'rnating.")
            except subprocess.CalledProcessError as e:
                raise Exception(f"LibreOffice orqali konvertatsiya qilishda xatolik: {e.stderr.decode('utf-8', errors='ignore')}")
                
        try:
            return await asyncio.to_thread(_run_cmd)
        except Exception as e:
            logger.error(f"Xato: {e}")
            raise

    async def word_to_pdf(self, input_path: str, output_path: str) -> str:
        """Word dan PDF formatiga o'tkazish (Word COM, LibreOffice yoki PyMuPDF fallback)."""
        output_dir = os.path.dirname(output_path) or '.'
        abs_in = os.path.abspath(input_path)
        abs_out = os.path.abspath(output_path)

        # 1. Windows da Microsoft Word COM orqali 100% asl sifatda konvertatsiya
        if os.name == 'nt':
            def _convert_with_word_com():
                try:
                    import pythoncom
                    import win32com.client
                except ImportError:
                    return None
                pythoncom.CoInitialize()
                word = None
                doc = None
                try:
                    word = win32com.client.Dispatch('Word.Application')
                    word.Visible = False
                    word.DisplayAlerts = False
                    doc = word.Documents.Open(abs_in)
                    doc.SaveAs(abs_out, FileFormat=17)  # 17 = wdFormatPDF
                    doc.Close(SaveChanges=0)
                    return abs_out
                finally:
                    if word:
                        try:
                            word.Quit()
                        except Exception:
                            pass
                    pythoncom.CoUninitialize()

            try:
                await asyncio.to_thread(_convert_with_word_com)
                if os.path.exists(abs_out) and os.path.getsize(abs_out) > 0:
                    return abs_out
            except Exception as e:
                logger.warning(f"Word COM orqali konvertatsiya qilib bo'lmadi: {e}, muqobil usul tekshirilmoqda...")

        # 2. LibreOffice headless orqali sinab ko'rish
        try:
            result_path = await self._convert_with_libreoffice(input_path, output_dir, 'pdf')
            if result_path != output_path and os.path.exists(result_path):
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(result_path, output_path)
            return output_path
        except Exception:
            pass

        # 3. Python-native fallback: PyMuPDF orqali to'liq UTF-8 matnli PDF yaratish
        def _fallback_convert():
            import fitz
            from docx import Document
            doc = Document(input_path)
            pdf = fitz.open()
            
            page = pdf.new_page(width=595, height=842) # A4
            rect = fitz.Rect(50, 50, 545, 792)
            
            lines = []
            for p in doc.paragraphs:
                if p.text.strip():
                    lines.append(p.text.strip())
            
            full_text = "\n\n".join(lines)
            page.insert_textbox(rect, full_text, fontsize=11, fontname="helv")
            pdf.save(output_path)
            pdf.close()
            return output_path

        return await asyncio.to_thread(_fallback_convert)

    async def excel_to_pdf(self, input_path: str, output_path: str) -> str:
        """Excel dan PDF formatiga o'tkazish."""
        output_dir = os.path.dirname(output_path) or '.'
        result_path = await self._convert_with_libreoffice(input_path, output_dir, 'pdf')
        if result_path != output_path:
            os.rename(result_path, output_path)
        return output_path

    async def pptx_to_pdf(self, input_path: str, output_path: str) -> str:
        """PowerPoint dan PDF formatiga o'tkazish."""
        output_dir = os.path.dirname(output_path) or '.'
        result_path = await self._convert_with_libreoffice(input_path, output_dir, 'pdf')
        if result_path != output_path:
            os.rename(result_path, output_path)
        return output_path

    def _convert_scanned_pdf(self, input_path: str, output_path: str) -> str:
        """
        Matnsiz, faqat rasmlardan iborat skaner qilingan PDF hujjatlarni
        Word (.docx) formatiga yuqori sifatli rasm sahifalari ko'rinishida o'tkazish.
        """
        import io
        import fitz
        from docx import Document
        from docx.shared import Inches, Pt

        doc = fitz.open(input_path)
        word_doc = Document()

        for sec in word_doc.sections:
            sec.top_margin = Inches(0.5)
            sec.bottom_margin = Inches(0.5)
            sec.left_margin = Inches(0.5)
            sec.right_margin = Inches(0.5)
            sec.page_width = Inches(8.27)
            sec.page_height = Inches(11.69)

        for i, page in enumerate(doc):
            if i > 0:
                word_doc.add_page_break()

            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            img_stream = io.BytesIO(img_bytes)

            p = word_doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run()
            run.add_picture(img_stream, width=Inches(7.27))

        doc.close()
        word_doc.save(output_path)
        return output_path

    def _convert_with_layout_engine(self, input_path: str, output_path: str) -> str:
        """
        PyMuPDF va python-docx asosidagi geometrik joylashuv dvigateli.
        Jadval va matnlarni koordinatalari bo'yicha tartiblab, tartibi buzilmasdan
        aniq Word (.docx) fayliga o'tkazadi.
        """
        import fitz
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import parse_xml
        from docx.oxml.ns import nsdecls

        doc = fitz.open(input_path)
        word_doc = Document()

        for sec in word_doc.sections:
            sec.top_margin = Inches(0.7)
            sec.bottom_margin = Inches(0.7)
            sec.left_margin = Inches(0.7)
            sec.right_margin = Inches(0.7)

        for pno, page in enumerate(doc):
            if pno > 0:
                word_doc.add_page_break()

            page_rect = page.rect
            page_width = page_rect.width

            table_finder = page.find_tables()
            tables = table_finder.tables if table_finder else []
            if not tables:
                try:
                    alt_finder = page.find_tables(vertical_strategy="text", horizontal_strategy="lines")
                    if alt_finder and alt_finder.tables:
                        tables = alt_finder.tables
                except Exception:
                    pass
            table_bboxes = [t.bbox for t in tables]

            blocks = page.get_text('blocks')

            def is_inside_table(bbox):
                bx0, by0, bx1, by1 = bbox[:4]
                b_mid_x = (bx0 + bx1) / 2
                b_mid_y = (by0 + by1) / 2
                for tx0, ty0, tx1, ty1 in table_bboxes:
                    if (tx0 - 5) <= b_mid_x <= (tx1 + 5) and (ty0 - 5) <= b_mid_y <= (ty1 + 5):
                        return True
                return False

            elements = []
            for b in blocks:
                if b[6] == 0:  # Matn bloki
                    text = b[4].strip()
                    if text and not is_inside_table(b):
                        elements.append({
                            'type': 'text',
                            'y0': b[1],
                            'x0': b[0],
                            'x1': b[2],
                            'text': text,
                            'block': b
                        })

            for t in tables:
                elements.append({
                    'type': 'table',
                    'y0': t.bbox[1],
                    'x0': t.bbox[0],
                    'table': t
                })

            # Geometrik y o'qi bo'yicha saralash (yaqin balandliklarni guruhlash uchun 4pt grid)
            elements.sort(key=lambda e: (round(e['y0'] / 4) * 4, e['x0']))

            for el in elements:
                if el['type'] == 'text':
                    txt = el['text']
                    lines = [l.strip() for l in txt.split('\n') if l.strip()]
                    for line in lines:
                        p = word_doc.add_paragraph()
                        p.paragraph_format.space_after = Pt(2)
                        p.paragraph_format.space_before = Pt(0)
                        p.paragraph_format.line_spacing = 1.15

                        mid_x = (el['x0'] + el['x1']) / 2
                        if abs(mid_x - page_width / 2) < 40 and len(line) < 70:
                            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        elif el['x0'] > page_width * 0.45:
                            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                        else:
                            p.alignment = WD_ALIGN_PARAGRAPH.LEFT

                        run = p.add_run(line)
                        run.font.name = 'Times New Roman'
                        if len(line) < 90 and (line.isupper() or any(k in line.upper() for k in ['VAZIRLIGI', 'REJASI', 'TASDIQLAYMAN', 'MA\'LUMOTNOMA'])):
                            run.bold = True
                            run.font.size = Pt(11)
                        else:
                            run.font.size = Pt(10.5)

                elif el['type'] == 'table':
                    t_obj = el['table']
                    raw_data = t_obj.extract()
                    if not raw_data or len(raw_data) == 0:
                        continue

                    num_rows = len(raw_data)
                    num_cols = max(len(r) for r in raw_data)

                    w_table = word_doc.add_table(rows=num_rows, cols=num_cols)
                    w_table.style = 'Table Grid'
                    w_table.autofit = True

                    for r_idx, row in enumerate(raw_data):
                        for c_idx in range(num_cols):
                            cell_val = row[c_idx] if c_idx < len(row) and row[c_idx] is not None else ''
                            cell = w_table.cell(r_idx, c_idx)
                            cell.text = str(cell_val).strip()

                            for cp in cell.paragraphs:
                                cp.paragraph_format.space_after = Pt(2)
                                cp.paragraph_format.space_before = Pt(2)
                                cp.paragraph_format.line_spacing = 1.05
                                for crun in cp.runs:
                                    crun.font.name = 'Times New Roman'
                                    crun.font.size = Pt(9.5)
                                    if r_idx == 0:
                                        crun.bold = True

                            if r_idx == 0:
                                shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F1F5F9"/>')
                                cell._tc.get_or_add_tcPr().append(shading)

                    p_after = word_doc.add_paragraph()
                    p_after.paragraph_format.space_before = Pt(2)
                    p_after.paragraph_format.space_after = Pt(2)

        word_doc.save(output_path)
        doc.close()
        return output_path

    @staticmethod
    def _post_process_docx_layout(input_pdf: str, docx_path: str) -> None:
        """
        pdf2docx tomonidan hosil qilingan Word hujjatini asl PDF geometriyasi
        bilan solishtirib, matnlar joylashuvi (chap, markaz, o'ng) va jadvallar
        tartibini 100% to'g'rilab, professional ko'rinishga keltiradi.
        """
        import fitz
        from docx import Document
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.shared import Pt
        from docx.oxml import parse_xml
        from docx.oxml.ns import nsdecls

        try:
            pdf_doc = fitz.open(input_pdf)
            word_doc = Document(docx_path)

            all_blocks = []
            for page in pdf_doc:
                p_width = page.rect.width
                for b in page.get_text("blocks"):
                    if b[6] == 0:  # Matn bloki
                        txt = b[4].strip()
                        if txt:
                            x0, y0, x1, y1 = b[:4]
                            mid_x = (x0 + x1) / 2
                            block_w = x1 - x0
                            is_center = (abs(mid_x - (p_width / 2)) < 55) and (block_w < p_width * 0.85)
                            is_right = (x0 > p_width * 0.42) and not is_center
                            all_blocks.append({
                                "text": txt,
                                "clean": "".join(txt.split()).lower(),
                                "is_center": is_center,
                                "is_right": is_right,
                            })
            pdf_doc.close()

            empty_count = 0
            for p in list(word_doc.paragraphs):
                p_raw = p.text.strip()
                if not p_raw:
                    empty_count += 1
                    if empty_count > 1:
                        p_element = p._p
                        p_element.getparent().remove(p_element)
                    continue
                else:
                    empty_count = 0

                p_clean = "".join(p_raw.split()).lower()

                matched = None
                for b in all_blocks:
                    if b["clean"] in p_clean or p_clean in b["clean"]:
                        matched = b
                        break

                if matched:
                    if matched["is_center"]:
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    elif matched["is_right"]:
                        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

                upper_txt = p_raw.upper()
                if any(k in upper_txt for k in ["TASDIQLAYMAN"]):
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                elif any(k in upper_txt for k in ["REJASI", "JADVALI", "BUYRUG'I", "HISOBOTI", "BAYONNOMASI", "MA'LUMOTNOMA"]):
                    if len(p_raw) < 100:
                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER

            for tbl in word_doc.tables:
                tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
                tbl.autofit = True
                for row in tbl.rows:
                    trPr = row._tr.get_or_add_trPr()
                    if trPr.find(parse_xml(f'<w:cantSplit {nsdecls("w")}/>').tag) is None:
                        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
                    for cell in row.cells:
                        for cp in cell.paragraphs:
                            cp.paragraph_format.space_before = Pt(1)
                            cp.paragraph_format.space_after = Pt(1)
                            cp.paragraph_format.line_spacing = 1.05

            word_doc.save(docx_path)
            logger.info(f"DOCX joylashuvi muvaffaqiyatli optimallashtirildi: {docx_path}")
        except Exception as e:
            logger.warning(f"DOCX post-processing ogohlantirish: {e}")

    async def pdf_to_word(self, input_path: str, output_path: str) -> str:
        """
        PDF dan Word (.docx) formatiga yuqori aniqlikda o'tkazish.
        Matnlar va jadvallarning asl joylashuvini, tartibini va strukturasini
        buzilmasdan saqlaydi (stream-table noto'g'ri bo'linishini oldini oladi).
        """
        def _convert():
            import fitz
            import docx

            # 1. PDF ni oldindan tahlil qilish: sahifalar, matn hajmi
            is_scanned = False
            try:
                test_doc = fitz.open(input_path)
                total_text_len = 0
                has_images = False
                for p in test_doc:
                    total_text_len += len(p.get_text().strip())
                    if len(p.get_images()) > 0:
                        has_images = True
                test_doc.close()

                # Agar matn deyarli bo'lmasa va rasm bo'lsa - bu skaner qilingan PDF
                if total_text_len < 20 and has_images:
                    is_scanned = True
            except Exception as e:
                logger.warning(f"PDF tahlilida ogohlantirish: {e}")

            if is_scanned:
                logger.info(f"Skaner qilingan PDF aniqlandi ({input_path}). Tasvirlar orqali DOCX ga o'tkazilmoqda.")
                return self._convert_scanned_pdf(input_path, output_path)

            # 2. Asosiy konvertatsiya: to'liq imkoniyatli pdf2docx
            # parse_stream_table=True qilib o'rnatamiz, bu barcha jadvallar va ko'p ustunli matnlar
            # Word jadvali va oqimi sifatida 100% to'g'ri o'tishini ta'minlaydi.
            try:
                cv = Converter(input_path)
                cv.convert(
                    output_path,
                    start=0,
                    end=None,
                    parse_lattice_table=True,
                    parse_stream_table=True,
                    connected_border_tolerance=0.5,
                    line_separate_threshold=5.0,
                    max_line_spacing_ratio=1.5,
                    delete_end_line_hyphen=True,
                    ignore_page_error=True
                )
                cv.close()

                # Natijani tekshirish va geometrik layoutni to'g'rilash
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    docx.Document(output_path)
                    self._post_process_docx_layout(input_path, output_path)
                    return output_path
            except Exception as e:
                logger.warning(f"Asosiy pdf2docx da xatolik yuz berdi ({e}). Geometrik layout dvigateliga o'tilmoqda...")

            # 3. Zaxira usul: PyMuPDF + python-docx geometrik layout dvigateli
            try:
                return self._convert_with_layout_engine(input_path, output_path)
            except Exception as e2:
                logger.error(f"Layout dvigatelida ham xatolik: {e2}")
                raise Exception(f"PDF dan Word ga o'tkazib bo'lmadi: {e2}")

        try:
            return await asyncio.to_thread(_convert)
        except Exception as e:
            logger.error(f"Xato: PDF dan Word ga o'tkazishda xatolik - {e}")
            raise

    async def excel_to_word(self, input_path: str, output_path: str, orientation: str = 'auto', table_style: str = 'modern_blue') -> str:
        """Excel (.xlsx/.xls/.csv) jadvallarini Word (.docx) formatiga avto-orientatsiya va chiroyli jadval ko'rinishida o'tkazish."""
        from .excel_processor import ExcelProcessor
        ep = ExcelProcessor()
        res = await ep.convert_to_word_table(
            file_path=input_path,
            output_path=output_path,
            orientation_mode=orientation,
            table_style=table_style
        )
        return res.get("output_path", output_path)


    async def excel_to_csv(self, input_path: str, output_path: str) -> str:
        """Excel dan CSV formatiga o'tkazish."""
        def _convert():
            wb = load_workbook(input_path, data_only=True)
            sheet = wb.active
            
            with open(output_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for row in sheet.iter_rows(values_only=True):
                    writer.writerow(["" if cell is None else str(cell) for cell in row])
            return output_path
            
        try:
            return await asyncio.to_thread(_convert)
        except Exception as e:
            logger.error(f"Xato: Excel dan CSV ga o'tkazishda xatolik - {e}")
            raise

    async def csv_to_excel(self, input_path: str, output_path: str) -> str:
        """CSV dan Excel formatiga o'tkazish."""
        def _convert():
            wb = Workbook()
            sheet = wb.active
            
            with open(input_path, mode='r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    sheet.append(row)
                    
            wb.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_convert)
        except Exception as e:
            logger.error(f"Xato: CSV dan Excel ga o'tkazishda xatolik - {e}")
            raise

    async def convert_to_pdf(self, input_path: str, output_dir: str) -> str:
        """Auto-detect file type and convert to PDF."""
        ext = os.path.splitext(input_path)[1].lower()
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{base_name}.pdf")
        os.makedirs(output_dir, exist_ok=True)

        if ext in ('.docx', '.doc'):
            return await self.word_to_pdf(input_path, output_path)
        elif ext in ('.xlsx', '.xls'):
            return await self.excel_to_pdf(input_path, output_path)
        elif ext in ('.pptx', '.ppt'):
            return await self.pptx_to_pdf(input_path, output_path)
        else:
            raise ValueError(f"'{ext}' formatdan PDF ga konvertatsiya qo'llab-quvvatlanmaydi.")

