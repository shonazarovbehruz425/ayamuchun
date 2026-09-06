"""EduBot - Main entry point for the Telegram bot and FastAPI server."""

import asyncio
import logging
import signal
import sys

import uvicorn
from telegram import Update, MenuButtonWebApp, WebAppInfo
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from bot.config import get_settings
from bot.database.engine import init_db
from bot.handlers.start import start_command, help_command
from bot.handlers.file_handler import handle_file, handle_file_callback
from bot.handlers.ai_handler import (
    ai_menu,
    handle_summarize,
    handle_translate,
    handle_lesson_plan,
    handle_improve_text,
    handle_grammar_check,
    handle_explain,
    process_text_input,
    WAITING_TEXT,
    WAITING_TOPIC,
)
from bot.handlers.quiz_handler import (
    quiz_menu,
    start_quiz_creation,
    handle_quiz_count,
    handle_quiz_type,
    handle_quiz_export,
    QUIZ_TOPIC,
    QUIZ_COUNT,
    QUIZ_TYPE,
    QUIZ_EXPORT,
)
from bot.handlers.tools_handler import tools_menu, create_grade_table, WAITING_STUDENTS, WAITING_SUBJECTS
from bot.handlers.settings_handler import settings_menu, show_stats, change_language, manual_backup_command
from bot.keyboards.reply import main_menu_keyboard
from bot.services.backup_service import DatabaseSyncService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

config = get_settings()


# ── Menu text routing ──────────────────────────────────────────────────────

async def handle_menu_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route main menu button presses to the appropriate handlers."""
    text = update.message.text

    if text == "📄 Fayl asboblari":
        await update.message.reply_text(
            "📎 Iltimos, menga fayl yuboring.\n"
            "Qo'llab-quvvatlanadigan formatlar: PDF, Word, Excel, PowerPoint, CSV"
        )
    elif text == "🧠 AI yordamchi":
        await ai_menu(update, context)
    elif text == "📝 Test yaratish":
        await quiz_menu(update, context)
    elif text == "📊 Baholar jadvali":
        await tools_menu(update, context)
    elif text == "⚙️ Sozlamalar":
        await settings_menu(update, context)
    elif text == "📱 Mini App":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        if config.WEBAPP_URL:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "📱 Mini App ochish",
                    web_app=WebAppInfo(url=config.WEBAPP_URL)
                )]
            ])
            await update.message.reply_text(
                "Mini ilovani ochish uchun quyidagi tugmani bosing:",
                reply_markup=keyboard,
            )
        else:
            await update.message.reply_text(
                "ℹ️ Mini App havolasi serverda sozlanmoqda. Tez orada faollashadi!"
            )
    elif text == "🔙 Orqaga":
        await update.message.reply_text(
            "🏠 Bosh menyu",
            reply_markup=main_menu_keyboard(),
        )
    else:
        await update.message.reply_text(
            "Kechirasiz, men bu buyruqni tushunmadim.\n"
            "Iltimos, menyudan tanlang yoki /help buyrug'ini yuboring."
        )


# ── Application builder ───────────────────────────────────────────────────

def build_application():
    """Build and configure the Telegram bot application."""
    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .connection_pool_size(30)
        .pool_timeout(30.0)
        .build()
    )

    # ── Command handlers ───────────────────────────────────────────────
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("backup", manual_backup_command))

    # ── AI conversation handler ────────────────────────────────────────
    ai_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📋 Xulosa qilish$"), handle_summarize),
            MessageHandler(filters.Regex("^🔄 Tarjima$"), handle_translate),
            MessageHandler(filters.Regex("^📝 Dars rejasi$"), handle_lesson_plan),
            MessageHandler(filters.Regex("^✏️ Matn yaxshilash$"), handle_improve_text),
            MessageHandler(filters.Regex("^🔍 Grammatika tekshirish$"), handle_grammar_check),
            MessageHandler(filters.Regex("^💡 Tushuntirish$"), handle_explain),
        ],
        states={
            WAITING_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_input),
            ],
            WAITING_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_input),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🔙 Orqaga$"), handle_menu_text),
            CommandHandler("cancel", help_command),
        ],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(ai_conv_handler)

    # ── Quiz conversation handler ──────────────────────────────────────
    quiz_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📝 Test yaratish$"), lambda u, c: start_quiz_topic(u, c)),
        ],
        states={
            QUIZ_TOPIC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_quiz_creation),
            ],
            QUIZ_COUNT: [
                CallbackQueryHandler(handle_quiz_count, pattern="^quiz_count_"),
            ],
            QUIZ_TYPE: [
                CallbackQueryHandler(handle_quiz_type, pattern="^quiz_type_"),
            ],
            QUIZ_EXPORT: [
                CallbackQueryHandler(handle_quiz_export, pattern="^quiz_export_"),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🔙 Orqaga$"), handle_menu_text),
            CommandHandler("cancel", help_command),
        ],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(quiz_conv_handler)

    # ── Tools conversation handler ─────────────────────────────────────
    tools_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📊 Baholar jadvali$"), tools_menu),
        ],
        states={
            WAITING_STUDENTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_grade_table),
            ],
            WAITING_SUBJECTS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, create_grade_table),
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^🔙 Orqaga$"), handle_menu_text),
            CommandHandler("cancel", help_command),
        ],
        per_user=True,
        per_chat=True,
    )
    application.add_handler(tools_conv_handler)

    # ── Document handler ───────────────────────────────────────────────
    doc_filter = filters.Document.FileExtension("pdf") | \
                 filters.Document.FileExtension("docx") | \
                 filters.Document.FileExtension("xlsx") | \
                 filters.Document.FileExtension("pptx") | \
                 filters.Document.FileExtension("doc") | \
                 filters.Document.FileExtension("xls") | \
                 filters.Document.FileExtension("csv")
    application.add_handler(MessageHandler(doc_filter, handle_file))

    # ── File action callbacks ──────────────────────────────────────────
    application.add_handler(CallbackQueryHandler(handle_file_callback, pattern="^file_"))

    # ── Settings handlers ──────────────────────────────────────────────
    application.add_handler(MessageHandler(filters.Regex("^⚙️ Sozlamalar$"), settings_menu))
    application.add_handler(MessageHandler(filters.Regex("^📊 Statistika$"), show_stats))
    application.add_handler(MessageHandler(filters.Regex("^🌐 Tilni o'zgartirish$"), change_language))

    # ── Generic text handler (menu routing, must be last) ──────────────
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_text))

    return application


async def start_quiz_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to enter quiz topic."""
    await update.message.reply_text(
        "📝 Test yaratish uchun mavzu kiriting yoki fayl yuboring:"
    )
    return QUIZ_TOPIC


