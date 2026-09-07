from telegram import ReplyKeyboardMarkup

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ['🔄 PDF ➔ Word', '🔄 Word ➔ PDF'],
        ['📝 Doc tahrirlash', '✏️ PDF tahrirlash'],
        ['🖼️ Rasmlarni PDF qilish', '📦 PDF rasmlarini olish'],
        ['🧠 AI yordamchi', '📱 Mini App'],
        ['⚙️ Sozlamalar']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def ai_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ['📝 Dars rejasi', '❓ Test & Savollar'],
        ['📋 Xulosa qilish', '💡 Tushuntirish'],
        ['🔍 Grammatika tekshirish', '🔄 Tarjima'],
        ['✏️ Matn yaxshilash', '🔙 Orqaga']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [['🔙 Orqaga']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def cancel_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [['❌ Bekor qilish']]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def settings_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ['🌐 Tilni o\'zgartirish'],
        ['📊 Statistika'],
        ['🔙 Orqaga']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
