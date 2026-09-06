"""Quiz Handler — Multi-step quiz creation workflow using AI."""

import io
import json
import logging
import os
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import get_settings
from bot.keyboards.inline import quiz_settings_keyboard, quiz_type_keyboard, quiz_export_keyboard
from bot.keyboards.reply import back_keyboard, main_menu_keyboard
from bot.services.ai_service import AIService
from bot.services.quiz_service import QuizService

logger = logging.getLogger(__name__)
config = get_settings()
ai_service = AIService(api_key=config.GEMINI_API_KEY)
quiz_service = QuizService(ai_service)

# Conversation states
QUIZ_TOPIC = 0
QUIZ_COUNT = 1
QUIZ_TYPE = 2
QUIZ_PREVIEW = 3
QUIZ_EXPORT = 4


async def quiz_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show quiz creation menu."""
    await update.message.reply_text(
        "📝 Test yaratish\n\n"
        "Mavzuni kiriting yoki matnli fayl yuboring.\n"
        "AI avtomatik ravishda test savollarini yaratadi.",
        reply_markup=back_keyboard(),
    )


async def start_quiz_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive quiz topic and ask for question count."""
    context.user_data["quiz_topic"] = update.message.text
    await update.message.reply_text(
        "📊 Nechta savol bo'lishini tanlang:",
        reply_markup=quiz_settings_keyboard(),
    )
    return QUIZ_COUNT


async def handle_quiz_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle question count selection."""
    query = update.callback_query
    await query.answer()

    count = int(query.data.split("_")[-1])
    context.user_data["quiz_count"] = count

    await query.message.edit_text(
        f"✅ {count} ta savol tanlandi.\n\n"
        "Test turini tanlang:",
        reply_markup=quiz_type_keyboard(),
    )
    return QUIZ_TYPE


async def handle_quiz_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quiz type selection and generate quiz."""
    query = update.callback_query
    await query.answer()

    qtype = query.data.replace("quiz_type_", "")
    context.user_data["quiz_type"] = qtype

    type_names = {"multiple": "Test (A/B/C/D)", "open": "Ochiq savol", "mixed": "Aralash"}
    type_name = type_names.get(qtype, qtype)

    await query.message.edit_text(
        f"⏳ {type_name} formatida test yaratilmoqda...\n"
        "Bu biroz vaqt olishi mumkin."
    )

    try:
        topic = context.user_data.get("quiz_topic", "")
        count = context.user_data.get("quiz_count", 10)

        questions = await ai_service.generate_quiz(
            text=topic,
            num_questions=count,
            quiz_type=qtype,
        )
        context.user_data["quiz_data"] = questions

        # Show preview
        preview = "📝 Test tayyor! Ko'rib chiqing:\n\n"
        for i, q in enumerate(questions[:3], 1):  # Show first 3 questions as preview
            preview += f"{i}. {q.get('question', '')}\n"
            for j, opt in enumerate(q.get("options", [])):
                letter = chr(65 + j)
                preview += f"   {letter}) {opt}\n"
            preview += "\n"

        if len(questions) > 3:
            preview += f"... va yana {len(questions) - 3} ta savol\n\n"

        preview += "Eksport formatini tanlang:"

        await query.message.edit_text(preview, reply_markup=quiz_export_keyboard())
        return QUIZ_EXPORT

    except Exception as e:
        logger.error(f"Quiz generation error: {e}")
        await query.message.edit_text(
            f"❌ Test yaratishda xatolik: {str(e)}\n"
            "Iltimos, qayta urinib ko'ring.",
        )
        return ConversationHandler.END


async def handle_quiz_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quiz export format selection."""
    query = update.callback_query
    await query.answer()

    export_format = query.data.replace("quiz_export_", "")
    questions = context.user_data.get("quiz_data", [])

    if not questions:
        await query.message.edit_text("⚠️ Test ma'lumotlari topilmadi.")
        return ConversationHandler.END

    await query.message.edit_text(f"⏳ {export_format.upper()} formatda tayyorlanmoqda...")

    try:
        if export_format == "word":
            output_path = os.path.join(config.exports_dir, f"test_{query.from_user.id}.docx")
            await quiz_service.export_to_word(questions, output_path)
            with open(output_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename="test.docx",
                    caption="📄 Test Word formatda",
                )

        elif export_format == "pdf":
            output_path = os.path.join(config.exports_dir, f"test_{query.from_user.id}.pdf")
            await quiz_service.export_to_pdf(questions, output_path)
            with open(output_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename="test.pdf",
                    caption="📕 Test PDF formatda",
                )

        elif export_format == "telegram":
            polls = quiz_service.format_for_telegram(questions)
            await query.message.edit_text("📨 Telegram test yuborilmoqda...")
            for poll_data in polls:
                try:
                    await context.bot.send_poll(
                        chat_id=query.message.chat_id,
                        question=poll_data["question"][:300],
                        options=poll_data["options"][:10],
                        type="quiz",
                        correct_option_id=poll_data.get("correct_option_id", 0),
                        explanation=poll_data.get("explanation", "")[:200],
                        is_anonymous=False,
                    )
                except Exception as e:
                    logger.warning(f"Poll send error: {e}")

        await query.message.reply_text(
            "✅ Test tayyor!",
            reply_markup=main_menu_keyboard(),
        )

    except Exception as e:
        logger.error(f"Quiz export error: {e}")
        await query.message.edit_text(f"❌ Eksport xatosi: {str(e)}")

    return ConversationHandler.END
