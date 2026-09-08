import asyncio
import os
import io
import logging
import zipfile
import pymupdf as fitz
from PIL import Image
from typing import Any
import pdfplumber
from pypdf import PdfReader, PdfWriter
from fpdf import FPDF

from .base import BaseProcessor, FileMetadata

logger = logging.getLogger(__name__)

class PDFProcessor(BaseProcessor):
    """
    PDF hujjatlarni qayta ishlash uchun sinf.
    """
    SUPPORTED_EXTENSIONS = ['.pdf']

    async def extract_text(self, file_path: str) -> str:
        """PDF dan matnni ajratib olish."""
        def _extract():
            text = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text.append(page_text)
            return "\n\n".join(text)
        
        try:
            return await asyncio.to_thread(_extract)
        except Exception as e:
            logger.error(f"Xato: PDF dan matnni ajratishda xatolik - {e}")
            raise

    async def get_metadata(self, file_path: str) -> FileMetadata:
        """PDF metama'lumotlarini olish."""
        def _get_meta():
            size = os.path.getsize(file_path)
            with pdfplumber.open(file_path) as pdf:
                page_count = len(pdf.pages)
                has_images = any(len(page.images) > 0 for page in pdf.pages)
                has_tables = any(len(page.find_tables()) > 0 for page in pdf.pages)
                
                # Matnni olib, so'zlar sonini hisoblash
                full_text = ""
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + " "
                word_count = len(full_text.split())
                
                return FileMetadata(
                    file_name=os.path.basename(file_path),
                    file_type="PDF",
                    file_size=size,
                    page_count=page_count,
                    word_count=word_count,
                    has_images=has_images,
                    has_tables=has_tables
                )
        
        try:
            return await asyncio.to_thread(_get_meta)
        except Exception as e:
            logger.error(f"Xato: PDF metama'lumotlarini olishda xatolik - {e}")
            raise

    async def extract_tables(self, file_path: str) -> list[list[list[str]]]:
        """PDF dan jadvallarni ajratib olish."""
        def _extract_tables():
            tables_data = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        tables_data.append(table)
            return tables_data
            
        try:
            return await asyncio.to_thread(_extract_tables)
        except Exception as e:
            logger.error(f"Xato: PDF dan jadval ajratishda xatolik - {e}")
            raise

    async def split_pdf(self, file_path: str, start_page: int, end_page: int, output_path: str) -> str:
        """PDF sahifalarini ajratib olish."""
        def _split():
            reader = PdfReader(file_path)
            writer = PdfWriter()
            
            # Note: start_page and end_page are expected to be 1-indexed by users usually.
            # Assuming 0-indexed internally:
            for i in range(start_page, min(end_page + 1, len(reader.pages))):
                writer.add_page(reader.pages[i])
                
            with open(output_path, "wb") as f:
                writer.write(f)
            return output_path
            
        try:
            return await asyncio.to_thread(_split)
        except Exception as e:
            logger.error(f"Xato: PDF ni bo'lishda xatolik - {e}")
            raise

    async def compress_pdf(self, file_path: str, output_path: str, quality_level: str = "medium") -> dict:
        """
        PDF hajmini siqish (50-80% gacha).
        quality_level:
          - 'low': maksimal siqish (70-85% gacha kichraytirish)
          - 'medium': muvozanatli (50-70% gacha kichraytirish, tavsiya etiladi)
          - 'high': sifatni saqlagan holda yengil siqish
        """
        def _compress():
            initial_size = os.path.getsize(file_path)
            doc = fitz.open(file_path)

            max_dim = 1000 if quality_level == "low" else (1400 if quality_level == "medium" else 1800)
            jpeg_quality = 50 if quality_level == "low" else (68 if quality_level == "medium" else 82)

            for xref in range(1, doc.xref_length()):
                if doc.xref_is_image(xref):
                    try:
                        base_image = doc.extract_image(xref)
                        if not base_image:
                            continue
                        img_bytes = base_image.get("image")
                        if not img_bytes:
                            continue

                        pil_img = Image.open(io.BytesIO(img_bytes))
                        w, h = pil_img.size
                        if w > max_dim or h > max_dim:
                            pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                        if pil_img.mode in ("RGBA", "P"):
                            pil_img = pil_img.convert("RGB")

                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
                        new_data = buf.getvalue()

                        if len(new_data) < len(img_bytes):
                            doc.update_stream(xref, new_data)
                    except Exception:
                        pass

            doc.save(output_path, garbage=4, deflate=True, clean=True)
            doc.close()

            final_size = os.path.getsize(output_path)
            saved_percent = round((1 - (final_size / max(initial_size, 1))) * 100, 1)
            return {
                "initial_size": initial_size,
                "final_size": final_size,
                "saved_percent": max(0.0, saved_percent)
            }

        try:
            return await asyncio.to_thread(_compress)
        except Exception as e:
            logger.error(f"PDF siqishda xatolik: {e}")
            raise

    async def watermark_pdf(
        self,
        file_path: str,
        output_path: str,
        mode: str = "text",
        text: str = "EduBot",
        font_size: int = 24,
        opacity: float = 0.35,
        angle: int = 45,
        color_hex: str = "#6366f1",
        logo_path: str = None,
        repeat: bool = True
    ) -> str:
        """
        PDF sahifalariga matn yoki rasm (logo) shaklida suv belgisi (watermark) qo'yish.
        - Matn: sahifa bo'ylab 10-15 ta takroriy diagonal belgi yoki bitta markaziy belgi.
        - Rasm (Logo): proporsiyasi buzilmasdan, shaffoflik va burchak saqlangan holda markazda joylashadi.
        """
        def _watermark():
            doc = fitz.open(file_path)

            # Hex to RGB 0.0-1.0
            clean_hex = color_hex.lstrip("#")
            if len(clean_hex) == 6:
                r = int(clean_hex[0:2], 16) / 255.0
                g = int(clean_hex[2:4], 16) / 255.0
                b = int(clean_hex[4:6], 16) / 255.0
                color_tuple = (r, g, b)
            else:
                color_tuple = (0.4, 0.4, 0.9)

            clamped_opacity = max(0.05, min(1.0, opacity))

            # Agar rasm bo'lsa, uni bir marta yuklab, shaffoflik va burchakni qayta ishlaymiz
            prepared_img_bytes = None
            orig_img_w = 0
            orig_img_h = 0
            if mode == "image" and logo_path and os.path.exists(logo_path):
                try:
                    pil_img = Image.open(logo_path).convert("RGBA")
                    # Shaffoflikni (alpha kanalini) moslash
                    r_ch, g_ch, b_ch, a_ch = pil_img.split()
                    a_ch = a_ch.point(lambda p: int(p * clamped_opacity))
                    pil_img = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))

                    # Agar burchak berilgan bo'lsa aylantirish
                    if angle != 0:
                        pil_img = pil_img.rotate(angle, expand=True, resample=Image.Resampling.BICUBIC)

                    orig_img_w, orig_img_h = pil_img.size
                    buf = io.BytesIO()
                    pil_img.save(buf, format="PNG")
                    prepared_img_bytes = buf.getvalue()
                except Exception as img_err:
                    logger.error(f"Suv belgisi rasmini qayta ishlashda xatolik: {img_err}")
                    prepared_img_bytes = None

            for page in doc:
                rect = page.rect
                cx = rect.width / 2
                cy = rect.height / 2

                if mode == "image" and prepared_img_bytes:
                    # Proporsiyasini saqlagan holda sahifaga moslashtirish (squash/buzilishsiz)
                    max_w = min(rect.width * 0.65, 420)
                    max_h = min(rect.height * 0.65, 420)
                    scale = min(max_w / orig_img_w, max_h / orig_img_h, 1.0)
                    w = orig_img_w * scale
                    h = orig_img_h * scale

                    img_rect = fitz.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
                    page.insert_image(img_rect, stream=prepared_img_bytes, overlay=True)

                else:
                    # Text Watermark
                    if repeat:
                        # Sahifa bo'ylab 10–15 ta takroriy panjara (grid) ko'rinishida
                        num_cols = 3 if rect.height >= rect.width else 5
                        num_rows = 5 if rect.height >= rect.width else 3
                        # 3 ustun x 5 qator = 15 ta suv belgisi
                        cell_w = rect.width / num_cols
                        cell_h = rect.height / num_rows

                        for r_idx in range(num_rows):
                            # Qatorlar orasidagi siljish (staggered diagonal ko'rinish uchun)
                            offset = (cell_w * 0.25) if (r_idx % 2 == 1) else (-cell_w * 0.25)
                            for c_idx in range(num_cols):
                                x = (c_idx + 0.5) * cell_w + offset
                                y = (r_idx + 0.5) * cell_h
                                pt = fitz.Point(x - (len(text) * font_size * 0.22), y)
                                page.insert_text(
                                    pt,
                                    text,
                                    fontsize=font_size,
                                    color=color_tuple,
                                    fill_opacity=clamped_opacity,
                                    morph=(fitz.Point(x, y), fitz.Matrix(angle)) if angle != 0 else None,
                                    overlay=True
                                )
                    else:
                        # Bitta markazda joylashgan suv belgisi
                        center_point = fitz.Point(cx - (len(text) * font_size * 0.22), cy)
                        page.insert_text(
                            center_point,
                            text,
                            fontsize=font_size,
                            color=color_tuple,
                            fill_opacity=clamped_opacity,
                            morph=(fitz.Point(cx, cy), fitz.Matrix(angle)) if angle != 0 else None,
                            overlay=True
                        )

            doc.save(output_path, garbage=3, deflate=True)
            doc.close()
            return output_path

        try:
            return await asyncio.to_thread(_watermark)
        except Exception as e:
            logger.error(f"PDF ga suv belgisi qo'yishda xatolik: {e}")
            raise

    async def merge_pdfs(self, file_paths: list[str], output_path: str) -> str:
        """Bir nechta PDF fayllarni bitta tartibli PDF hujjatga birlashtirish (PyMuPDF)."""
        def _merge():
            merged_doc = fitz.open()
            for path in file_paths:
                if os.path.exists(path):
                    doc = fitz.open(path)
                    merged_doc.insert_pdf(doc)
                    doc.close()
            merged_doc.save(output_path, garbage=3, deflate=True)
            merged_doc.close()
            return output_path

        try:
            return await asyncio.to_thread(_merge)
        except Exception as e:
            logger.error(f"PDF larni birlashtirishda xatolik: {e}")
            raise

    async def split_pdf_advanced(
        self,
        file_path: str,
        output_dir: str,
        split_mode: str = "range",
        page_range_str: str = "1"
    ) -> dict:
        """
        PDF sahifalarini bo'lish / ajratib olish.
        split_mode:
          - 'range': kiritilgan sahifalar oralig'i (masalan: '1-3' yoki '1,3,5') bitta yangi PDF bo'ladi
          - 'all': har bir sahifa alohida PDF qilinib, bitta ZIP arxivga yig'iladi
        """
        def _split():
            doc = fitz.open(file_path)
            total_pages = len(doc)
            base_name = os.path.splitext(os.path.basename(file_path))[0]

            if split_mode == "all":
                # Split all pages into separate PDFs and package into ZIP
                zip_filename = f"{base_name}_ajratilgan_sahifalar.zip"
                zip_path = os.path.join(output_dir, zip_filename)
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for i in range(total_pages):
                        single_doc = fitz.open()
                        single_doc.insert_pdf(doc, from_page=i, to_page=i)
                        single_name = f"{base_name}_sahifa_{i + 1}.pdf"
                        single_path = os.path.join(output_dir, single_name)
                        single_doc.save(single_path)
                        single_doc.close()
                        zip_file.write(single_path, arcname=single_name)
                        try:
                            os.remove(single_path)
                        except Exception:
                            pass
                doc.close()
                return {
                    "is_zip": True,
                    "file_path": zip_path,
                    "file_name": zip_filename,
                    "total_pages": total_pages,
                    "extracted_count": total_pages
                }

            # Parse page range (e.g., '1-3', '2,4,6', '1-2, 5')
            pages_to_extract = set()
            parts = [p.strip() for p in page_range_str.split(",") if p.strip()]
            for part in parts:
                if "-" in part:
                    r_parts = part.split("-")
                    try:
                        s = int(r_parts[0].strip())
                        e = int(r_parts[1].strip())
                        for p_idx in range(max(1, s), min(total_pages, e) + 1):
                            pages_to_extract.add(p_idx - 1)
                    except ValueError:
                        pass
                else:
                    try:
                        p_idx = int(part)
                        if 1 <= p_idx <= total_pages:
                            pages_to_extract.add(p_idx - 1)
                    except ValueError:
                        pass

            if not pages_to_extract:
                pages_to_extract = {0}

            sorted_pages = sorted(list(pages_to_extract))
            new_doc = fitz.open()
            for p_idx in sorted_pages:
                new_doc.insert_pdf(doc, from_page=p_idx, to_page=p_idx)

            clean_range = "_".join(parts) or "ajratilgan"
            clean_range = "".join(c for c in clean_range if c.isalnum() or c in ("-", "_"))[:20]
            out_name = f"{base_name}_sahifalar_{clean_range}.pdf"
            out_path = os.path.join(output_dir, out_name)
            new_doc.save(out_path, garbage=3, deflate=True)
            new_doc.close()
            doc.close()

            return {
                "is_zip": False,
                "file_path": out_path,
                "file_name": out_name,
                "total_pages": total_pages,
                "extracted_count": len(sorted_pages)
            }

        try:
            return await asyncio.to_thread(_split)
        except Exception as e:
            logger.error(f"PDF ni bo'lishda xatolik: {e}")
            raise

    async def create_pdf_from_text(self, text: str, output_path: str, title: str = None) -> str:
        """Matndan yangi PDF yaratish."""
        def _create():
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            # Default font for FPDF does not support full UTF-8 typically, using standard Arial/Helvetica
            pdf.set_font("Arial", size=12)
            
            if title:
                pdf.set_font("Arial", style='B', size=16)
                pdf.cell(200, 10, txt=title, ln=True, align='C')
                pdf.ln(10)
                
            pdf.set_font("Arial", size=12)
            # Handle unicode strings via standard output or multi_cell
            pdf.multi_cell(0, 10, txt=text.encode('latin-1', 'replace').decode('latin-1'))
            pdf.output(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_create)
        except Exception as e:
            logger.error(f"Xato: PDF yaratishda xatolik - {e}")
            raise

    async def protect_pdf(self, file_path: str, password: str, output_path: str) -> str:
        """PDF ga parol o'rnatish."""
        def _protect():
            reader = PdfReader(file_path)
            writer = PdfWriter()
            
            for page in reader.pages:
                writer.add_page(page)
                
            writer.encrypt(password)
            with open(output_path, "wb") as f:
                writer.write(f)
            return output_path
            
        try:
            return await asyncio.to_thread(_protect)
        except Exception as e:
            logger.error(f"Xato: PDF parolini o'rnatishda xatolik - {e}")
            raise
