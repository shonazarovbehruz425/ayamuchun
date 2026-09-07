import os
import csv
import asyncio
import logging
from .base import BaseProcessor, FileMetadata

logger = logging.getLogger(__name__)

class CSVProcessor(BaseProcessor):
    SUPPORTED_EXTENSIONS = ['.csv']

    async def extract_text(self, file_path: str) -> str:
        def _extract():
            lines = []
            for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'latin-1'):
                try:
                    with open(file_path, 'r', encoding=enc, errors='replace') as f:
                        reader = csv.reader(f)
                        for row in reader:
                            if any(cell.strip() for cell in row):
                                lines.append("\t".join(row))
                    break
                except Exception:
                    continue
            return "\n".join(lines)

        try:
            return await asyncio.to_thread(_extract)
        except Exception as e:
            logger.error(f"Xato: CSV matnini ajratishda xatolik - {e}")
            raise

    async def get_metadata(self, file_path: str) -> FileMetadata:
        def _get_meta():
            size = os.path.getsize(file_path)
            row_count = 0
            col_count = 0
            for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'latin-1'):
                try:
                    with open(file_path, 'r', encoding=enc, errors='replace') as f:
                        reader = csv.reader(f)
                        for row in reader:
                            row_count += 1
                            if len(row) > col_count:
                                col_count = len(row)
                    break
                except Exception:
                    continue

            return FileMetadata(
                file_name=os.path.basename(file_path),
                file_type="CSV Document",
                file_size=size,
                page_count=1,
                has_tables=True,
                extra={"row_count": row_count, "column_count": col_count}
            )

        try:
            return await asyncio.to_thread(_get_meta)
        except Exception as e:
            logger.error(f"Xato: CSV metama'lumotlarini olishda xatolik - {e}")
            raise
