"""AI Handler — Handles AI-related menu items and conversation flows."""

import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import get_settings
from bot.keyboards.reply import ai_menu_keyboard, back_keyboard, main_menu_keyboard
from bot.services.ai_service import AIService

logger = logging.getLogger(__name__)

# Conversation states
WAITING_TEXT = 0
WAITING_TOPIC = 1

# Initialize AI service
_config = get_settings()
ai_service = AIService(api_key=_config.GEMINI_API_KEY)


async def ai_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the AI tools submenu."""
    await update.message.reply_text(
        "🧠 AI yordamchi bo'limi\n\n"
        "Quyidagi asboblardan birini tanlang:",
        reply_markup=ai_menu_keyboard(),
    )


async def handle_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start summarize flow — ask user for text."""
    context.user_data["ai_action"] = "summarize"
    await update.message.reply_text(
        "📋 Xulosa qilish uchun matn yuboring:",
        reply_markup=back_keyboard(),
    )
    return WAITING_TEXT


async def handle_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start translate flow — ask user for text."""
    context.user_data["ai_action"] = "translate"
    await update.message.reply_text(
        "🔄 Tarjima qilish uchun matn yuboring:\n"
        "(Til avtomatik aniqlanadi va o'zbek/rus/ingliz tiliga tarjima qilinadi)",
        reply_markup=back_keyboard(),
    )
    return WAITING_TEXT


async def handle_lesson_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start lesson plan flow — ask for subject and topic."""
    context.user_data["ai_action"] = "lesson_plan"
    await update.message.reply_text(
        "📝 Dars rejasi yaratish uchun fan va mavzuni kiriting.\n"
        "Format: Fan — Mavzu\n"
        "Masalan: Matematika — Kvadrat tenglama",
        reply_markup=back_keyboard(),
    )
    return WAITING_TOPIC


async def handle_improve_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start text improvement flow."""
    context.user_data["ai_action"] = "improve"
    await update.message.reply_text(
        "✏️ Yaxshilash uchun matn yuboring:",
        reply_markup=back_keyboard(),
    )
    return WAITING_TEXT


async def handle_grammar_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start grammar check flow."""
    context.user_data["ai_action"] = "grammar"
    await update.message.reply_text(
        "🔍 Grammatikasini tekshirish uchun matn yuboring:",
        reply_markup=back_keyboard(),
    )
    return WAITING_TEXT


async def handle_explain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start topic explanation flow."""
    context.user_data["ai_action"] = "explain"
    await update.message.reply_text(
        "💡 Qaysi mavzuni tushuntirishimni xohlaysiz?\n"
        "Mavzu nomini yozing:",
        reply_markup=back_keyboard(),
    )
    return WAITING_TOPIC


async def process_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the user's text input based on the selected AI action."""
    text = update.message.text
    action = context.user_data.get("ai_action", "summarize")

    msg = await update.message.reply_text("⏳ AI ishlamoqda, biroz kuting...")

    try:
        if action == "summarize":
            result = await ai_service.summarize_text(text)
            header = "📋 Xulosa:"
        elif action == "translate":
            result = await ai_service.translate_text(text)
            header = "🔄 Tarjima:"
        elif action == "improve":
            result = await ai_service.improve_text(text)
            header = "✏️ Yaxshilangan matn:"
        elif action == "grammar":
            result = await ai_service.check_grammar(text)
            header = "🔍 Grammatika tekshiruvi:"
        elif action == "explain":
            result = await ai_service.explain_topic(text)
            header = "💡 Tushuntirish:"
        elif action == "lesson_plan":
            # Parse "Fan — Mavzu" format
            if "—" in text:
                parts = text.split("—", 1)
                subject = parts[0].strip()
                topic = parts[1].strip()
            elif "-" in text:
                parts = text.split("-", 1)
                subject = parts[0].strip()
                topic = parts[1].strip()
            else:
                subject = "Umumiy"
                topic = text.strip()
            result = await ai_service.generate_lesson_plan(subject, topic)
            header = "📝 Dars rejasi:"
        else:
            result = await ai_service.summarize_text(text)
            header = "📋 Natija:"

        # Truncate if too long for Telegram
        full_response = f"{header}\n\n{result}"
        if len(full_response) > 4096:
            # Send as multiple messages
            chunks = [full_response[i:i + 4096] for i in range(0, len(full_response), 4096)]
            await msg.edit_text(chunks[0])
            for chunk in chunks[1:]:
                await update.message.reply_text(chunk)
        else:
            await msg.edit_text(full_response)

    except Exception as e:
        logger.error(f"AI processing error: {e}")
        await msg.edit_text(
            f"❌ Xatolik yuz berdi: {str(e)}\n"
            "Iltimos, qayta urinib ko'ring."
        )

    await update.message.reply_text(
        "Yana biror narsa qilishni xohlaysizmi?",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END
