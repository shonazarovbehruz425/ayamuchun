import os
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from bot.config import get_settings

_settings = get_settings()
_CUSTOM_DB_URL = getattr(_settings, "DATABASE_URL", None) or os.getenv("DATABASE_URL")

if _CUSTOM_DB_URL:
    # Convert standard postgres:// or postgresql:// to postgresql+asyncpg:// if needed
    db_url = _CUSTOM_DB_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    async_engine = create_async_engine(db_url, echo=False)
else:
    # Internal runtime SQLite engine (acts as local cache synchronized with Telegram Channel)
    _STORAGE_DIR = getattr(_settings, "STORAGE_PATH", "./storage") or "./storage"
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    _LOCAL_DB_FILE = os.path.join(_STORAGE_DIR, "edubot_cache.db")
    async_engine = create_async_engine(f"sqlite+aiosqlite:///{_LOCAL_DB_FILE}", echo=False)

AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

Base = declarative_base()

@asynccontextmanager
async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        def migrate_users(sync_conn):
            try:
                cursor = sync_conn.connection.cursor()
                cursor.execute("PRAGMA table_info(users)")
                cols = [row[1] for row in cursor.fetchall()]
                if 'phone_number' not in cols:
                    try:
                        cursor.execute("ALTER TABLE users ADD COLUMN phone_number VARCHAR")
                    except Exception:
                        pass
                if 'photo_url' not in cols:
                    try:
                        cursor.execute("ALTER TABLE users ADD COLUMN photo_url VARCHAR")
                    except Exception:
                        pass
                cursor.execute("PRAGMA table_info(files)")
                f_cols = [row[1] for row in cursor.fetchall()]
                if 'channel_message_id' not in f_cols:
                    try:
                        cursor.execute("ALTER TABLE files ADD COLUMN channel_message_id INTEGER")
                    except Exception:
                        pass
                cursor.close()
            except Exception:
                pass

        await conn.run_sync(migrate_users)
