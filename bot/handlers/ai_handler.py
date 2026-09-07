"""AI Handler — Handles AI-related menu items and conversation flows."""

import logging
import os
import tempfile
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import get_settings
from bot.keyboards.reply import ai_menu_keyboard, back_keyboard, main_menu_keyboard
from bot.services.ai_service import AIService
from bot.processors.word_processor import WordProcessor

logger = logging.getLogger(__name__)

# Conversation states
WAITING_TEXT = 0
WAITING_TOPIC = 1

# Initialize AI service
_config = get_settings()
ai_service = AIService(api_key=_config.GEMINI_API_KEY)
word_processor = WordProcessor()


async def ai_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the AI tools submenu."""
    await update.message.reply_text(
        "🧠 <b>AI Pedagogik Yordamchi (Gemini 2.0 Flash)</b>\n\n"
        "O'qituvchi va murabbiylar uchun maxsus moslashtirilgan sun'iy intellekt xizmatlari.\n"
        "Quyidagi asboblardan birini tanlang:",
        reply_markup=ai_menu_keyboard(),
        parse_mode="HTML"
    )


async def handle_lesson_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start lesson plan flow — ask for subject and topic."""
    context.user_data["ai_action"] = "lesson_plan"
    await update.message.reply_text(
        "📝 <b>Dars Rejasi (Konspekt) Tuzish</b>\n\n"
        "Fan, sinf va mavzuni yozing. AI 45 daqiqalik dars bosqichlari (kirish, yangi mavzu, mustahkamlash, baholash, uyga vazifa) bo'yicha to'liq konspekt tayyorlab beradi.\n\n"
        "<b>Format:</b> <code>[Sinf] [Fan] — [Mavzu]</code>\n"
        "<i>Misol:</i> <code>5-sinf Matematika — Oddiy kasrlar ustida amallar</code>\n"
        "<i>Misol:</i> <code>8-sinf Fizika — Nyutonning 2-qonuni va formulasi</code>",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TOPIC


async def handle_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start quiz generation flow."""
    context.user_data["ai_action"] = "quiz"
    await update.message.reply_text(
        "❓ <b>Test & Savollar Tuzish (A/B/C/D)</b>\n\n"
        "Mavzu va savollar sonini kiriting. AI to'g'ri va noto'g'ri variantlar hamda javob izohlari bilan tayyor testlar tuzadi.\n\n"
        "<b>Format:</b> <code>[Savollar soni] ta test: [Mavzu nomi]</code>\n"
        "<i>Misol:</i> <code>5 ta test: 8-sinf Biologiya — Hujayra tuzilishi</code>\n"
        "<i>Misol:</i> <code>10 ta test: O'zbekiston tarixi — Amir Temur davri</code>",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TEXT


async def handle_summarize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start summarize flow — ask user for text."""
    context.user_data["ai_action"] = "summarize"
    await update.message.reply_text(
        "📋 <b>Katta Matnni Xulosa Qilish</b>\n\n"
        "Xulosa qilinadigan maqola, darslik parchasini yoki buyruq matnini yuboring.\n"
        "AI uning eng asosiy tezislari va qisqa xulosalarini ajratib beradi.",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TEXT


async def handle_explain(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start topic explanation flow."""
    context.user_data["ai_action"] = "explain"
    await update.message.reply_text(
        "💡 <b>Mavzuni Sodda Tushuntirish</b>\n\n"
        "Qaysi tushuncha yoki formulani o'quvchilarga sodda qilib tushuntirib berish kerak?\n"
        "Mavzu nomini yozing. AI hayotiy misollar va o'xshatishlar bilan tushuntiradi.\n\n"
        "<i>Misol:</i> <code>Nisbiylik nazariyasi (Eynshteyn)</code>\n"
        "<i>Misol:</i> <code>Quyosh va oy tutilishi qanday yuz beradi</code>",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TOPIC


async def handle_grammar_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start grammar check flow."""
    context.user_data["ai_action"] = "grammar"
    await update.message.reply_text(
        "🔍 <b>Grammatika & Imlo Tekshiruvi</b>\n\n"
        "Imlosi, tinish belgilari va uslubi tekshirilishi kerak bo'lgan matnni yuboring.\n"
        "AI barcha xatolarni aniqlab, tuzatilgan tayyor ko'rinishini taqdim etadi.",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TEXT


async def handle_translate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start translate flow — ask user for text."""
    context.user_data["ai_action"] = "translate"
    await update.message.reply_text(
        "🔄 <b>Professional Tarjima</b>\n\n"
        "Tarjima qilinadigan matnni yuboring.\n"
        "Pedagogik va ilmiy atamalar aniq saqlangan holda O'zbek ⇄ Rus ⇄ Ingliz tillariga tarjima qilinadi.",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TEXT


async def handle_improve_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start text improvement flow."""
    context.user_data["ai_action"] = "improve"
    await update.message.reply_text(
        "✏️ <b>Matnni Sayqallash & Boyitish</b>\n\n"
        "O'qituvchi nutqi, hisobot, tavsiyanoma yoki maqolani professional pedagogik uslubga keltirish uchun matnni yuboring.",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TEXT


async def process_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the user's text input based on the selected AI action."""
    text = update.message.text
    action = context.user_data.get("ai_action", "summarize")

    msg = await update.message.reply_text("⏳ AI tahlil qilmoqda va tayyorlamoqda, biroz kuting...")

    try:
        title = "AI Natijasi"
        if action == "summarize":
            result = await ai_service.summarize_text(text)
            header = "📋 <b>Matn Xulosasi:</b>"
            title = "Matn Xulosasi"
        elif action == "translate":
            result = await ai_service.translate_text(text)
            header = "🔄 <b>Tarjima Natijasi:</b>"
            title = "Tarjima Natijasi"
        elif action == "improve":
            result = await ai_service.improve_text(text)
            header = "✏️ <b>Sayqallangan Matn:</b>"
            title = "Sayqallangan Matn"
        elif action == "grammar":
            result = await ai_service.check_grammar(text)
            header = "🔍 <b>Grammatika Tekshiruvi:</b>"
            title = "Grammatika Tekshiruvi"
        elif action == "explain":
            result = await ai_service.explain_topic(text)
            header = "💡 <b>Sodda Tushuntirish:</b>"
            title = f"{text[:30]} — Tushuntirish"
        elif action == "lesson_plan":
            if "—" in text:
                parts = text.split("—", 1)
                subject, topic = parts[0].strip(), parts[1].strip()
            elif "-" in text:
                parts = text.split("-", 1)
                subject, topic = parts[0].strip(), parts[1].strip()
            else:
                subject, topic = "Umumiy", text.strip()
            result = await ai_service.generate_lesson_plan(subject, topic)
            header = "📝 <b>Dars Rejasi (Konspekt):</b>"
            title = f"{subject} — {topic} (Konspekt)"
        elif action == "quiz":
            import re
            num_q = 5
            num_match = re.search(r'(\d+)\s*ta', text, re.IGNORECASE)
            if num_match:
                try:
                    num_q = min(int(num_match.group(1)), 20)
                except ValueError:
                    num_q = 5
            quiz_list = await ai_service.generate_quiz(text, num_questions=num_q, quiz_type="multiple")
            header = "❓ <b>Test Savollari:</b>"
            title = f"{text[:30]} (Test)"
            if isinstance(quiz_list, list) and len(quiz_list) > 0 and isinstance(quiz_list[0], dict):
                lines = []
                for i, q in enumerate(quiz_list, 1):
                    lines.append(f"{i}. {q.get('question', '')}")
                    for opt in q.get("options", []):
                        lines.append(f"   {opt}")
                    lines.append(f"To'g'ri javob: {q.get('correct_answer', '')}")
                    if q.get("explanation"):
                        lines.append(f"Izoh: {q.get('explanation', '')}")
                    lines.append("")
                result = "\n".join(lines)
            else:
                result = str(quiz_list)
        else:
            result = await ai_service.summarize_text(text)
            header = "📋 <b>Natija:</b>"
            title = "AI Natijasi"

        full_response = f"{header}\n\n{result}"

        # If result is large, generate a Word docx as well so teacher can directly download it!
        doc_path = None
        try:
            temp_dir = tempfile.mkdtemp()
            clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip() or "AI_Natijasi"
            file_name = f"{clean_title}.docx"
            doc_path = os.path.join(temp_dir, file_name)
            await word_processor.create_document(result, doc_path, title=title)
        except Exception as doc_err:
            logger.warning(f"Could not generate docx preview for AI message: {doc_err}")
            doc_path = None

        if len(full_response) > 4000:
            chunks = [full_response[i:i + 4000] for i in range(0, len(full_response), 4000)]
            await msg.edit_text(chunks[0], parse_mode="HTML" if "<b" in chunks[0] else None)
            for chunk in chunks[1:]:
                await update.message.reply_text(chunk)
        else:
            try:
                await msg.edit_text(full_response, parse_mode="HTML")
            except Exception:
                await msg.edit_text(full_response)

        # Send .docx document if generated
        if doc_path and os.path.exists(doc_path):
            with open(doc_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(doc_path),
                    caption="📄 <i>Ushbu material Word (.docx) formatida ham tayyorlandi!</i>",
                    parse_mode="HTML"
                )
            try:
                os.remove(doc_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"AI processing error: {e}", exc_info=True)
        await msg.edit_text(
            f"❌ Xatolik yuz berdi: {str(e)}\n"
            "Iltimos, qayta urinib ko'ring."
        )

    await update.message.reply_text(
        "Yana biror narsa qilishni xohlaysizmi?",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END

