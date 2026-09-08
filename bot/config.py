from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

from pydantic import model_validator

def _parse_channel_id(val: Optional[object]) -> Optional[int]:
    """Safely parse channel ID from environment variable or config value."""
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None
    try:
        return int(val_str)
    except (ValueError, TypeError):
        return None

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = "local_dev_preview_token"
    ADMIN_IDS: List[int] = []
    ADMIN_SECRET_KEY: str = os.getenv("ADMIN_SECRET_KEY", "edubot_admin_secret_2026_superkey")

    # AI Engine Settings (Multi-provider: OpenAI, Gemini, DeepSeek, Claude, Groq, Custom)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini")  # "gemini" | "openai" | "deepseek" | "custom"
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")  # Backward compatibility fallback
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "")        # Custom endpoint e.g. "https://api.openai.com/v1" or "https://api.deepseek.com/v1"
    AI_MODEL: str = os.getenv("AI_MODEL", "")              # e.g. "gemini-2.0-flash", "gpt-4o-mini", "deepseek-chat"
    AI_DISPLAY_NAME: str = os.getenv("AI_DISPLAY_NAME", "EduBot AI")  # Public user-facing name (no third-party brand)

    # 1. Telegram Channel for User Files (PDF, Word, Excel, PPTX, 3x4 photos)
    # Strictly resolved from FILES_CHANNEL_ID or STORAGE_CHANNEL_ID env vars
    FILES_CHANNEL_ID: Optional[int] = None
    STORAGE_CHANNEL_ID: Optional[int] = None

    # 2. Telegram Channel for Database Backup (.js dumps, user sync)
    # Strictly resolved from DATABASE_CHANNEL_ID, CHANNEL_DB_ID, or BACKUP_CHANNEL_ID env vars
    DATABASE_CHANNEL_ID: Optional[int] = None
    BACKUP_CHANNEL_ID: Optional[int] = None
    CHANNEL_DB_ID: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def resolve_channels_from_env(cls, values):
        if not isinstance(values, dict):
            return values

        # Resolve User Files Channel (from env or loaded values)
        files_val = _parse_channel_id(
            values.get("FILES_CHANNEL_ID")
            or values.get("STORAGE_CHANNEL_ID")
            or os.getenv("FILES_CHANNEL_ID")
            or os.getenv("STORAGE_CHANNEL_ID")
        )
        values["FILES_CHANNEL_ID"] = files_val
        values["STORAGE_CHANNEL_ID"] = files_val

        # Resolve Database Backup Channel (from env or loaded values)
        db_val = _parse_channel_id(
            values.get("DATABASE_CHANNEL_ID")
            or values.get("CHANNEL_DB_ID")
            or values.get("BACKUP_CHANNEL_ID")
            or os.getenv("DATABASE_CHANNEL_ID")
            or os.getenv("CHANNEL_DB_ID")
            or os.getenv("BACKUP_CHANNEL_ID")
        )
        values["DATABASE_CHANNEL_ID"] = db_val
        values["BACKUP_CHANNEL_ID"] = db_val
        values["CHANNEL_DB_ID"] = db_val

        return values

    # Persistent Database URL (e.g. Postgres / Supabase / Neon / Render Postgres)
    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL", None)

    # Web App & Host
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://ayamuchun.onrender.com")
    API_HOST: str = "0.0.0.0"
    API_PORT: int = int(os.getenv("PORT", 8000))
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_PORT: int = 8443
    STORAGE_PATH: str = "./storage"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def upload_dir(self) -> str:
        path = os.path.join(self.STORAGE_PATH, "uploads")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def processed_dir(self) -> str:
        path = os.path.join(self.STORAGE_PATH, "processed")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def exports_dir(self) -> str:
        path = os.path.join(self.STORAGE_PATH, "exports")
        os.makedirs(path, exist_ok=True)
        return path

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# Convenience instance (reads lazily or when imported)
def _get_config():
    try:
        return get_settings()
    except Exception:
        return None

config = _get_config()
