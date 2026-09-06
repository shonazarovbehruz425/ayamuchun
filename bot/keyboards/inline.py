from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def file_actions_keyboard(file_type: str) -> InlineKeyboardMarkup:
    from bot.config import get_settings
    from telegram import WebAppInfo
    settings = get_settings()
    keyboard = []
    
    if file_type == 'pdf':
        keyboard.append([
            InlineKeyboardButton("🔄 Word (DOCX) ga", callback_data="file_to_docx"),
            InlineKeyboardButton("🖼️ Rasmlarni olish (ZIP)", callback_data="file_extract_images")
        ])
        if settings.WEBAPP_URL:
            keyboard.append([
                InlineKeyboardButton("✏️ PDF tahrirlash (Mini App)", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#/"))
            ])
        keyboard.append([
            InlineKeyboardButton("📖 Matn olish", callback_data="file_extract_text"),
            InlineKeyboardButton("🧠 AI tahlil", callback_data="file_ai_analyze")
        ])
    elif file_type in ('docx', 'doc'):
        keyboard.append([
            InlineKeyboardButton("🔄 PDF ga", callback_data="file_to_pdf"),
            InlineKeyboardButton("📖 Matn olish", callback_data="file_extract_text")
        ])
        if settings.WEBAPP_URL:
            keyboard.append([
                InlineKeyboardButton("📝 Doc tahrirlash (Mini App)", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#/"))
            ])
        keyboard.append([
            InlineKeyboardButton("🧠 AI tahlil", callback_data="file_ai_analyze")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("📖 Matn olish", callback_data="file_extract_text"),
            InlineKeyboardButton("🧠 AI tahlil", callback_data="file_ai_analyze")
        ])
        
    return InlineKeyboardMarkup(keyboard)

def quiz_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("5 ta savol", callback_data="quiz_count_5"),
         InlineKeyboardButton("10 ta savol", callback_data="quiz_count_10")],
        [InlineKeyboardButton("15 ta savol", callback_data="quiz_count_15"),
         InlineKeyboardButton("20 ta savol", callback_data="quiz_count_20")]
    ]
    return InlineKeyboardMarkup(keyboard)

def quiz_type_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📝 Test (A/B/C/D)", callback_data="quiz_type_multiple"),
         InlineKeyboardButton("✏️ Ochiq savol", callback_data="quiz_type_open")],
        [InlineKeyboardButton("🔀 Aralash", callback_data="quiz_type_mixed")]
    ]
    return InlineKeyboardMarkup(keyboard)

def quiz_export_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📄 Word", callback_data="quiz_export_word"),
         InlineKeyboardButton("📕 PDF", callback_data="quiz_export_pdf")],
        [InlineKeyboardButton("📨 Telegram Quiz", callback_data="quiz_export_telegram")]
    ]
    return InlineKeyboardMarkup(keyboard)

def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✅ Ha", callback_data=f"confirm_{action}"),
         InlineKeyboardButton("❌ Yo'q", callback_data=f"cancel_{action}")]
    ]
    return InlineKeyboardMarkup(keyboard)
