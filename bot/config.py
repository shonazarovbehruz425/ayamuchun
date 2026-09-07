from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: str = "local_dev_preview_token"
    ADMIN_IDS: List[int] = []

    # AI Engine Settings (Multi-provider: OpenAI, Gemini, DeepSeek, Claude, Groq, Custom)
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini")  # "gemini" | "openai" | "deepseek" | "custom"
    AI_API_KEY: str = os.getenv("AI_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")  # Backward compatibility fallback
    AI_BASE_URL: str = os.getenv("AI_BASE_URL", "")        # Custom endpoint e.g. "https://api.openai.com/v1" or "https://api.deepseek.com/v1"
    AI_MODEL: str = os.getenv("AI_MODEL", "")              # e.g. "gemini-2.0-flash", "gpt-4o-mini", "deepseek-chat"
    AI_DISPLAY_NAME: str = os.getenv("AI_DISPLAY_NAME", "EduBot AI")  # Public user-facing name (no third-party brand)

    # Telegram Cloud Storage Channel for user documents, photos (3x4), PDFs, DOCXs
    STORAGE_CHANNEL_ID: int = int(os.getenv("STORAGE_CHANNEL_ID", "-1003745209875"))
    # Separate channel for DB dumps (if configured; None by default so user storage channel is never polluted)
    BACKUP_CHANNEL_ID: Optional[int] = None
    CHANNEL_DB_ID: Optional[int] = None

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
