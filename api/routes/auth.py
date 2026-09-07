import hmac
import hashlib
import json
import logging
from urllib.parse import parse_qsl
from fastapi import APIRouter, Depends, HTTPException, Header
from bot.config import get_settings

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
    return user_data

@router.get("/me")
@router.post("/validate")
async def validate_auth(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    return {"status": "ok", "user": user, "is_admin": user.get("is_admin", False)}

from pydantic import BaseModel

class PhoneUpdateRequest(BaseModel):
    phone_number: str

@router.post("/update-phone")
async def update_phone(req: PhoneUpdateRequest, authorization: str = Header(None)):
    user = await get_current_user(authorization)
    # Return updated user info with phone
    user["phone_number"] = req.phone_number
    return {"status": "ok", "phone_number": req.phone_number, "user": user}
