"""Cloud Storage Service — Persistent cloud storage via Telegram Channel.
Ensures all user files (photos, 3x4, PDFs, Word, etc.) survive server reboots and ephemeral disk wipes,
auto-restores missing files, and sends files to users with zero channel attribution (hide name)."""

import os
import io
import logging
from datetime import datetime
from typing import Optional, Tuple
import httpx
from telegram import Bot
from telegram.error import TelegramError

from bot.config import get_settings
from bot.utils.helpers import format_file_size

logger = logging.getLogger(__name__)
settings = get_settings()


class CloudStorageService:
    def __init__(self, channel_id: int = None, bot_token: str = None):
        self.channel_id = channel_id or settings.STORAGE_CHANNEL_ID
        self.bot_token = bot_token or settings.BOT_TOKEN

    async def backup_file_to_channel(
        self,
        file_path: str,
        file_name: str,
        telegram_id: int,
        user_full_name: str = "Foydalanuvchi",
        username: str = "",
        tool_name: str = "EduBot Hujjati"
    ) -> Tuple[str, Optional[int]]:
        """
        Upload file to private backup channel configured via env.
        Returns (telegram_file_id, channel_message_id).
        """
        if not self.channel_id:
            logger.warning("Storage channel ID not configured in environment (FILES_CHANNEL_ID). Skipping cloud channel backup.")
            return ("", None)

        if not self.bot_token or self.bot_token in ("local_dev_preview_token", "your_bot_token_here"):
            logger.warning("Bot token not configured for cloud storage backup.")
            return ("", None)

        if not os.path.exists(file_path):
            logger.error(f"Cannot backup non-existent file: {file_path}")
            return ("", None)

        file_size = os.path.getsize(file_path)
        clean_user = username.replace("@", "") if username else "yoq"
        clean_tool = tool_name.replace(" ", "_").replace("(", "").replace(")", "").replace("×", "x")

        caption = (
            f"📁 <b>#User_{telegram_id}</b> | <b>#{clean_tool}</b>\n"
            f"👤 <b>Foydalanuvchi:</b> {user_full_name} (@{clean_user})\n"
            f"📄 <b>Fayl:</b> <code>{file_name}</code> ({format_file_size(file_size)})\n"
            f"⏰ <b>Vaqt:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        )

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                with open(file_path, "rb") as f:
                    files = {"document": (file_name, f)}
                    data = {
                        "chat_id": self.channel_id,
                        "caption": caption,
                        "parse_mode": "HTML"
                    }
                    resp = await client.post(url, data=data, files=files)
                    
                    if resp.status_code == 200:
                        res_json = resp.json()
                        result = res_json.get("result", {})
                        message_id = result.get("message_id")
                        doc = result.get("document", {})
                        file_id = doc.get("file_id", "")
                        logger.info(f"Cloud backup SUCCESS to channel {self.channel_id}: {file_name} (msg_id={message_id}, file_id={file_id[:12]}...)")
                        return (file_id, message_id)
                    else:
                        logger.error(f"Cloud backup FAILED ({resp.status_code}): {resp.text}")
                        return ("", None)
        except Exception as e:
            logger.error(f"Error during cloud storage backup: {e}", exc_info=True)
            return ("", None)

    async def ensure_local_file(self, file_record) -> str:
        """
        Verify if local file exists. If erased due to server reboot/wipe,
        re-download from Telegram Cloud using file_record.telegram_file_id.
        Returns valid local_path on disk.
        """
        local_path = getattr(file_record, "local_path", None)
        telegram_file_id = getattr(file_record, "telegram_file_id", None)

        if local_path and os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            return local_path

        if not telegram_file_id:
            logger.warning(f"No telegram_file_id to restore file: {getattr(file_record, 'file_name', 'unknown')}")
            return local_path or ""

        # Destination path
        user_id = getattr(file_record, "user_id", "common")
        file_name = getattr(file_record, "file_name", "restored_file")
        restore_dir = os.path.join(settings.processed_dir, str(user_id))
        os.makedirs(restore_dir, exist_ok=True)
        restore_path = local_path if local_path else os.path.join(restore_dir, file_name)

        logger.info(f"Local file missing on disk. Auto-restoring from Telegram Cloud: {file_name} ({telegram_file_id[:12]}...)")

        try:
            # 1. Get file path from Telegram
            get_file_url = f"https://api.telegram.org/bot{self.bot_token}/getFile?file_id={telegram_file_id}"
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.get(get_file_url)
                if res.status_code != 200:
                    logger.error(f"Could not getFile from Telegram: {res.text}")
                    return restore_path

                file_info = res.json().get("result", {})
                tg_file_path = file_info.get("file_path")
                if not tg_file_path:
                    logger.error("No file_path returned by Telegram")
                    return restore_path

                # 2. Download bytes
                download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{tg_file_path}"
                dl_res = await client.get(download_url)
                if dl_res.status_code == 200:
                    with open(restore_path, "wb") as out_f:
                        out_f.write(dl_res.content)
                    logger.info(f"File restored successfully to {restore_path} ({len(dl_res.content)} bytes)")
                    return restore_path
                else:
                    logger.error(f"Failed to download restored file: {dl_res.status_code}")
        except Exception as err:
            logger.error(f"Error while restoring file from Telegram: {err}", exc_info=True)

        return restore_path

    async def send_file_to_user_hidden(
        self,
        telegram_id: int,
        file_record,
        caption: str = ""
    ) -> bool:
        """
        Send file to user WITHOUT ANY channel attribution ("hide name").
        Uses sendDocument with telegram_file_id or local file stream directly.
        Recipient sees it as a pure direct message from EduBot.
        """
        if not self.bot_token or not telegram_id or self.bot_token in ("local_dev_preview_token", "your_bot_token_here"):
            return False

        telegram_file_id = getattr(file_record, "telegram_file_id", None)
        file_name = getattr(file_record, "file_name", "hujjat")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"

        # Try fast sending using telegram_file_id (zero re-upload, 100% clean, no channel info)
        if telegram_file_id:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    data = {
                        "chat_id": telegram_id,
                        "document": telegram_file_id,
                        "caption": caption,
                        "parse_mode": "HTML"
                    }
                    resp = await client.post(url, data=data)
                    if resp.status_code == 200:
                        logger.info(f"Sent file {file_name} to user {telegram_id} via file_id (Hidden channel attribution)")
                        return True
                    else:
                        logger.warning(f"Fast send via file_id failed ({resp.status_code}): {resp.text}. Falling back to stream.")
            except Exception as e:
                logger.warning(f"Fast send via file_id exception: {e}")

        # Fallback: ensure local file and send as fresh document stream
        local_path = await self.ensure_local_file(file_record)
        if local_path and os.path.exists(local_path):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    with open(local_path, "rb") as f:
                        files = {"document": (file_name, f)}
                        data = {
                            "chat_id": telegram_id,
                            "caption": caption,
                            "parse_mode": "HTML"
                        }
                        resp = await client.post(url, data=data, files=files)
                        if resp.status_code == 200:
                            logger.info(f"Sent file {file_name} to user {telegram_id} via fresh stream (Hidden channel attribution)")
                            return True
                        else:
                            logger.error(f"Stream send failed: {resp.status_code} - {resp.text}")
            except Exception as e:
                logger.error(f"Error streaming file to user: {e}")

        return False


_storage_instance = None

def get_cloud_storage() -> CloudStorageService:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = CloudStorageService()
    return _storage_instance
