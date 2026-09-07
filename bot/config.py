from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = "local_dev_preview_token"
    ADMIN_IDS: List[int] = []

    # AI (Google Gemini) - Optional
    GEMINI_API_KEY: str = ""

    # Telegram Channel Vault & Database (Cloud storage)
    CHANNEL_DB_ID: int = -1003745209875
    BACKUP_CHANNEL_ID: int = -1003745209875
    STORAGE_CHANNEL_ID: int = -1003745209875

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
