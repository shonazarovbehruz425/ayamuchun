"""AI Handler — Handles AI-related menu items and conversation flows."""

import logging
import os
import tempfile
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import get_settings
from bot.keyboards.reply import ai_menu_keyboard, back_keyboard, main_menu_keyboard
from bot.services.ai_service import AIService
from bot.processors.word_processor import WordProcessor
from bot.utils.validators import is_prompt_injection
from bot.utils.helpers import parse_lesson_subject_topic, split_html_message
from bot.database.engine import get_session
from bot.database import crud

logger = logging.getLogger(__name__)

from bot.services.ai_service import get_ai_service


# Conversation states
WAITING_TEXT = 0
WAITING_TOPIC = WAITING_TEXT  # Alias for backward compatibility

# Initialize AI service
_config = get_settings()
ai_service = get_ai_service()
word_processor = WordProcessor()


async def ai_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the AI tools submenu."""
    ai_title = _config.AI_DISPLAY_NAME or "EduBot AI"
    await update.message.reply_text(
        f"🧠 <b>{ai_title} — Pedagogik Yordamchi</b>\n\n"
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
    return WAITING_TEXT


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
    return WAITING_TEXT


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


async def cancel_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel active AI conversation, clean user context, and return to main menu."""
    context.user_data.pop("ai_action", None)
    await update.message.reply_text(
        "🏠 Bosh menyu",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def handle_non_text_in_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Catch stickers, audio, voice, or unexpected media during active AI state without hanging."""
    await update.message.reply_text(
        "⚠️ Iltimos, faqat matn yuboring yoki bekor qilish uchun <b>🔙 Orqaga</b> tugmasini bosing.",
        reply_markup=back_keyboard(),
        parse_mode="HTML"
    )
    return WAITING_TEXT


async def handle_file_during_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """If user sends a file during AI conversation, exit AI state cleanly and process the file."""
    context.user_data.pop("ai_action", None)
    from bot.handlers.file_handler import handle_file
    await handle_file(update, context)
    return ConversationHandler.END


async def handle_photo_during_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """If user sends a photo during AI conversation, exit AI state cleanly and process the photo."""
    context.user_data.pop("ai_action", None)
    from bot.handlers.photo_handler import handle_photo
    await handle_photo(update, context)
    return ConversationHandler.END



async def process_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the user's text input based on the selected AI action."""
    raw_text = update.message.text or ""

    # Check if user wants to cancel or go back
    if raw_text.strip() in ("🔙 Orqaga", "❌ Bekor qilish", "/cancel"):
        return await cancel_ai(update, context)

    # B9 fix: If user pressed another AI menu button or main menu button while state is open
    ai_menu_routes = {
        "📝 Dars rejasi": handle_lesson_plan,
        "❓ Test & Savollar": handle_quiz,
        "📋 Xulosa qilish": handle_summarize,
        "💡 Tushuntirish": handle_explain,
        "🔍 Grammatika tekshirish": handle_grammar_check,
        "🔄 Tarjima": handle_translate,
        "✏️ Matn yaxshilash": handle_improve_text,
    }
    if raw_text.strip() in ai_menu_routes:
        return await ai_menu_routes[raw_text.strip()](update, context)

    main_menu_buttons = {
        "📄 Fayl asboblari", "🧠 AI yordamchi", "📝 Test yaratish",
        "📊 Baholar jadvali", "⚙️ Sozlamalar", "📱 Mini App"
    }
    if raw_text.strip() in main_menu_buttons:
        context.user_data.pop("ai_action", None)
        from bot.main import handle_menu_text
        await handle_menu_text(update, context)
        return ConversationHandler.END

    # Check if text is empty or only whitespace
    clean_text = raw_text.strip()
    if not clean_text:
        await update.message.reply_text(
            "⚠️ Iltimos, bo'sh bo'lmagan matn yuboring.\n"
            "Bekor qilish uchun <b>🔙 Orqaga</b> tugmasini bosing.",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )
        return WAITING_TEXT

    # Length limit check (max 15000 chars)
    if len(clean_text) > 15000:
        await update.message.reply_text(
            "⚠️ Kiritilgan matn juda uzun (maksimal 15 000 belgi ruxsat etiladi).\n"
            "Iltimos, matnni qisqartirib qayta yuboring.",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )
        return WAITING_TEXT

    # Prompt injection check
    if is_prompt_injection(clean_text):
        await update.message.reply_text(
            "⚠️ Kechirasiz, xavfsizlik qoidalariga zid bo'lgan yoki tizim ko'rsatmalarini o'zgartirishga urinuvchi so'rovlar qabul qilinmaydi.\n"
            "Iltimos, dars yoki ta'limga oid savol yoki matn yuboring.",
            reply_markup=back_keyboard(),
            parse_mode="HTML"
        )
        return WAITING_TEXT

    text = clean_text
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
            subject, topic = parse_lesson_subject_topic(text)
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

        # Log usage to DB
        try:
            tokens = getattr(ai_service, "last_token_usage", {}) or {}
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, update.effective_user.id, update.effective_user.full_name or "User")
                await crud.log_usage(
                    session,
                    db_user.id,
                    f"ai_{action}",
                    text[:60],
                    prompt_tokens=tokens.get("prompt_tokens", 0),
                    completion_tokens=tokens.get("completion_tokens", 0),
                    total_tokens=tokens.get("total_tokens", 0)
                )
        except Exception as log_err:
            logger.warning(f"Could not log AI usage to DB: {log_err}")

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

        chunks = split_html_message(full_response, max_len=3800)
        # Edit first chunk into status message
        try:
            await msg.edit_text(chunks[0], parse_mode="HTML")
        except Exception:
            await msg.edit_text(chunks[0])

        for chunk in chunks[1:]:
            try:
                await update.message.reply_text(chunk, parse_mode="HTML")
            except Exception:
                await update.message.reply_text(chunk)

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
            "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring."
        )

    await update.message.reply_text(
        "Yana biror narsa qilishni xohlaysizmi?",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END




# ── SMART TELEGRAM CHATBOT & ACTION SUGGESTIONS ─────────────────────────────

def format_ai_response_for_telegram(text: str) -> str:
    """Safely convert AI markdown into clean Telegram HTML entities."""
    import html as html_lib
    import re
    
    # 1. HTML escape everything first
    safe_text = html_lib.escape(text)
    
    # 2. Bold: **text** or __text__ -> <b>text</b>
    safe_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', safe_text)
    safe_text = re.sub(r'__(.+?)__', r'<b>\1</b>', safe_text)
    
    # 3. Italic: *text* or _text_ -> <i>text</i>
    safe_text = re.sub(r'(?<!\w)\*([^\*\n]+?)\*(?!\w)', r'<i>\1</i>', safe_text)
    safe_text = re.sub(r'(?<!\w)_([^\_\n]+?)_(?!\w)', r'<i>\1</i>', safe_text)
    
    # 4. Inline code: `code` -> <code>code</code>
    safe_text = re.sub(r'`([^`\n]+?)`', r'<code>\1</code>', safe_text)
    
    # 5. Headings: ### Header -> <b>Header</b>
    safe_text = re.sub(r'^#{1,6}\s*(.+)$', r'<b>\1</b>', safe_text, flags=re.MULTILINE)
    
    # 6. Bullet lists: * item or - item -> • item
    safe_text = re.sub(r'^[\*\-]\s+', '• ', safe_text, flags=re.MULTILINE)
    
    return safe_text


def build_ai_suggestions_keyboard(topic: str = "") -> InlineKeyboardMarkup:
    """Build quick interactive next-action suggestion chips for Telegram AI responses."""
    settings = get_settings()
    webapp_url = settings.WEBAPP_URL or "https://ayamuchun.onrender.com"
    
    buttons = [
        [
            InlineKeyboardButton("📄 Word (.docx) yuklab olish", callback_data="chat_ai_word"),
            InlineKeyboardButton("📝 5 ta test tuzish", callback_data="chat_ai_quiz"),
        ],
        [
            InlineKeyboardButton("🔄 Rus/Eng tarjima", callback_data="chat_ai_translate"),
            InlineKeyboardButton("📋 Qisqa xulosa", callback_data="chat_ai_summarize"),
        ],
        [
            InlineKeyboardButton("📱 Mini App'da ochish", web_app=WebAppInfo(url=f"{webapp_url}#/ai")),
            InlineKeyboardButton("🗑️ Yangi mavzu", callback_data="chat_ai_clear"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


async def handle_smart_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Intelligently handle any user text in Telegram chat:
    - Recognizes explicit/implicit intents and commands (test, lesson plan, translation, file tools)
    - Generates multi-turn pedagogical AI answers with memory
    - Offers instant interactive micro-actions (Word download, quiz generation, translation, Mini App)
    """
    if not update.message or not update.message.text:
        return

    raw_text = update.message.text.strip()
    chat_id = update.effective_chat.id

    # 1. Send live typing indicator in Telegram header
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass

    # 2. Agar foydalanuvchi avval rasm yuborgan bo'lsa va AI so'ragan savolga javob yozayotgan bo'lsa:
    waiting_photo = context.user_data.pop("waiting_photo_intent", False)
    photo_info = context.user_data.get("last_photo")
    if waiting_photo and photo_info and os.path.exists(photo_info.get("path", "")):
        context.user_data["last_photo_user_wish"] = raw_text
        lower_raw = raw_text.lower()
        
        # Qaysi rejimga mosligini aniqlash:
        action_name = "Surat bilan ishlash"
        if any(k in lower_raw for k in ["3x4", "3*4", "pasport", "viza", "hujjat", "surat"]):
            action_name = "3×4 Hujjat fotosi tayyorlash"
        elif any(k in lower_raw for k in ["pdf", "hujjat qil", "kitob"]):
            action_name = "A4 PDF hujjatiga aylantirish"
        elif any(k in lower_raw for k in ["matn", "ocr", "yozuv", "oqish", "o'qish", "tahlil"]):
            action_name = "Rasmdagi matnni o'qish (AI tahlil)"
        elif any(k in lower_raw for k in ["fon", "oq", "ko'k", "kok", "almashtir"]):
            action_name = "Surat fonini almashtirish"
        else:
            action_name = f"«{raw_text[:35]}» vazifasi"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🤖 AI qilib berish (Avtomatik)", callback_data="photo_ai_auto"),
            ],
            [
                InlineKeyboardButton("🛠️ Qo'lda qilish (Sozlamalar bilan)", callback_data="photo_manual_options"),
            ]
        ])

        await update.message.reply_text(
            f"💡 <b>Tushundim! Sizning tanlovingiz:</b>\n"
            f"🎯 <i>{action_name}</i>\n\n"
            f"Ushbu amalni qanday bajarishni xohlaysiz?\n"
            f"• <b>🤖 AI qilib berish:</b> AI avtomatik tarzda eng maqbul parametrlar bilan tayyorlab beradi.\n"
            f"• <b>🛠️ Qo'lda qilish:</b> Fon ranglari, o'lchamlari va sozlamalarini o'zingiz tanlaysiz.\n\n"
            f"Quyidagi tugmalardan birini tanlang:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    # 3. Check for File Tools intent in user natural language
    lower_text = raw_text.lower()
    if any(w in lower_text for w in ("pdf to word", "pdfni word", "pdf dan word", "pdf wordga")):
        context.user_data["expected_tool"] = "pdf_to_word"
        await update.message.reply_text(
            "🔄 <b>PDF ➔ Word (DOCX)</b>\n\n"
            "Menga <b>PDF fayl</b> yuboring, uni sifatli va tahrirlanadigan Word (.docx) hujjatiga aylantirib beraman.",
            parse_mode="HTML"
        )
        return
    elif any(w in lower_text for w in ("word to pdf", "wordni pdf", "doc to pdf", "word pdfga")):
        context.user_data["expected_tool"] = "word_to_pdf"
        await update.message.reply_text(
            "🔄 <b>Word ➔ PDF</b>\n\n"
            "Menga <b>Word (.docx yoki .doc)</b> fayl yuboring, uni sifatli PDF ga aylantirib beraman.",
            parse_mode="HTML"
        )
        return
    elif any(w in lower_text for w in ("3x4 rasm", "3x4 foto", "hujjat foto", "3*4 rasm")):
        context.user_data["expected_tool"] = "photo_3x4"
        await update.message.reply_text(
            "📸 <b>Hujjat foto (3×4) tayyorlash</b>\n\n"
            "Menga fotosurat yuboring. Uni 3×4 o'lchamga keltirib, oq yoki ko'k fon bilan tayyorlab beraman.",
            parse_mode="HTML"
        )
        return

    import re

    # Clean command prefixes if user typed /ai, /test, /konspekt, etc.
    clean_prompt = raw_text
    if raw_text.startswith("/test") or raw_text.startswith("/quiz"):
        topic = re.sub(r"^/(test|quiz)\s*", "", raw_text).strip() or "Umumiy fanlar"
        clean_prompt = f"Menga quyidagi mavzu bo'yicha 5 ta test (A, B, C, D variantlari va to'g'ri javoblar bilan) tuzib ber: {topic}"
    elif raw_text.startswith("/konspekt") or raw_text.startswith("/dars"):
        topic = re.sub(r"^/(konspekt|dars)\s*", "", raw_text).strip() or "Dars mavzusi"
        clean_prompt = f"Menga quyidagi mavzu bo'yicha 45 daqiqalik to'liq dars ishlanmasi (konspekt) tuzib ber: {topic}"
    elif raw_text.startswith("/tarjima"):
        topic = re.sub(r"^/tarjima\s*", "", raw_text).strip()
        clean_prompt = f"Quyidagi matnni Rus va Ingliz tillariga professional tarjima qil: {topic}"
    elif raw_text.startswith("/xulosa"):
        topic = re.sub(r"^/xulosa\s*", "", raw_text).strip()
        clean_prompt = f"Quyidagi matnni eng muhim tezislarini ajratib qisqacha xulosa qil: {topic}"
    elif raw_text.startswith("/ai") or raw_text.startswith("/chat"):
        clean_prompt = re.sub(r"^/(ai|chat)\s*", "", raw_text).strip()

    if not clean_prompt:
        return

    if len(clean_prompt) > 15000:
        await update.message.reply_text("⚠️ Xabar matni juda uzun (maksimal 15 000 belgi).")
        return

    if is_prompt_injection(clean_prompt):
        await update.message.reply_text(
            "⚠️ Kechirasiz, xavfsizlik qoidalariga zid bo'lgan yoki tizim ko'rsatmalarini o'zgartirishga urinuvchi so'rovlar qabul qilinmaydi."
        )
        return

    status_msg = await update.message.reply_text("⏳ <i>AI javob tayyorlamoqda...</i>", parse_mode="HTML")

    try:
        # Multi-turn conversational memory: restore from DB if RAM is empty
        chat_history = context.user_data.get("telegram_chat_history")
        if chat_history is None:
            chat_history = []
            try:
                from bot.database.engine import get_session
                from bot.database import crud
                async with get_session() as session:
                    db_user = await crud.get_or_create_user(session, update.effective_user.id, update.effective_user.full_name or "User")
                    db_msgs = await crud.get_chat_history(session, db_user.id, session_id="telegram", limit=8)
                    if db_msgs:
                        chat_history = [{"role": m.role, "content": m.content} for m in db_msgs]
            except Exception as dbe:
                logger.warning(f"Could not load chat history from DB: {dbe}")
            context.user_data["telegram_chat_history"] = chat_history
        
        system_instruction = (
            "Siz EduBot AI — o'qituvchilar, talabalar va barcha foydalanuvchilar uchun "
            "yuksak bilimdon, pedagogik tajribali va do'stona virtual sun'iy intellekt yordamchisisiz. "
            "Foydalanuvchining savol, matn va topshiriqlariga doim o'zbek tilida, aniq, chiroyli va tartibli "
            "(sarlavha, qalin harflar, nuqtali ro'yxatlar bilan) javob bering. "
            "Agar savol test yoki konspektga oid bo'lsa, to'liq va o'quv standartlariga mos shaklda tuzing."
        )

        chat_history.append({"role": "user", "content": clean_prompt})
        if len(chat_history) > 8:
            chat_history = chat_history[-8:]
        context.user_data["telegram_chat_history"] = chat_history

        ai_reply = await ai_service.generate_chat(
            messages=chat_history,
            system_prompt=system_instruction
        )

        # Save assistant message to memory
        chat_history.append({"role": "assistant", "content": ai_reply})
        if len(chat_history) > 8:
            chat_history = chat_history[-8:]
        context.user_data["telegram_chat_history"] = chat_history
        context.user_data["last_ai_response"] = ai_reply
        context.user_data["last_ai_topic"] = clean_prompt[:35]

        # Persist messages to DB asynchronously
        try:
            from bot.database.engine import get_session
            from bot.database import crud
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, update.effective_user.id, update.effective_user.full_name or "User")
                await crud.save_chat_message(session, db_user.id, "user", clean_prompt, session_id="telegram")
                await crud.save_chat_message(session, db_user.id, "assistant", ai_reply, session_id="telegram")
        except Exception as dbe:
            logger.warning(f"Could not persist chat message to DB: {dbe}")

        # Format reply
        formatted_html = format_ai_response_for_telegram(ai_reply)
        keyboard = build_ai_suggestions_keyboard(topic=clean_prompt[:30])

        try:
            await status_msg.delete()
        except Exception:
            pass

        # Send response safely
        if len(formatted_html) <= 4000:
            try:
                await update.message.reply_text(
                    formatted_html,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                await update.message.reply_text(ai_reply, reply_markup=keyboard)
        else:
            chunks = [formatted_html[i:i + 3800] for i in range(0, len(formatted_html), 3800)]
            for i, chunk in enumerate(chunks):
                is_last = (i == len(chunks) - 1)
                try:
                    await update.message.reply_text(
                        chunk,
                        reply_markup=keyboard if is_last else None,
                        parse_mode="HTML"
                    )
                except Exception:
                    await update.message.reply_text(
                        chunk,
                        reply_markup=keyboard if is_last else None
                    )

    except Exception as e:
        logger.error(f"Error in handle_smart_chat_message: {e}", exc_info=True)
        err_text = (
            "⚠️ <b>Javob berishda xatolik yuz berdi.</b>\n"
            "Iltimos, qayta urinib ko'ring yoki savolingizni boshqacharoq yozing."
        )
        try:
            await status_msg.edit_text(err_text, parse_mode="HTML")
        except Exception:
            await update.message.reply_text("⚠️ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")


async def handle_chat_ai_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback button clicks from smart suggestions under AI responses."""
    query = update.callback_query
    await query.answer()

    action = query.data
    last_response = context.user_data.get("last_ai_response", "")
    last_topic = context.user_data.get("last_ai_topic", "Material")

    if action == "chat_ai_word":
        if not last_response:
            await query.message.reply_text("⚠️ Avval biror savol yoki mavzu yuboring.")
            return

        wait_msg = await query.message.reply_text("⏳ Word (.docx) hujjati tayyorlanmoqda...")
        try:
            temp_dir = tempfile.mkdtemp()
            clean_title = "".join(c for c in last_topic if c.isalnum() or c in (" ", "-", "_")).strip() or "Material"
            file_name = f"{clean_title[:30]}.docx"
            out_path = os.path.join(temp_dir, file_name)

            await word_processor.create_document(last_response, out_path, title=last_topic)

            with open(out_path, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename=file_name,
                    caption=f"📄 <b>{clean_title}</b> hujjati Word (.docx) formatida tayyor!",
                    parse_mode="HTML"
                )
            try:
                await wait_msg.delete()
                os.remove(out_path)
            except Exception:
                pass
        except Exception as err:
            logger.error(f"Word docx export error: {err}", exc_info=True)
            await wait_msg.edit_text("❌ Word fayl yaratishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

    elif action == "chat_ai_quiz":
        prompt_topic = last_topic or last_response[:200]
        wait_msg = await query.message.reply_text(f"📝 <b>«{last_topic[:30]}»</b> mavzusi bo'yicha 5 ta test tuzilmoqda...", parse_mode="HTML")
        try:
            quiz_list = await ai_service.generate_quiz(text=prompt_topic, num_questions=5, quiz_type="multiple")
            if isinstance(quiz_list, list) and len(quiz_list) > 0 and isinstance(quiz_list[0], dict):
                lines = [f"📝 <b>Mavzu:</b> {last_topic} bo'yicha testlar\n"]
                for i, q in enumerate(quiz_list, 1):
                    lines.append(f"<b>{i}. {q.get('question', '')}</b>")
                    for opt in q.get("options", []):
                        lines.append(f"   {opt}")
                    lines.append(f"✅ <i>To'g'ri javob:</i> {q.get('correct_answer', '')}")
                    if q.get("explanation"):
                        lines.append(f"💡 <i>Izoh:</i> {q.get('explanation', '')}")
                    lines.append("")
                quiz_text = "\n".join(lines)
            else:
                quiz_text = str(quiz_list)

            context.user_data["last_ai_response"] = quiz_text
            context.user_data["last_ai_topic"] = f"{last_topic} - Testlar"

            keyboard = build_ai_suggestions_keyboard(topic=f"{last_topic} - Test")
            await wait_msg.delete()
            await query.message.reply_text(quiz_text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as err:
            logger.error(f"Quiz generation error: {err}", exc_info=True)
            await wait_msg.edit_text("❌ Test tuzishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.")

    elif action == "chat_ai_summarize":
        if not last_response:
            await query.message.reply_text("⚠️ Xulosa qilish uchun avval matn yuboring.")
            return

        wait_msg = await query.message.reply_text("📋 <i>Qisqa xulosa tayyorlanmoqda...</i>", parse_mode="HTML")
        try:
            summary = await ai_service.summarize_text(text=last_response[:4000])
            context.user_data["last_ai_response"] = summary
            keyboard = build_ai_suggestions_keyboard(topic=f"{last_topic} - Xulosa")
            await wait_msg.delete()
            await query.message.reply_text(
                f"📋 <b>Qisqacha Xulosa:</b>\n\n{summary}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as err:
            logger.error(f"Summarize callback error: {err}", exc_info=True)
            await wait_msg.edit_text("❌ Xulosa qilishda xatolik yuz berdi.")

    elif action == "chat_ai_translate":
        if not last_response:
            await query.message.reply_text("⚠️ Tarjima qilish uchun avval matn yuboring.")
            return

        wait_msg = await query.message.reply_text("🔄 <i>Rus va Ingliz tillariga tarjima qilinmoqda...</i>", parse_mode="HTML")
        try:
            tr_prompt = [
                {"role": "user", "content": f"Quyidagi matnni Rus va Ingliz tillariga sifatli va tushunarli qilib tarjima qilib ber:\n\n{last_response[:2500]}"}
            ]
            translated = await ai_service.generate_chat(messages=tr_prompt)
            context.user_data["last_ai_response"] = translated
            keyboard = build_ai_suggestions_keyboard(topic=f"{last_topic} - Tarjima")
            await wait_msg.delete()
            await query.message.reply_text(
                f"🔄 <b>Tarjima (Rus va Ingliz tillarida):</b>\n\n{translated}",
                reply_markup=keyboard
            )
        except Exception as err:
            logger.error(f"Translate callback error: {err}", exc_info=True)
            await wait_msg.edit_text("❌ Tarjima qilishda xatolik yuz berdi.")


    elif action == "chat_ai_clear":
        context.user_data["telegram_chat_history"] = []
        context.user_data["last_ai_response"] = ""
        context.user_data["last_ai_topic"] = ""
        await query.message.reply_text(
            "🧹 <b>Yangi suhbat boshlandi!</b>\n\n"
            "Menga xohlagan savolingiz, mavzungiz, konspekt yoki test tuzish bo'yicha topshirig'ingizni yozishingiz mumkin.",
            parse_mode="HTML"
        )
