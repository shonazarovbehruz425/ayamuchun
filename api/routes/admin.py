import os
import time
import httpx
import logging
import platform
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from bot.config import get_settings
from bot.database.engine import get_session
from bot.database import crud

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
SERVER_START_TIME = time.time()

class BroadcastRequest(BaseModel):
    message: str
    parse_mode: Optional[str] = "HTML"

class DirectMessageRequest(BaseModel):
    telegram_id: int
    message: str

def format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

@router.get("/stats")
async def get_stats():
    uptime_seconds = int(time.time() - SERVER_START_TIME)
    uptime_str = f"{uptime_seconds // 3600}s {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
    
    storage_bytes = 0
    storage_files_count = 0
    if os.path.exists(settings.STORAGE_PATH):
        for root, _, files in os.walk(settings.STORAGE_PATH):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    storage_bytes += os.path.getsize(fp)
                    storage_files_count += 1
                except Exception:
                    pass

    async with get_session() as session:
        db_stats = await crud.get_admin_overview(session)

    bot_configured = bool(settings.BOT_TOKEN and settings.BOT_TOKEN not in ("your_bot_token_here", "local_dev_preview_token"))
    ai_configured = bool(settings.AI_API_KEY or settings.GEMINI_API_KEY)

    return {
        "status": "ok",
        "overview": {
            "total_users": db_stats["total_users"],
            "active_today": db_stats["active_today"],
            "total_files": db_stats["total_files"],
            "total_quizzes": db_stats["total_quizzes"],
            "db_storage_bytes": db_stats["total_storage_bytes"],
            "db_storage_formatted": format_bytes(db_stats["total_storage_bytes"]),
            "disk_storage_bytes": storage_bytes,
            "disk_storage_formatted": format_bytes(storage_bytes),
            "disk_files_count": storage_files_count
        },
        "system": {
            "uptime": uptime_str,
            "uptime_seconds": uptime_seconds,
            "python_version": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "bot_configured": bot_configured,
            "ai_configured": ai_configured,
            "gemini_configured": ai_configured,
            "ai_display_name": settings.AI_DISPLAY_NAME or "EduBot AI",
            "ai_provider": settings.AI_PROVIDER,
            "ai_model": settings.AI_MODEL or "standart",
            "webapp_url": settings.WEBAPP_URL,
            "server_time": datetime.utcnow().strftime("%d.%m.%Y %H:%M:%S UTC")
        }
    }

@router.get("/users")
async def get_users(search: Optional[str] = Query(None), limit: int = Query(100)):
    async with get_session() as session:
        users = await crud.get_admin_users_list(session, limit=limit, search=search)
    return {"status": "ok", "users": users, "count": len(users)}

@router.get("/files")
async def get_recent_files(limit: int = Query(50)):
    async with get_session() as session:
        files = await crud.get_admin_recent_files(session, limit=limit)
    for f in files:
        f["formatted_size"] = format_bytes(f["file_size"])
    return {"status": "ok", "files": files, "count": len(files)}

@router.post("/send-message")
async def send_direct_message(req: DirectMessageRequest):
    if not settings.BOT_TOKEN or settings.BOT_TOKEN in ("your_bot_token_here", "local_dev_preview_token"):
        return {"status": "mock", "message": "Bot tokeni sozlanmagan (mahalliy test rejimi). Xabar simulyatsiya qilindi."}

    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": req.telegram_id,
        "text": req.message,
        "parse_mode": "HTML"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                return {"status": "ok", "detail": "Xabar muvaffaqiyatli yetkazildi"}
            else:
                return {"status": "error", "detail": f"Telegram xatosi: {resp.text}"}
    except Exception as e:
        logger.error(f"send_direct_message error: {e}")
        return {"status": "error", "detail": str(e)}

@router.post("/broadcast")
async def broadcast_announcement(req: BroadcastRequest):
    async with get_session() as session:
        user_ids = await crud.get_all_user_ids(session)

    if not user_ids:
        return {"status": "ok", "sent_count": 0, "failed_count": 0, "message": "Foydalanuvchilar topilmadi"}

    if not settings.BOT_TOKEN or settings.BOT_TOKEN in ("your_bot_token_here", "local_dev_preview_token"):
        return {
            "status": "mock",
            "sent_count": len(user_ids),
            "failed_count": 0,
            "message": f"Mahalliy test rejimi: {len(user_ids)} ta foydalanuvchiga simulyatsiya qilindi."
        }

    sent_count = 0
    failed_count = 0
    url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient(timeout=10.0) as client:
        for uid in user_ids:
            try:
                resp = await client.post(url, json={
                    "chat_id": uid,
                    "text": req.message,
                    "parse_mode": req.parse_mode
                })
                if resp.status_code == 200:
                    sent_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1

    return {
        "status": "ok",
        "sent_count": sent_count,
        "failed_count": failed_count,
        "total_targets": len(user_ids)
    }

@router.post("/cleanup")
async def cleanup_storage():
    deleted_files = 0
    freed_bytes = 0
    cutoff_time = time.time() - (86400 * 2)

    for folder in [settings.upload_dir, settings.processed_dir, settings.exports_dir]:
        if not os.path.exists(folder):
            continue
        for fname in os.listdir(folder):
            fp = os.path.join(folder, fname)
            try:
                if os.path.isfile(fp):
                    mtime = os.path.getmtime(fp)
                    if mtime < cutoff_time:
                        sz = os.path.getsize(fp)
                        os.remove(fp)
                        deleted_files += 1
                        freed_bytes += sz
            except Exception as e:
                logger.warning(f"Error removing {fp}: {e}")

    return {
        "status": "ok",
        "deleted_files": deleted_files,
        "freed_bytes": freed_bytes,
        "freed_formatted": format_bytes(freed_bytes)
    }

@router.get("/backup-db")
async def download_db_backup():
    db_candidates = [
        os.path.join(settings.STORAGE_PATH, "edubot_cache.db"),
        os.path.join(settings.STORAGE_PATH, "edubot.db")
    ]
    db_path = None
    for cand in db_candidates:
        if os.path.exists(cand) and os.path.getsize(cand) > 0:
            db_path = cand
            break
    if not db_path:
        for cand in db_candidates:
            if os.path.exists(cand):
                db_path = cand
                break

    if not db_path:
        raise HTTPException(status_code=404, detail="Ma'lumotlar bazasi fayli topilmadi")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"edubot_backup_{timestamp}.db"
    return FileResponse(
        path=db_path,
        filename=filename,
        media_type="application/x-sqlite3"
    )
