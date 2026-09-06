import asyncio
import os
import logging
from pptx import Presentation

from .base import BaseProcessor, FileMetadata

logger = logging.getLogger(__name__)

class PptxProcessor(BaseProcessor):
    """
    PowerPoint (PPTX) hujjatlarini qayta ishlash uchun sinf.
    """
    SUPPORTED_EXTENSIONS = ['.pptx', '.ppt']

    async def extract_text(self, file_path: str) -> str:
        """Slaydlardan barcha matnni ajratib olish."""
        def _extract():
            prs = Presentation(file_path)
            text = []
            for i, slide in enumerate(prs.slides):
                text.append(f"--- Slayd {i+1} ---")
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        text.append(shape.text.strip())
            return "\n".join(text)
            
        try:
            return await asyncio.to_thread(_extract)
        except Exception as e:
            logger.error(f"Xato: Slaydlardan matnni ajratishda xatolik - {e}")
            raise

    async def get_metadata(self, file_path: str) -> FileMetadata:
        """PowerPoint hujjati metama'lumotlarini olish."""
        def _get_meta():
            prs = Presentation(file_path)
            size = os.path.getsize(file_path)
            
            slide_count = len(prs.slides)
            has_images = False
            has_tables = False
            word_count = 0
            
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.shape_type == 13: # msoPICTURE
                        has_images = True
                    if shape.has_table:
                        has_tables = True
                    if hasattr(shape, "text"):
                        word_count += len(shape.text.split())
                        
            return FileMetadata(
                file_name=os.path.basename(file_path),
                file_type="PowerPoint Presentation",
                file_size=size,
                page_count=slide_count,
                word_count=word_count,
                has_images=has_images,
                has_tables=has_tables
            )
            
        try:
            return await asyncio.to_thread(_get_meta)
        except Exception as e:
            logger.error(f"Xato: PowerPoint metama'lumotlarini olishda xatolik - {e}")
            raise

    async def create_presentation(self, slides_data: list[dict], output_path: str, title: str = None) -> str:
        """Ma'lumotlardan yangi taqdimot yaratish."""
        def _create():
            prs = Presentation()
            
            if title:
                title_slide_layout = prs.slide_layouts[0]
                slide = prs.slides.add_slide(title_slide_layout)
                slide.shapes.title.text = title
                if slide.placeholders and len(slide.placeholders) > 1:
                    slide.placeholders[1].text = "Avtomatik yaratilgan"
            
            for slide_data in slides_data:
                layout_type = slide_data.get('layout', 'title_content')
                
                if layout_type == 'title':
                    layout = prs.slide_layouts[0]
                elif layout_type == 'content':
                    layout = prs.slide_layouts[6] # blank or text only
                else:
                    layout = prs.slide_layouts[1] # title and content
                    
                slide = prs.slides.add_slide(layout)
                
                if 'title' in slide_data and hasattr(slide.shapes, "title") and slide.shapes.title:
                    slide.shapes.title.text = slide_data['title']
                    
                if 'content' in slide_data and len(slide.placeholders) > 1:
                    body = slide.placeholders[1]
                    body.text = slide_data['content']
                    
            prs.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_create)
        except Exception as e:
            logger.error(f"Xato: Taqdimot yaratishda xatolik - {e}")
            raise

    async def extract_slide_texts(self, file_path: str) -> list[dict]:
        """Har bir slayd matnini alohida olish."""
        def _extract_slide():
            prs = Presentation(file_path)
            slides = []
            for i, slide in enumerate(prs.slides):
                slide_text = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_text.append(shape.text.strip())
                slides.append({
                    "slide_number": i + 1,
                    "text": "\n".join(slide_text)
                })
            return slides
            
        try:
            return await asyncio.to_thread(_extract_slide)
        except Exception as e:
            logger.error(f"Xato: Slayd matnlarini olishda xatolik - {e}")
            raise

    async def add_slide(self, file_path: str, title: str, content: str, output_path: str) -> str:
        """Mavjud taqdimotga yangi slayd qo'shish."""
        def _add():
            prs = Presentation(file_path)
            
            slide_layout = prs.slide_layouts[1] # title and content
            slide = prs.slides.add_slide(slide_layout)
            
            if hasattr(slide.shapes, "title") and slide.shapes.title:
                slide.shapes.title.text = title
                
            if len(slide.placeholders) > 1:
                slide.placeholders[1].text = content
                
            prs.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_add)
        except Exception as e:
            logger.error(f"Xato: Slayd qo'shishda xatolik - {e}")
            raise
