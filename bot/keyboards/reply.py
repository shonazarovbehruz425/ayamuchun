from telegram import ReplyKeyboardMarkup

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ['📄 Fayl asboblari', '🧠 AI yordamchi'],
        ['📝 Test yaratish', '📊 Baholar jadvali'],
        ['⚙️ Sozlamalar', '📱 Mini App']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def ai_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ['📋 Xulosa qilish', '🔄 Tarjima'],
        ['📝 Dars rejasi', '✏️ Matn yaxshilash'],
        ['🔍 Grammatika tekshirish', '💡 Tushuntirish'],
        ['🔙 Orqaga']
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
