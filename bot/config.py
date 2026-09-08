from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

def _parse_channel_id(val: Optional[str], default: Optional[int] = None) -> Optional[int]:
    """Safely parse channel ID from environment variable string."""
    if val is None:
        return default
    val_str = str(val).strip()
    if not val_str:
        return default
    try:
        return int(val_str)
    except (ValueError, TypeError):
        return default

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
    # Reads from FILES_CHANNEL_ID or STORAGE_CHANNEL_ID
    STORAGE_CHANNEL_ID: int = _parse_channel_id(
        os.getenv("FILES_CHANNEL_ID") or os.getenv("STORAGE_CHANNEL_ID"),
        default=-1003745209875
    )

    # 2. Telegram Channel for Database Backup (.js dumps, user sync)
    # Reads from DATABASE_CHANNEL_ID, CHANNEL_DB_ID, or BACKUP_CHANNEL_ID
    BACKUP_CHANNEL_ID: Optional[int] = _parse_channel_id(
        os.getenv("DATABASE_CHANNEL_ID") or os.getenv("CHANNEL_DB_ID") or os.getenv("BACKUP_CHANNEL_ID"),
        default=None
    )
    CHANNEL_DB_ID: Optional[int] = _parse_channel_id(
        os.getenv("DATABASE_CHANNEL_ID") or os.getenv("CHANNEL_DB_ID") or os.getenv("BACKUP_CHANNEL_ID"),
        default=None
    )

    @property
    def FILES_CHANNEL_ID(self) -> int:
        return self.STORAGE_CHANNEL_ID

    @property
    def DATABASE_CHANNEL_ID(self) -> Optional[int]:
        return self.BACKUP_CHANNEL_ID

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
