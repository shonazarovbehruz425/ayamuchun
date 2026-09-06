from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from bot.keyboards.reply import main_menu_keyboard
# try:
#     from database.crud import get_or_create_user
# except ImportError:
#     pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    
    welcome_text = (
        f"Assalomu alaykum, {user.first_name}! EduBot'ga xush kelibsiz.\n\n"
        "Men sizning shaxsiy ta'lim yordamchingizman. Quyidagi bo'limlardan birini tanlang:"
    )
    await update.message.reply_text(welcome_text, reply_markup=main_menu_keyboard())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "EduBot yordam bo'limi:\n\n"
        "📄 Fayl asboblari - PDF, DOCX, XLSX kabi fayllarni tahrirlash.\n"
        "🧠 AI yordamchi - Matnlarni tahlil qilish, tarjima va h.k.\n"
        "📝 Test yaratish - Fayllar yoki matnlardan avtomatik testlar tuzish.\n"
        "📊 Baholar jadvali - O'quvchilar reytingini yaratish.\n"
        "⚙️ Sozlamalar - Bot sozlamalari va tilni o'zgartirish."
    )
    await update.message.reply_text(help_text)
