import os
import json
import logging
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse as FastFileResponse
from datetime import datetime

from .auth import get_current_user
from ..schemas.responses import FileResponse
from bot.database.engine import get_session
from bot.database import crud
from bot.database.models import File as DBFile
from bot.config import get_settings
from bot.processors import get_processor
from bot.processors.converter import FileConverter
from bot.utils.helpers import sanitize_filename, generate_unique_filename

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
converter = FileConverter()

@router.get("", response_model=List[FileResponse])
async def list_files(user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        return [
            FileResponse(
                id=f.id,
                file_name=f.file_name,
                file_type=f.file_type,
                file_size=f.file_size,
                uploaded_at=f.uploaded_at
            ) for f in files
        ]

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    try:
        user_id_str = str(user["telegram_id"])
        user_dir = os.path.join(settings.upload_dir, user_id_str)
        os.makedirs(user_dir, exist_ok=True)
        
        safe_name = generate_unique_filename(file.filename)
        dest_path = os.path.join(user_dir, safe_name)
        
        content = await file.read()
        file_size = len(content)
        with open(dest_path, "wb") as f:
            f.write(content)
            
        ext = os.path.splitext(file.filename)[1].lower().lstrip(".")
        
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
            record = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=file.filename,
                file_type=ext,
                telegram_file_id="",
                local_path=dest_path,
                file_size=file_size
            )
            await crud.log_usage(session, db_user.id, "upload_web", f"Uploaded {file.filename}")
            
            return {
                "message": "Fayl muvaffaqiyatli yuklandi",
                "file_id": record.id,
                "file_name": record.file_name,
                "file_size": file_size
            }
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{file_id}/convert")
async def convert_file(
    file_id: int,
    format: str = "pdf",
    user: dict = Depends(get_current_user)
):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
            
        try:
            if format.lower() == "pdf":
                out_path = await converter.convert_to_pdf(target.local_path, settings.processed_dir)
            elif format.lower() == "csv":
                out_path = os.path.join(settings.processed_dir, f"{os.path.splitext(target.file_name)[0]}.csv")
                await converter.excel_to_csv(target.local_path, out_path)
            elif format.lower() in ("docx", "word"):
                out_path = os.path.join(settings.processed_dir, f"{os.path.splitext(target.file_name)[0]}.docx")
                await converter.pdf_to_word(target.local_path, out_path)
            else:
                raise HTTPException(status_code=400, detail=f"{format} formatiga konvertatsiya mavjud emas")
                
            new_ext = os.path.splitext(out_path)[1].lstrip(".").lower()
            new_record = await crud.save_file_record(
                session=session,
                user_id=db_user.id,
                file_name=os.path.basename(out_path),
                file_type=new_ext,
                telegram_file_id="",
                local_path=out_path,
                file_size=os.path.getsize(out_path)
            )
            return {
                "message": "Konvertatsiya muvaffaqiyatli yakunlandi",
                "new_file_id": new_record.id,
                "new_file_name": new_record.file_name
            }
        except Exception as e:
            logger.error(f"Conversion error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/{file_id}/download")
async def download_file(file_id: int, user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        
        if not target or not os.path.exists(target.local_path):
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
            
        return FastFileResponse(
            path=target.local_path,
            filename=target.file_name,
            media_type="application/octet-stream"
        )

@router.delete("/{file_id}")
async def delete_file(file_id: int, user: dict = Depends(get_current_user)):
    async with get_session() as session:
        db_user = await crud.get_or_create_user(session, user["telegram_id"], user.get("first_name", "Teacher"))
        files = await crud.get_user_files(session, db_user.id)
        target = next((f for f in files if f.id == file_id), None)
        
        if not target:
            raise HTTPException(status_code=404, detail="Fayl topilmadi")
            
        if os.path.exists(target.local_path):
            try:
                os.remove(target.local_path)
            except Exception as e:
                logger.warning(f"Could not delete physical file: {e}")
                
        await crud.delete_file_record(session, file_id)
        return {"message": "Fayl muvaffaqiyatli o'chirildi"}
