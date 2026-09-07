from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def file_actions_keyboard(file_type: str) -> InlineKeyboardMarkup:
    from bot.config import get_settings
    from telegram import WebAppInfo
    settings = get_settings()
    keyboard = []
    
    if file_type == 'pdf':
        keyboard.append([
            InlineKeyboardButton("🔄 Word (DOCX) ga", callback_data="file_to_docx"),
            InlineKeyboardButton("🟪 Kichraytirish", callback_data="file_compress")
        ])
        keyboard.append([
            InlineKeyboardButton("🟧 PDF Bo'lish", callback_data="file_split"),
            InlineKeyboardButton("🟦 Suv belgisi", callback_data="file_watermark")
        ])
        keyboard.append([
            InlineKeyboardButton("🟥 Birlashtirish", callback_data="file_merge"),
            InlineKeyboardButton("🖼️ Rasmlar (ZIP)", callback_data="file_extract_images")
        ])
        if settings.WEBAPP_URL:
            keyboard.append([
                InlineKeyboardButton("📱 Mini App'da barcha asboblar", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#/"))
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

def photo_actions_keyboard() -> InlineKeyboardMarkup:
    from bot.config import get_settings
    from telegram import WebAppInfo
    settings = get_settings()
    keyboard = [
        [InlineKeyboardButton("📸 3×4 Hujjat fotosi tayyorlash", callback_data="photo_process_3x4")],
        [InlineKeyboardButton("🖼️ PDF ga aylantirish", callback_data="photo_to_pdf")],
    ]
    if settings.WEBAPP_URL:
        keyboard.append([
            InlineKeyboardButton("🎨 Mini App 3×4 Studiyada ochish", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#/?tool=photo3x4"))
        ])
    return InlineKeyboardMarkup(keyboard)

def photo_result_keyboard() -> InlineKeyboardMarkup:
    from bot.config import get_settings
    from telegram import WebAppInfo
    settings = get_settings()
    keyboard = []
    if settings.WEBAPP_URL:
        keyboard.append([
            InlineKeyboardButton("🎨 Mini App Studiyada boshqarish", web_app=WebAppInfo(url=f"{settings.WEBAPP_URL}#/?tool=photo3x4"))
        ])
    keyboard.append([
        InlineKeyboardButton("⚪ Oq fon", callback_data="photo_bg_white"),
        InlineKeyboardButton("🔵 Ko'k fon", callback_data="photo_bg_blue")
    ])
    keyboard.append([
        InlineKeyboardButton("🔘 Kulrang", callback_data="photo_bg_gray"),
        InlineKeyboardButton("📐 Burchak (Doira)", callback_data="photo_toggle_corner")
    ])
    return InlineKeyboardMarkup(keyboard)

