"""Cloud Database Sync Service — Backs up and restores database to/from a Telegram Channel as .js format."""

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
                    "phone_number": getattr(u, "phone_number", None),
                    "photo_url": getattr(u, "photo_url", None),
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
                    "channel_message_id": getattr(f, "channel_message_id", None),
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
            logger.info("Backup channel ID is not configured. Skipping DB sync.")
            return False

        if self.channel_id == settings.STORAGE_CHANNEL_ID:
            logger.warning(
                f"Blocked DB sync: Channel {self.channel_id} is strictly reserved for USER files (PDF, DOCX, Photos). "
                "DB .js dumps must not be sent here."
            )
            return False

        try:
            data = await self.export_database_to_json()
            # Wrap as .js (JavaScript object format) as requested
            js_content = (
                f"// EduBot Cloud Database - {datetime.utcnow().isoformat()}\n"
                f"window.EDUBOT_DB = {json.dumps(data, indent=2, ensure_ascii=False)};\n"
            )
            
            file_stream = io.BytesIO(js_content.encode("utf-8"))
            filename = f"edubot_db_{int(datetime.utcnow().timestamp())}.js"
            
            caption = (
                f"📦 <b>EduBot Database (.js)</b>\n"
                f"🕒 Vaqt: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                f"👤 Foydalanuvchilar: {len(data['users'])}\n"
                f"📁 Fayllar: {len(data['files'])}\n"
                f"📝 Testlar: {len(data['quizzes'])}\n"
                f"📌 Sabab: {reason}"
            )

            sent_msg = await self.bot.send_document(
                chat_id=self.channel_id,
                document=file_stream,
                filename=filename,
                caption=caption,
                parse_mode="HTML",
            )
            # Pin the newest backup message so it can always be located instantly on restart!
            try:
                await sent_msg.pin(disable_notification=True)
            except Exception:
                pass

            logger.info(f"Database successfully saved to Telegram channel {self.channel_id} as {filename}")
            return True
        except TelegramError as te:
            logger.error(f"Telegram error during DB sync to channel: {te}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during DB sync: {e}")
            return False

    async def restore_from_channel(self) -> bool:
        """Find the latest .js backup file in the channel and restore the database."""
        if not self.channel_id or self.channel_id == settings.STORAGE_CHANNEL_ID:
            logger.info("No separate DB backup channel configured for restore.")
            return False

        logger.info(f"Connecting to database channel: {self.channel_id} ...")
        try:
            chat = await self.bot.get_chat(self.channel_id)
            logger.info(f"Connected to database channel: {chat.title or self.channel_id}")

            target_file_id = None

            # 1. Check pinned message first
            if chat.pinned_message and chat.pinned_message.document:
                doc = chat.pinned_message.document
                if doc.file_name and (doc.file_name.endswith(".js") or doc.file_name.endswith(".json")):
                    target_file_id = doc.file_id
                    logger.info(f"Found pinned database file: {doc.file_name}")

            if not target_file_id:
                logger.info("No pinned database backup found. Starting fresh schema in channel.")
                return False

            # Download document
            tg_file = await self.bot.get_file(target_file_id)
            file_bytes = io.BytesIO()
            await tg_file.download_to_memory(file_bytes)
            file_bytes.seek(0)
            raw_text = file_bytes.read().decode("utf-8")

            # Extract JSON from .js
            json_str = raw_text
            if "window.EDUBOT_DB =" in raw_text:
                json_str = raw_text.split("window.EDUBOT_DB =", 1)[1].strip()
                if json_str.endswith(";"):
                    json_str = json_str[:-1].strip()

            data = json.loads(json_str)
            await self._apply_restored_data(data)
            logger.info(f"Database successfully restored from Telegram channel! ({len(data.get('users', []))} users loaded)")
            return True

        except Exception as e:
            logger.error(f"Failed to restore database from channel: {e}")
            return False

    async def _apply_restored_data(self, data: dict) -> None:
        """Insert or update restored data into tables."""
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
                        phone_number=u.get("phone_number"),
                        photo_url=u.get("photo_url"),
                        language=u.get("language", "uz"),
                        created_at=datetime.fromisoformat(u["created_at"]) if u.get("created_at") else datetime.utcnow(),
                        last_active=datetime.fromisoformat(u["last_active"]) if u.get("last_active") else datetime.utcnow(),
                    )
                    session.add(new_u)
                else:
                    if u.get("phone_number") and not existing.phone_number:
                        existing.phone_number = u["phone_number"]
                    if u.get("photo_url") and not existing.photo_url:
                        existing.photo_url = u["photo_url"]

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
                        channel_message_id=f.get("channel_message_id"),
                        uploaded_at=datetime.fromisoformat(f["uploaded_at"]) if f.get("uploaded_at") else datetime.utcnow(),
                    )
                    session.add(new_f)

            await session.commit()
