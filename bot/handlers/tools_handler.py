"""Tools Handler — Grade tables, attendance sheets, and other teacher tools."""

import io
import os
import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.config import get_settings
from bot.keyboards.reply import back_keyboard, main_menu_keyboard
from bot.processors.excel_processor import ExcelProcessor

logger = logging.getLogger(__name__)
config = get_settings()
excel_processor = ExcelProcessor()

# Conversation states
WAITING_STUDENTS = 0
WAITING_SUBJECTS = 1


async def tools_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show tools menu and ask for student names."""
    await update.message.reply_text(
        "📊 Baholar jadvali yaratish\n\n"
        "O'quvchilar ismlarini kiriting (har birini yangi qatordan yozing):\n\n"
        "Masalan:\n"
        "Ali Valiyev\n"
        "Vali Aliyev\n"
        "Guli Karimova",
        reply_markup=back_keyboard(),
    )
    return WAITING_STUDENTS


async def create_grade_table(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process student names or subjects and create grade table."""
    text = update.message.text.strip()

    if "students" not in context.user_data:
        # First input — student names
        students = [name.strip() for name in text.split("\n") if name.strip()]
        if not students:
            await update.message.reply_text("❌ Kamida bitta ism kiriting.")
            return WAITING_STUDENTS

        context.user_data["students"] = students
        await update.message.reply_text(
            f"✅ {len(students)} ta o'quvchi kiritildi.\n\n"
            "Endi fanlarni kiriting (vergul bilan ajrating):\n\n"
            "Masalan: Matematika, Fizika, Kimyo, Ingliz tili",
        )
        return WAITING_SUBJECTS
    else:
        # Second input — subjects
        subjects = [s.strip() for s in text.split(",") if s.strip()]
        if not subjects:
            await update.message.reply_text("❌ Kamida bitta fan kiriting.")
            return WAITING_SUBJECTS

        students = context.user_data.pop("students")
        msg = await update.message.reply_text("⏳ Baholar jadvali yaratilmoqda...")

        try:
            output_path = os.path.join(
                config.exports_dir,
                f"baholar_jadvali_{update.effective_user.id}.xlsx",
            )
            await excel_processor.create_grade_table(students, subjects, output_path)

            await msg.edit_text("✅ Baholar jadvali tayyor!")
            with open(output_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename="baholar_jadvali.xlsx",
                    caption=f"📊 Baholar jadvali\n👨‍🎓 {len(students)} o'quvchi\n📚 {len(subjects)} fan",
                )
        except Exception as e:
            logger.error(f"Grade table error: {e}")
            await msg.edit_text(f"❌ Xatolik: {str(e)}")

        await update.message.reply_text(
            "Yana biror narsa qilishni xohlaysizmi?",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END


async def create_attendance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create an attendance sheet."""
    msg = await update.message.reply_text("⏳ Davomat jadvali yaratilmoqda...")

    try:
        students = context.user_data.get("students", ["Ism kiriting"])
        days = [str(i) for i in range(1, 31)]

        output_path = os.path.join(
            config.exports_dir,
            f"davomat_{update.effective_user.id}.xlsx",
        )
        await excel_processor.create_grade_table(students, days, output_path)

        await msg.edit_text("✅ Davomat jadvali tayyor!")
        with open(output_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename="davomat_jadvali.xlsx",
                caption="📋 Davomat jadvali",
            )
    except Exception as e:
        logger.error(f"Attendance sheet error: {e}")
        await msg.edit_text(f"❌ Xatolik: {str(e)}")
