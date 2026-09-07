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
        """Ustunlar bo'yicha statistika hisoblash (barcha raqamli ustunlar yoki ko'rsatilgan ustun)."""
        def _stats():
            ext = os.path.splitext(file_path)[1].lower()
            data_rows = []
            
            if ext == '.csv':
                for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'latin-1'):
                    try:
                        with open(file_path, 'r', encoding=enc, errors='replace') as f:
                            r = csv.reader(f)
                            for row in r:
                                data_rows.append(row)
                        break
                    except Exception:
                        continue
            else:
                wb = load_workbook(file_path, data_only=True)
                sheet = wb.active
                for row in sheet.iter_rows(values_only=True):
                    data_rows.append(list(row))

            if not data_rows:
                return {}

            headers = [str(c or f"Ustun {i+1}") for i, c in enumerate(data_rows[0])]
            rows_data = data_rows[1:] if len(data_rows) > 1 else []

            columns_stats = {}

            if column is not None:
                target_indices = [column - 1]
            else:
                target_indices = list(range(len(headers)))

            for idx in target_indices:
                if idx < 0 or idx >= len(headers):
                    continue
                col_name = headers[idx]
                num_values = []
                for row in rows_data:
                    if idx < len(row):
                        val = row[idx]
                        if isinstance(val, (int, float)):
                            num_values.append(float(val))
                        elif isinstance(val, str):
                            val_str = val.strip().replace(',', '.')
                            try:
                                num_values.append(float(val_str))
                            except ValueError:
                                pass
                
                if num_values:
                    columns_stats[col_name] = {
                        "Eng kichik (min)": min(num_values),
                        "Eng katta (max)": max(num_values),
                        "O'rtacha (avg)": round(sum(num_values) / len(num_values), 2),
                        "Jami yig'indi (sum)": round(sum(num_values), 2),
                        "Raqamlar soni": len(num_values)
                    }

            if not columns_stats and column is not None:
                return {"min": 0, "max": 0, "avg": 0, "count": 0}

            return columns_stats

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
