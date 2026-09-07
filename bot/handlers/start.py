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
        "📌 <b>Barcha 12 ta asbob:</b>\n"
        "1️⃣ <b>PDF ➔ Word</b> — PDF faylni sifatli Word (.docx) ga aylantirish\n"
        "2️⃣ <b>Word ➔ PDF</b> — Word hujjatini 100% asl sifatda PDF qilish\n"
        "3️⃣ <b>Doc tahrirlash</b> — Word matn va jadvallarini to'g'ridan-to'g'ri tahrirlash\n"
        "4️⃣ <b>PDF tahrirlash</b> — PDF hujjat matnlarini o'zgartirish\n"
        "5️⃣ 🟥 <b>PDF birlashtirish</b> — Bir nechta PDF ni bitta faylga birlashtirish\n"
        "6️⃣ 🟧 <b>PDF bo'lish</b> — Sahifalarni kesish (masalan: 1-3, 5) yoki ZIP qilish\n"
        "7️⃣ 🟪 <b>PDF kichraytirish</b> — Hajmni 50-80% gacha siqish\n"
        "8️⃣ 🟦 <b>PDF suv belgisi</b> — Shaxsiy matn yoki logotip himoyasi\n"
        "9️⃣ 🖼️ <b>Rasmlarni PDF qilish</b> — Suratlarni tartibli A4 PDF ga yig'ish\n"
        "🔟 📸 <b>Hujjat foto (3×4)</b> — Pasport, viza va hujjat fotosuratlari\n"
        "1️⃣1️⃣ 📦 <b>PDF rasmlarini olish</b> — PDF dagi suratlarni ZIP qilib ajratish\n"
        "1️⃣2️⃣ 🧠 <b>AI Pedagogik yordamchi</b> — Dars ishlanmasi, xulosa, test va tarjimalar\n\n"
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
        "🟥 <b>PDF birlashtirish</b> — Bir nechta PDF hujjatlarini tartibli bitta faylga yig'ish.\n"
        "🟧 <b>PDF bo'lish</b> — Kerakli sahifalar oralig'ini kesib olish yoki ZIP arxiv qilish.\n"
        "🟪 <b>PDF kichraytirish</b> — Hajmni sifatli saqlab siqish (Yengil, Optimal, Kuchli).\n"
        "🟦 <b>PDF suv belgisi</b> — Sahifalarga matn yoki shaxsiy belgi (watermark) qo'yish.\n"
        "🖼️ <b>Rasmlarni PDF qilish</b> — Bir nechta rasmlarni bitta PDF ga birlashtirish.\n"
        "📸 <b>Hujjat foto (3×4)</b> — 3×4 o'lchamli hujjat rasmlarini tayyorlash.\n"
        "📦 <b>PDF rasmlarini olish</b> — PDF ichidagi barcha suratlarni ZIP qilib olish.\n"
        "🧠 <b>AI yordamchi</b> — Mavzularni tushuntirish, test yaratish, dars rejasi va tarjimalar.\n"
        "📱 <b>Mini App</b> — Barcha funksiyalardan zamonaviy veb interfeys orqali foydalanish.\n\n"
        "Savol yoki takliflar bo'lsa, adminga murojaat qiling."
    )
    await update.message.reply_text(help_text, parse_mode="HTML")
