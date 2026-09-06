import asyncio
import os
import logging
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

    async def merge_pdfs(self, file_paths: list[str], output_path: str) -> str:
        """Bir nechta PDF larni birlashtirish."""
        def _merge():
            writer = PdfWriter()
            for path in file_paths:
                reader = PdfReader(path)
                for page in reader.pages:
                    writer.add_page(page)
            with open(output_path, "wb") as f:
                writer.write(f)
            return output_path
            
        try:
            return await asyncio.to_thread(_merge)
        except Exception as e:
            logger.error(f"Xato: PDF larni birlashtirishda xatolik - {e}")
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
