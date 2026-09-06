import asyncio
import os
import csv
import logging
from openpyxl import load_workbook, Workbook

from .base import BaseProcessor, FileMetadata

logger = logging.getLogger(__name__)

class ExcelProcessor(BaseProcessor):
    """
    Excel hujjatlarni qayta ishlash uchun sinf.
    """
    SUPPORTED_EXTENSIONS = ['.xlsx', '.xls', '.xlsm']

    async def extract_text(self, file_path: str) -> str:
        """Excel dan matnni ajratib olish (barcha hujayralardan)."""
        def _extract():
            wb = load_workbook(file_path, data_only=True)
            text = []
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                text.append(f"--- Sheet: {sheet_name} ---")
                for row in sheet.iter_rows(values_only=True):
                    row_data = [str(cell) for cell in row if cell is not None]
                    if row_data:
                        text.append("\t".join(row_data))
            return "\n".join(text)
            
        try:
            return await asyncio.to_thread(_extract)
        except Exception as e:
            logger.error(f"Xato: Excel dan matnni ajratishda xatolik - {e}")
            raise

    async def get_metadata(self, file_path: str) -> FileMetadata:
        """Excel metama'lumotlarini olish."""
        def _get_meta():
            wb = load_workbook(file_path, read_only=True)
            size = os.path.getsize(file_path)
            
            sheet_count = len(wb.sheetnames)
            
            # Faqat faol varaq qatorlari hisobi yoki hamma
            active_sheet = wb.active
            row_count = active_sheet.max_row
            col_count = active_sheet.max_column
            
            return FileMetadata(
                file_name=os.path.basename(file_path),
                file_type="Excel Spreadsheet",
                file_size=size,
                page_count=sheet_count,  # Varoqlar sonini page_count da ko'rsatamiz
                has_tables=True,
                extra={"row_count": row_count, "column_count": col_count}
            )
            
        try:
            return await asyncio.to_thread(_get_meta)
        except Exception as e:
            logger.error(f"Xato: Excel metama'lumotlarini olishda xatolik - {e}")
            raise

    async def read_data(self, file_path: str, sheet_name: str = None) -> list[list]:
        """Excel hujjatidan ma'lumotlarni o'qish."""
        def _read():
            wb = load_workbook(file_path, data_only=True)
            sheet = wb[sheet_name] if sheet_name and sheet_name in wb.sheetnames else wb.active
            
            data = []
            for row in sheet.iter_rows(values_only=True):
                data.append(list(row))
            return data
            
        try:
            return await asyncio.to_thread(_read)
        except Exception as e:
            logger.error(f"Xato: Excel ma'lumotlarini o'qishda xatolik - {e}")
            raise

    async def create_spreadsheet(self, data: list[list], output_path: str, headers: list[str] = None, sheet_name: str = 'Sheet1') -> str:
        """Yangi Excel hujjatini yaratish."""
        def _create():
            wb = Workbook()
            sheet = wb.active
            sheet.title = sheet_name
            
            start_row = 1
            if headers:
                sheet.append(headers)
                start_row = 2
                
            for row in data:
                sheet.append(row)
                
            wb.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_create)
        except Exception as e:
            logger.error(f"Xato: Excel hujjati yaratishda xatolik - {e}")
            raise

    async def calculate_stats(self, file_path: str, column: int = None) -> dict:
        """Ustun bo'yicha statistika hisoblash."""
        def _stats():
            wb = load_workbook(file_path, data_only=True)
            sheet = wb.active
            
            # Agar ustun ko'rsatilmagan bo'lsa, 1-ustunni olamiz (1-indexed)
            col_idx = column if column else 1
            values = []
            
            for row in sheet.iter_rows(min_col=col_idx, max_col=col_idx, min_row=2, values_only=True):
                val = row[0]
                if isinstance(val, (int, float)):
                    values.append(val)
                    
            if not values:
                return {"min": 0, "max": 0, "avg": 0, "count": 0}
                
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "count": len(values)
            }
            
        try:
            return await asyncio.to_thread(_stats)
        except Exception as e:
            logger.error(f"Xato: Statistika hisoblashda xatolik - {e}")
            raise

    async def create_grade_table(self, students: list[str], subjects: list[str], output_path: str) -> str:
        """Baholash uchun shablon yaratish."""
        def _create_grade():
            wb = Workbook()
            sheet = wb.active
            sheet.title = "Baholar"
            
            headers = ["O'quvchi"] + subjects
            sheet.append(headers)
            
            for student in students:
                row = [student] + [""] * len(subjects)
                sheet.append(row)
                
            wb.save(output_path)
            return output_path
            
        try:
            return await asyncio.to_thread(_create_grade)
        except Exception as e:
            logger.error(f"Xato: Baholar jadvalini yaratishda xatolik - {e}")
            raise

    async def to_csv(self, file_path: str, output_path: str) -> str:
        """Excel dan CSV formatiga o'tkazish."""
        def _convert():
            wb = load_workbook(file_path, data_only=True)
            sheet = wb.active
            
            with open(output_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for row in sheet.iter_rows(values_only=True):
                    writer.writerow(["" if cell is None else str(cell) for cell in row])
            return output_path
            
        try:
            return await asyncio.to_thread(_convert)
        except Exception as e:
            logger.error(f"Xato: CSV formatiga o'tkazishda xatolik - {e}")
            raise
