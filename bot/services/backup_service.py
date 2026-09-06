"""Cloud Database Sync Service — Backs up and restores database to/from a Telegram Channel as .js / JSON format."""

import io
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.future import select
from telegram import Bot
from telegram.error import TelegramError

from bot.config import get_settings
from bot.database.engine import get_session
from bot.database.models import User, File, Quiz, UsageLog

logger = logging.getLogger(__name__)
settings = get_settings()


class DatabaseSyncService:
    """Manages exporting DB state to Telegram Channel and restoring on startup."""

    def __init__(self, bot: Bot, channel_id: int):
        self.bot = bot
        self.channel_id = channel_id

    async def export_database_to_json(self) -> dict:
        """Dump all tables into a structured dictionary."""
        async with get_session() as session:
            # 1. Users
            users_res = await session.execute(select(User))
            users = [
                {
                    "id": u.id,
                    "telegram_id": u.telegram_id,
                    "full_name": u.full_name,
                    "username": u.username,
                    "language": u.language,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                    "last_active": u.last_active.isoformat() if u.last_active else None,
                }
                for u in users_res.scalars().all()
            ]

            # 2. Files
            files_res = await session.execute(select(File))
            files = [
                {
                    "id": f.id,
                    "user_id": f.user_id,
                    "file_name": f.file_name,
                    "file_type": f.file_type,
                    "telegram_file_id": f.telegram_file_id,
                    "local_path": f.local_path,
                    "file_size": f.file_size,
                    "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
                }
                for f in files_res.scalars().all()
            ]

            # 3. Quizzes
            quizzes_res = await session.execute(select(Quiz))
            quizzes = [
                {
                    "id": q.id,
                    "user_id": q.user_id,
                    "title": q.title,
                    "subject": q.subject,
                    "questions_count": q.questions_count,
                    "questions_data": q.questions_data,
                    "created_at": q.created_at.isoformat() if q.created_at else None,
                }
                for q in quizzes_res.scalars().all()
            ]

            # 4. Usage Logs
            logs_res = await session.execute(select(UsageLog))
            usage_logs = [
                {
                    "id": l.id,
                    "user_id": l.user_id,
                    "action_type": l.action_type,
                    "details": l.details,
                    "created_at": l.created_at.isoformat() if l.created_at else None,
                }
                for l in logs_res.scalars().all()
            ]

            return {
                "version": 1,
                "exported_at": datetime.utcnow().isoformat(),
                "users": users,
                "files": files,
                "quizzes": quizzes,
                "usage_logs": usage_logs,
            }

    async def sync_to_channel(self, reason: str = "Auto-Sync") -> bool:
        """Export database to a .js file and upload it to the backup channel."""
        if not self.channel_id:
            logger.warning("Backup channel ID is not configured. Skipping sync.")
            return False

        try:
            data = await self.export_database_to_json()
            # Wrap as .js (JavaScript object format) as requested
            js_content = f"// EduBot Database Backup - {datetime.utcnow().isoformat()}\nwindow.EDUBOT_DB = {json.dumps(data, indent=2, ensure_ascii=False)};\n"
            
            file_stream = io.BytesIO(js_content.encode("utf-8"))
            filename = f"edubot_db_{int(datetime.utcnow().timestamp())}.js"
            
            caption = (
                f"📦 <b>EduBot Database Backup</b>\n"
                f"🕒 Vaqt: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"👤 Foydalanuvchilar: {len(data['users'])}\n"
                f"📁 Fayllar: {len(data['files'])}\n"
                f"📝 Testlar: {len(data['quizzes'])}\n"
                f"📌 Sabab: {reason}"
            )

            await self.bot.send_document(
                chat_id=self.channel_id,
                document=file_stream,
                filename=filename,
                caption=caption,
                parse_mode="HTML",
            )
            logger.info(f"Database successfully backed up to channel {self.channel_id} as {filename}")
            return True
        except TelegramError as te:
            logger.error(f"Telegram error during DB sync to channel: {te}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during DB sync: {e}")
            return False

    async def restore_from_channel(self) -> bool:
        """Find the latest .js backup file in the channel and restore the database."""
        if not self.channel_id:
            logger.warning("No channel ID provided for DB restore.")
            return False

        logger.info(f"Checking channel {self.channel_id} for database backups...")
        try:
            # We fetch chat history or latest updates to find the last database backup file
            # In Telegram Bot API, we can inspect messages by listening or via getChat/forward
            # Alternatively, bot sends a probe or reads last known backup message
            # For robust recovery on startup, bot queries the last messages if bot has history access
            
            # Note: For bots in channels, get_chat gives chat info. 
            # To fetch messages directly, we can read updates or check pins/history:
            chat = await self.bot.get_chat(self.channel_id)
            logger.info(f"Connected to backup channel: {chat.title or self.channel_id}")

            # If the channel has a pinned message with backup or recent document:
            pinned = chat.pinned_message
            target_file_id = None

            if pinned and pinned.document and (pinned.document.file_name.endswith(".js") or pinned.document.file_name.endswith(".json")):
                target_file_id = pinned.document.file_id
                logger.info(f"Found pinned DB backup in channel: {pinned.document.file_name}")

            # If no pinned message, we'll restore if passed or when updates arrive
            if not target_file_id:
                logger.info("No pinned DB backup found in channel. Database will start with existing or new schema.")
                return False

            # Download document
            tg_file = await self.bot.get_file(target_file_id)
            file_bytes = io.BytesIO()
            await tg_file.download_to_memory(file_bytes)
            file_bytes.seek(0)
            raw_text = file_bytes.read().decode("utf-8")

            # Extract JSON from .js (window.EDUBOT_DB = { ... };)
            json_str = raw_text
            if "window.EDUBOT_DB =" in raw_text:
                json_str = raw_text.split("window.EDUBOT_DB =", 1)[1].strip()
                if json_str.endswith(";"):
                    json_str = json_str[:-1].strip()

            data = json.loads(json_str)
            await self._apply_restored_data(data)
            logger.info("Database successfully restored from Telegram channel!")
            return True

        except Exception as e:
            logger.error(f"Failed to restore database from channel: {e}")
            return False

    async def _apply_restored_data(self, data: dict) -> None:
        """Insert or update restored data into SQLite tables."""
        async with get_session() as session:
            # 1. Restore Users
            for u in data.get("users", []):
                res = await session.execute(select(User).where(User.telegram_id == u["telegram_id"]))
                existing = res.scalar_one_or_none()
                if not existing:
                    new_u = User(
                        id=u.get("id"),
                        telegram_id=u["telegram_id"],
                        full_name=u["full_name"],
                        username=u.get("username"),
                        language=u.get("language", "uz"),
                        created_at=datetime.fromisoformat(u["created_at"]) if u.get("created_at") else datetime.utcnow(),
                        last_active=datetime.fromisoformat(u["last_active"]) if u.get("last_active") else datetime.utcnow(),
                    )
                    session.add(new_u)

            await session.commit()

            # 2. Restore Quizzes
            for q in data.get("quizzes", []):
                res = await session.execute(select(Quiz).where(Quiz.id == q["id"]))
                existing = res.scalar_one_or_none()
                if not existing:
                    new_q = Quiz(
                        id=q["id"],
                        user_id=q["user_id"],
                        title=q["title"],
                        subject=q.get("subject"),
                        questions_count=q["questions_count"],
                        questions_data=q["questions_data"],
                        created_at=datetime.fromisoformat(q["created_at"]) if q.get("created_at") else datetime.utcnow(),
                    )
                    session.add(new_q)

            await session.commit()

            # 3. Restore Files
            for f in data.get("files", []):
                res = await session.execute(select(File).where(File.id == f["id"]))
                existing = res.scalar_one_or_none()
                if not existing:
                    new_f = File(
                        id=f["id"],
                        user_id=f["user_id"],
                        file_name=f["file_name"],
                        file_type=f["file_type"],
                        telegram_file_id=f.get("telegram_file_id", ""),
                        local_path=f["local_path"],
                        file_size=f["file_size"],
                        uploaded_at=datetime.fromisoformat(f["uploaded_at"]) if f.get("uploaded_at") else datetime.utcnow(),
                    )
                    session.add(new_f)

            await session.commit()
