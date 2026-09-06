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
                    "username": user_obj.get("username", "")
                }
            return {"telegram_id": int(parsed_data.get("id", 12345678)), "first_name": "Teacher"}
        return None
    except Exception as e:
        logger.warning(f"validate_init_data error: {e}")
        return None

async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        # Dev fallback if no auth header passed
        return {"telegram_id": 99999999, "first_name": "Demo Teacher", "username": "demo"}
    
    parts = authorization.split(" ")
    if len(parts) == 2 and parts[0] == "Bearer":
        init_data = parts[1]
        user_info = validate_init_data(init_data, settings.BOT_TOKEN)
        if user_info:
            return user_info
        # If bot token isn't yet configured with real values or testing locally:
        if settings.BOT_TOKEN == "your_bot_token_here":
            return {"telegram_id": 99999999, "first_name": "Teacher", "username": "teacher"}
        raise HTTPException(status_code=401, detail="Noto'g'ri Telegram autentifikatsiya ma'lumoti")
        
    return {"telegram_id": 99999999, "first_name": "Teacher", "username": "teacher"}

@router.post("/validate")
async def validate_auth(authorization: str = Header(None)):
    user = await get_current_user(authorization)
    return {"status": "ok", "user": user}
