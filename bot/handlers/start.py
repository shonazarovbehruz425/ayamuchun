"""Start and Help Handlers — Registers user in database and sends welcome text."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards.reply import main_menu_keyboard
from bot.database.engine import get_session
from bot.database import crud

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    # Register/update user in database
    try:
        async with get_session() as session:
            await crud.get_or_create_user(
                session=session,
                telegram_id=user.id,
                full_name=user.full_name or user.first_name,
                username=user.username
            )
            await crud.log_usage(session, user.id, "start_bot", f"User started bot: {user.id}")
    except Exception as e:
        logger.error(f"Error registering user on /start: {e}")

    welcome_text = (
        f"Assalomu alaykum, {user.first_name}! 🎓 <b>EduBot</b>'ga xush kelibsiz.\n\n"
        "Men o'qituvchi va murabbiylar uchun yaratilgan universal yordamchiman.\n\n"
        "📌 <b>Imkoniyatlar:</b>\n"
        "• PDF, Word, Excel, PowerPoint fayllarni tahlil qilish va konvertatsiya\n"
        "• AI orqali dars rejasi, xulosalar va tarjimalar\n"
        "• Avtomatik testlar tuzish va Word/PDF formatda olish\n"
        "• Baholar va davomat jadvallari\n"
        "• Telegram Mini App orqali qulay boshqaruv\n\n"
        "Quyidagi menyudan kerakli bo'limni tanlang:"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📖 <b>EduBot yordam bo'limi:</b>\n\n"
        "📄 <b>Fayl asboblari</b> — PDF, DOCX, XLSX, PPTX fayllarni yuboring va ulardan matn ajratish, konvertatsiya qilish yoki tahlil qilish imkoniyati.\n"
        "🧠 <b>AI yordamchi</b> — Mavzularni tushuntirish, dars ishlanmasi (lesson plan) yaratish, grammatika tekshirish.\n"
        "📝 <b>Test yaratish</b> — Istalgan mavzu yoki matn asosida avtomatik test tuzish.\n"
        "📊 <b>Baholar jadvali</b> — O'quvchilar ro'yxati va fanlar bo'yicha tayyor Excel jadval generatsiyasi.\n"
        "📱 <b>Mini App</b> — Barcha funksiyalarni qulay veb interfeys orqali boshqarish.\n\n"
        "Savol yoki takliflar uchun bot administratsiyasiga murojaat qiling."
    )
    await update.message.reply_text(help_text, parse_mode="HTML")
