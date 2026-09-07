import hmac
import hashlib
import json
import logging
import httpx
from urllib.parse import parse_qsl
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import Response
from bot.config import get_settings
from bot.database.engine import get_session
from bot.database.models import User
from sqlalchemy.future import select

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

def validate_init_data(init_data: str, bot_token: str) -> dict:
    try:
        parsed_data = dict(parse_qsl(init_data))
        if 'hash' not in parsed_data:
            return None
        
        hash_val = parsed_data.pop('hash')
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(calculated_hash, hash_val):
            user_data_str = parsed_data.get("user")
            if user_data_str:
                user_obj = json.loads(user_data_str)
                return {
                    "telegram_id": user_obj.get("id"),
                    "first_name": user_obj.get("first_name", "Teacher"),
                    "last_name": user_obj.get("last_name", ""),
                    "username": user_obj.get("username", ""),
                    "photo_url": user_obj.get("photo_url", ""),
                    "phone_number": user_obj.get("phone_number", ""),
                    "language_code": user_obj.get("language_code", "uz"),
                    "is_premium": user_obj.get("is_premium", False)
                }
            return {"telegram_id": int(parsed_data.get("id", 12345678)), "first_name": "Teacher", "username": ""}
        return None
    except Exception as e:
        logger.warning(f"validate_init_data error: {e}")
        return None

async def get_current_user(authorization: str = Header(None)):
    user_data = {
        "telegram_id": 99999999,
        "first_name": "Demo Teacher",
        "last_name": "",
        "username": "demo_teacher",
        "photo_url": "",
        "phone_number": "",
        "language_code": "uz",
        "is_premium": False
    }
    
    if authorization:
        parts = authorization.split(" ")
        if len(parts) == 2 and parts[0] == "Bearer":
            init_data = parts[1]
            validated = validate_init_data(init_data, settings.BOT_TOKEN)
            if validated:
                user_data = validated
            elif settings.BOT_TOKEN not in ("your_bot_token_here", "local_dev_preview_token"):
                raise HTTPException(status_code=401, detail="Noto'g'ri Telegram autentifikatsiya ma'lumoti")

    user_data["is_admin"] = user_data["telegram_id"] in settings.ADMIN_IDS

    # Check database to see if phone_number or photo_url is already saved
    try:
        async with get_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == user_data["telegram_id"]))
            db_user = result.scalar_one_or_none()
            if db_user:
                if getattr(db_user, "phone_number", None):
                    user_data["phone_number"] = db_user.phone_number
                if getattr(db_user, "photo_url", None):
                    user_data["photo_url"] = db_user.photo_url
    except Exception as e:
        logger.warning(f"Error querying user from db: {e}")

    # If photo_url is still empty, set it to the avatar proxy endpoint
    if not user_data.get("photo_url"):
        user_data["photo_url"] = f"/api/auth/avatar?uid={user_data['telegram_id']}"

    return user_data

async def get_admin_user(authorization: str = Header(None)) -> dict:
    """Strict dependency for admin endpoints. Verifies admin Telegram ID or valid admin secret key."""
    if authorization:
        parts = authorization.split(" ")
        if len(parts) == 2:
            scheme, token = parts[0], parts[1]
            # Check for direct Admin Secret Key bearer token
            if scheme == "Bearer" and settings.ADMIN_SECRET_KEY and token == settings.ADMIN_SECRET_KEY:
                return {
                    "telegram_id": settings.ADMIN_IDS[0] if settings.ADMIN_IDS else 1,
                    "first_name": "Admin",
                    "username": "admin",
                    "is_admin": True
                }

    # Fall back to Telegram user validation and check is_admin
    user = await get_current_user(authorization)
    if not user.get("is_admin"):
        raise HTTPException(
            status_code=403,
            detail="Kirish taqiqlangan: Ushbu amal uchun Administrator huquqi talab qilinadi"
        )
    return user

@router.get("/avatar")
async def get_telegram_avatar(uid: int, current_user: dict = Depends(get_current_user)):
    """Fetch user's actual profile photo via Telegram Bot API and stream it as image/jpeg. Requires authenticated user."""
    # Only allow fetching one's own avatar unless admin
    if not current_user.get("is_admin") and current_user.get("telegram_id") != uid:
        raise HTTPException(status_code=403, detail="Faqat o'zingizning profilingiz rasmini yuklashingiz mumkin")

    if not settings.BOT_TOKEN or settings.BOT_TOKEN in ("your_bot_token_here", "local_dev_preview_token"):
        raise HTTPException(status_code=404, detail="Bot token unavailable for avatar fetch")

    try:
        url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getUserProfilePhotos?user_id={uid}&limit=1"
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok") and data.get("result", {}).get("total_count", 0) > 0:
                    photos = data["result"]["photos"][0]
                    # Select largest photo
                    file_id = photos[-1]["file_id"]
                    file_resp = await client.get(f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getFile?file_id={file_id}")
                    if file_resp.status_code == 200:
                        file_data = file_resp.json()
                        if file_data.get("ok"):
                            file_path = file_data["result"]["file_path"]
                            img_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file_path}"
                            img_resp = await client.get(img_url)
                            if img_resp.status_code == 200:
                                return Response(content=img_resp.content, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
    except Exception as e:
        logger.warning(f"Failed to fetch telegram avatar for uid={uid}: {e}")

    raise HTTPException(status_code=404, detail="Avatar not found")

@router.get("/me")
@router.post("/validate")
async def validate_auth(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    return {"status": "ok", "user": user, "is_admin": user.get("is_admin", False)}

import re
from pydantic import BaseModel, field_validator

class PhoneUpdateRequest(BaseModel):
    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Strip all whitespace, dashes, parentheses
        v_clean = v.strip()
        # Strictly allow format like +998901234567 or 998901234567
        # Digits with optional single leading +
        digits = re.sub(r'[\s\-\(\)]', '', v_clean)
        if not re.match(r'^\+?[0-9]{7,18}$', digits):
            raise ValueError("Noto'g'ri telefon raqami formati. Masalan: +998901234567")
        return digits

@router.post("/update-phone")
async def update_phone(req: PhoneUpdateRequest, authorization: str = Header(None)):
    user = await get_current_user(authorization)
    user["phone_number"] = req.phone_number

    # Persist to database
    try:
        async with get_session() as session:
            result = await session.execute(select(User).where(User.telegram_id == user["telegram_id"]))
            db_user = result.scalar_one_or_none()
            if db_user:
                db_user.phone_number = req.phone_number
                await session.commit()
    except Exception as e:
        logger.warning(f"Error persisting phone to DB: {e}")

    return {"status": "ok", "phone_number": req.phone_number, "user": user}
