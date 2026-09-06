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
        """Word dan PDF formatiga o'tkazish."""
        output_dir = os.path.dirname(output_path) or '.'
        result_path = await self._convert_with_libreoffice(input_path, output_dir, 'pdf')
        if result_path != output_path:
            os.rename(result_path, output_path)
        return output_path

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

    async def pdf_to_word(self, input_path: str, output_path: str) -> str:
        """PDF dan Word formatiga o'tkazish."""
        def _convert():
            cv = Converter(input_path)
            cv.convert(output_path, start=0, end=None)
            cv.close()
            return output_path
            
        try:
            return await asyncio.to_thread(_convert)
        except Exception as e:
            logger.error(f"Xato: PDF dan Word ga o'tkazishda xatolik - {e}")
            raise

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