async def periodic_db_sync(sync_service: DatabaseSyncService, interval_seconds: int = 600):
    """Background loop that exports DB to channel every 10 minutes."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            logger.info("Executing periodic database sync to channel...")
            await sync_service.sync_to_channel(reason="Periodic Auto-Backup (10m)")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in periodic_db_sync: {e}")


# ── Main entry point ──────────────────────────────────────────────────────

async def main() -> None:
    """Start the bot and API server concurrently."""
    # Initialize database
    await init_db()
    logger.info("Local SQLite database initialized")

    # Build bot application
    application = build_application()

    # Initialize bot
    await application.initialize()

    # ── RESTORE DATABASE FROM TELEGRAM CHANNEL (IF BACKUP EXISTS) ───────────
    sync_service = DatabaseSyncService(bot=application.bot, channel_id=config.BACKUP_CHANNEL_ID)
    try:
        restored = await sync_service.restore_from_channel()
        if restored:
            logger.info("Database state successfully restored from Telegram channel!")
        else:
            logger.info("No prior channel backup applied. Using local state.")
    except Exception as e:
        logger.warning(f"Could not restore database from channel on boot: {e}")

    # Start bot
    if config.WEBHOOK_URL:
        logger.info(f"Starting webhook on {config.WEBHOOK_URL}")
        await application.bot.set_webhook(url=config.WEBHOOK_URL)
        await application.start()
    else:
        logger.info("Starting polling mode")
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        await application.start()

    # Set Mini App menu button
    try:
        if config.WEBAPP_URL:
            await application.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="📱 Mini App",
                    web_app=WebAppInfo(url=config.WEBAPP_URL),
                )
            )
    except Exception as e:
        logger.warning(f"Could not set menu button: {e}")

    # Initial backup on start
    asyncio.create_task(sync_service.sync_to_channel(reason="Service Startup Sync"))

    # Launch periodic backup background task
    sync_task = asyncio.create_task(periodic_db_sync(sync_service, interval_seconds=600))

    # Start FastAPI server
    logger.info(f"Starting API server on {config.API_HOST}:{config.API_PORT}")
    uvicorn_config = uvicorn.Config(
        "api.main:app",
        host=config.API_HOST,
        port=config.API_PORT,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)

    try:
        await server.serve()
    finally:
        logger.info("Shutting down... Performing final database sync to channel.")
        sync_task.cancel()
        try:
            await sync_service.sync_to_channel(reason="Service Graceful Shutdown Sync")
        except Exception as e:
            logger.error(f"Shutdown sync error: {e}")

        if not config.WEBHOOK_URL:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
