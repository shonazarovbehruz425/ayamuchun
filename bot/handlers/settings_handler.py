"""Settings and Admin Backup Handlers — Displays statistics and manual DB sync trigger."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import get_settings
from bot.keyboards.reply import settings_keyboard
from bot.database.engine import get_session
from bot.database import crud
from bot.services.backup_service import DatabaseSyncService

logger = logging.getLogger(__name__)
settings = get_settings()


async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⚙️ <b>Sozlamalar bo'limi</b>", reply_markup=settings_keyboard(), parse_mode="HTML")


async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🇺🇿 Hozirgi til: <b>O'zbek tili</b>\n(Keyingi yangilanishlarda boshqa tillar ham qo'shiladi)", parse_mode="HTML")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        async with get_session() as session:
            db_user = await crud.get_or_create_user(session, user.id, user.full_name or user.first_name)
            stats = await crud.get_user_stats(session, db_user.id)
            
            stats_text = (
                f"📊 <b>Sizning statistikangiz:</b>\n\n"
                f"👤 Ism: {user.full_name}\n"
                f"📁 Yuklangan fayllar: <b>{stats['file_count']}</b> ta\n"
                f"📝 Yaratilgan testlar: <b>{stats['quiz_count']}</b> ta\n"
            )
            await update.message.reply_text(stats_text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await update.message.reply_text("Statistikani yuklashda xatolik yuz berdi.")


async def manual_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manual trigger to backup database to Telegram channel."""
    if not settings.BACKUP_CHANNEL_ID or settings.BACKUP_CHANNEL_ID == settings.STORAGE_CHANNEL_ID:
        await update.message.reply_text(
            "ℹ️ Maxsus ma'lumotlar bazasi zaxira kanali sozlanmagan.\n"
            "Foydalanuvchilar kanali faqat hujjatlar (PDF, Word) va rasmlar (3x4) uchun ajratilgan."
        )
        return

    msg = await update.message.reply_text("⏳ Ma'lumotlar bazasi alohida zaxira kanaliga yuborilmoqda...")
    try:
        sync_svc = DatabaseSyncService(bot=context.bot, channel_id=settings.BACKUP_CHANNEL_ID)
        success = await sync_svc.sync_to_channel(reason=f"Manual backup by {update.effective_user.id}")
        if success:
            await msg.edit_text("✅ Ma'lumotlar bazasi zaxira kanaliga muvaffaqiyatli saqlandi!")
        else:
            await msg.edit_text("❌ Alohida kanalga zaxiralashda xatolik yuz berdi.")
    except Exception as e:
        logger.error(f"Manual backup error: {e}")
        await msg.edit_text(f"❌ Xatolik: {e}")
