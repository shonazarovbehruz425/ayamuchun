from telegram import InlineKeyboardMarkup, InlineKeyboardButton

def file_actions_keyboard(file_type: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📖 Matn olish", callback_data="file_extract_text"),
         InlineKeyboardButton("🧠 AI tahlil", callback_data="file_ai_analyze")]
    ]
    
    if file_type == 'pdf':
        keyboard.append([
            InlineKeyboardButton("✂️ Kesish", callback_data="file_split"),
            InlineKeyboardButton("🔗 Birlashtirish", callback_data="file_merge"),
            InlineKeyboardButton("🔒 Himoyalash", callback_data="file_protect")
        ])
    elif file_type == 'docx':
        keyboard.append([
            InlineKeyboardButton("🔄 PDF ga", callback_data="file_to_pdf"),
            InlineKeyboardButton("✏️ Almashtirish", callback_data="file_replace")
        ])
    elif file_type == 'xlsx':
        keyboard.append([
            InlineKeyboardButton("📊 Statistika", callback_data="file_stats"),
            InlineKeyboardButton("🔄 PDF ga", callback_data="file_to_pdf"),
            InlineKeyboardButton("📋 CSV ga", callback_data="file_to_csv")
        ])
    elif file_type == 'pptx':
        keyboard.append([
            InlineKeyboardButton("🔄 PDF ga", callback_data="file_to_pdf")
        ])
        
    keyboard.append([InlineKeyboardButton("📝 Test yaratish", callback_data="file_quiz")])
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
