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
        "Men hujjatlar bilan ishlash va ta'lim jarayonini tezlashtiruvchi universal yordamchiman.\n\n"
        "📌 <b>Asosiy 7 ta asbob:</b>\n"
        "1️⃣ <b>PDF ➔ Word</b> — PDF faylni sifatli Word (.docx) ga aylantirish\n"
        "2️⃣ <b>Word ➔ PDF</b> — Word hujjatini 100% asl sifatda PDF qilish\n"
        "3️⃣ <b>Doc tahrirlash</b> — Word matn va jadvallarini to'g'ridan-to'g'ri tahrirlash\n"
        "4️⃣ <b>PDF tahrirlash</b> — PDF hujjat matnlarini o'zgartirish\n"
        "5️⃣ <b>Rasmlarni PDF qilish</b> — Suratlarni tartibli A4 PDF ga yig'ish\n"
        "6️⃣ <b>PDF rasmlarini olish</b> — PDF dagi barcha rasmlarni ZIP qilib olish\n"
        "7️⃣ <b>AI Pedagogik yordamchi</b> — Dars ishlanmasi, xulosa, test va tarjimalar\n\n"
        "Quyidagi menyudan kerakli asbobni tanlang yoki fayl yuboring:"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📖 <b>EduBot — Asboblar bo'yicha qo'llanma:</b>\n\n"
        "🔄 <b>PDF ➔ Word</b> — PDF fayl yuboring, uni bir zumda tahrirlanadigan DOCX faylga o'tkazib beradi.\n"
        "🔄 <b>Word ➔ PDF</b> — Word (.docx, .doc) fayl yuboring, uni sifatli PDF hujjatga aylantiradi.\n"
        "📝 <b>Doc tahrirlash</b> — Word faylingizni qulay interaktiv veb tahrirlovchida ochish va tahrirlash.\n"
        "✏️ <b>PDF tahrirlash</b> — PDF matnlarini to'g'ridan-to'g'ri tahrirlash.\n"
        "🖼️ <b>Rasmlarni PDF qilish</b> — Bir nechta rasmlarni bitta PDF ga birlashtirish.\n"
        "📦 <b>PDF rasmlarini olish</b> — PDF fayl ichidagi barcha suratlarni alohida ZIP arxivida yuklab olish.\n"
        "🧠 <b>AI yordamchi</b> — Mavzularni tushuntirish, test yaratish, dars rejasi va tarjimalar.\n"
        "📱 <b>Mini App</b> — Barcha funksiyalardan zamonaviy veb interfeys orqali foydalanish.\n\n"
        "Savol yoki takliflar bo'lsa, adminga murojaat qiling."
    )
    await update.message.reply_text(help_text, parse_mode="HTML")
