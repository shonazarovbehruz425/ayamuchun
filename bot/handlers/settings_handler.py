from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards.reply import settings_keyboard

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⚙️ Sozlamalar", reply_markup=settings_keyboard())

async def change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Til o'zgartirildi (Vaqtincha).")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    stats_text = "Sizning statistikangiz:\nFayllar: 0\nTestlar: 0\nAI so'rovlar: 0"
    await update.message.reply_text(stats_text)
