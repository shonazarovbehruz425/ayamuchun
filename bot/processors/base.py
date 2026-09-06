import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class FileMetadata:
    file_name: str
    file_type: str
    file_size: int
    page_count: int | None = None
    word_count: int | None = None
    has_images: bool = False
    has_tables: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

class BaseProcessor(ABC):
    """
    Hujjatlarni qayta ishlash uchun asosiy abstrakt sinf.
    """
    SUPPORTED_EXTENSIONS: list[str] = []
    
    @abstractmethod
    async def extract_text(self, file_path: str) -> str:
        """
        Hujjatdan matnni ajratib olish.
        """
        pass
    
    @abstractmethod
    async def get_metadata(self, file_path: str) -> FileMetadata:
        """
        Hujjat metama'lumotlarini olish.
        """
        pass
    
    def can_process(self, file_path: str) -> bool:
        """
        Ushbu faylni qayta ishlash mumkinligini tekshirish.
        """
        _, ext = os.path.splitext(file_path)
        return ext.lower() in self.SUPPORTED_EXTENSIONS

def get_processor(file_path: str) -> BaseProcessor:
    """
    Fayl kengaytmasiga qarab tegishli protsessorni qaytaradi.
    """
    from .pdf_processor import PDFProcessor
    from .word_processor import WordProcessor
    from .excel_processor import ExcelProcessor
    from .pptx_processor import PptxProcessor
    
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    if ext in PDFProcessor.SUPPORTED_EXTENSIONS:
        return PDFProcessor()
    elif ext in WordProcessor.SUPPORTED_EXTENSIONS:
        return WordProcessor()
    elif ext in ExcelProcessor.SUPPORTED_EXTENSIONS:
        return ExcelProcessor()
    elif ext in PptxProcessor.SUPPORTED_EXTENSIONS:
        return PptxProcessor()
    else:
        raise ValueError(f"Fayl formati qo'llab-quvvatlanmaydi: {ext}")
