from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str
    ADMIN_IDS: List[int] = []

    # AI (Google Gemini) - Optional default to prevent hard crash if not set immediately
    GEMINI_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./storage/edubot.db"

    # Web App & Host
    WEBAPP_URL: str = ""
    API_HOST: str = "0.0.0.0"
    API_PORT: int = int(os.getenv("PORT", 8000))
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_PORT: int = 8443
    STORAGE_PATH: str = "./storage"
    BACKUP_CHANNEL_ID: int = -1004294226425

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
