import asyncio
import os
import logging
from docx import Document

from .base import BaseProcessor, FileMetadata

logger = logging.getLogger(__name__)

class WordProcessor(BaseProcessor):
    """
    Word hujjatlarni qayta ishlash uchun sinf.
    """
    SUPPORTED_EXTENSIONS = ['.docx', '.doc']

    async def extract_text(self, file_path: str) -> str:
        """Word hujjatidan matnni ajratib olish."""
        def _extract():
            doc = Document(file_path)
            text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    text.append(para.text)
            
            for table in doc.tables:
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        if cell.text.strip():
                            row_data.append(cell.text.strip())
                    if row_data:
                        text.append(" | ".join(row_data))
                        
            return "\n".join(text)
            
        try:
            return await asyncio.to_thread(_extract)
        except Exception as e:
            logger.error(f"Xato: Word hujjatidan matnni ajratishda xatolik - {e}")
            raise

    async def get_metadata(self, file_path: str) -> FileMetadata:
        """Word hujjati metama'lumotlarini olish."""
        def _get_meta():
            doc = Document(file_path)
            size = os.path.getsize(file_path)
            
            para_count = len(doc.paragraphs)
            has_tables = len(doc.tables) > 0
            has_images = len(doc.inline_shapes) > 0
            
            full_text = " ".join([p.text for p in doc.paragraphs])
            word_count = len(full_text.split())
            
            return FileMetadata(
                file_name=os.path.basename(file_path),
                file_type="Word Document",
                file_size=size,
                page_count=None,
                word_count=word_count,
                has_images=has_images,
                has_tables=has_tables
            )
            
        try:
            return await asyncio.to_thread(_get_meta)
        except Exception as e:
            logger.error(f"Xato: Word metama'lumotlarini olishda xatolik - {e}")
            raise

    async def extract_tables(self, file_path: str) -> list[list[list[str]]]:
        """Word hujjatidan jadvallarni ajratib olish."""
        def _extract_tables():
            doc = Document(file_path)
            tables_data = []
            for table in doc.tables:
                table_data = []
                for row in table.rows:
                    row_data = [cell.text.strip() for cell in row.cells]
                    table_data.append(row_data)
                if table_data:
                    tables_data.append(table_data)
            return tables_data
            
        try:
            return await asyncio.to_thread(_extract_tables)
        except Exception as e:
            logger.error(f"Xato: Word dan jadval ajratishda xatolik - {e}")
            raise

    async def create_document(self, text: str, output_path: str, title: str = None) -> str:
        """Matndan yangi Word hujjati yaratish."""
        def _create():
            doc = Document()
            if title:
                doc.add_heading(title, 0)
            
            for para in text.split('\n'):
                if para.strip():
                    doc.add_paragraph(para)
                    
            doc.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_create)
        except Exception as e:
            logger.error(f"Xato: Word hujjati yaratishda xatolik - {e}")
            raise

    async def find_and_replace(self, file_path: str, replacements: dict[str, str], output_path: str) -> str:
        """Matnni topish va almashtirish."""
        def _replace():
            doc = Document(file_path)
            for para in doc.paragraphs:
                for old_text, new_text in replacements.items():
                    if old_text in para.text:
                        # Inline runs are used to preserve formatting
                        for run in para.runs:
                            if old_text in run.text:
                                run.text = run.text.replace(old_text, new_text)
            
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            for old_text, new_text in replacements.items():
                                if old_text in p.text:
                                    for run in p.runs:
                                        if old_text in run.text:
                                            run.text = run.text.replace(old_text, new_text)
                                            
            doc.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_replace)
        except Exception as e:
            logger.error(f"Xato: Word hujjatida matn almashtirishda xatolik - {e}")
            raise

    async def create_from_template(self, template_path: str, context: dict, output_path: str) -> str:
        """Shablondan yangi Word hujjati yaratish."""
        def _template():
            doc = Document(template_path)
            
            for para in doc.paragraphs:
                for key, value in context.items():
                    placeholder = f"{{{{{key}}}}}"
                    if placeholder in para.text:
                        for run in para.runs:
                            if placeholder in run.text:
                                run.text = run.text.replace(placeholder, str(value))
                                
            for table in doc.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            for key, value in context.items():
                                placeholder = f"{{{{{key}}}}}"
                                if placeholder in p.text:
                                    for run in p.runs:
                                        if placeholder in run.text:
                                            run.text = run.text.replace(placeholder, str(value))
                                            
            doc.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_template)
        except Exception as e:
            logger.error(f"Xato: Shablondan Word hujjati yaratishda xatolik - {e}")
            raise
