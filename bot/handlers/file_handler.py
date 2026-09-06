"""File Handler — Handles file uploads and file-related inline button actions."""

import io
import os
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import get_settings
from bot.keyboards.inline import file_actions_keyboard
from bot.keyboards.reply import main_menu_keyboard
from bot.processors import get_processor
from bot.processors.converter import FileConverter
from bot.services.ai_service import AIService
from bot.utils.helpers import format_file_size, get_file_extension, generate_unique_filename

logger = logging.getLogger(__name__)
config = get_settings()
ai_service = AIService(api_key=config.GEMINI_API_KEY)
converter = FileConverter()


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming document uploads."""
    document = update.message.document

    # Check file size (20 MB limit for Telegram Bot API downloads)
    if document.file_size > 20 * 1024 * 1024:
        await update.message.reply_text(
            "❌ Fayl hajmi 20 MB dan oshmasligi kerak.\n"
            f"Sizning faylingiz: {format_file_size(document.file_size)}"
        )
        return

    # Get file extension
    file_name = document.file_name or "unknown"
    ext = get_file_extension(file_name).lower()
    supported = {".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".csv"}

    if f".{ext}" not in supported and ext not in [e.lstrip('.') for e in supported]:
        await update.message.reply_text(
            "❌ Bu fayl formati qo'llab-quvvatlanmaydi.\n"
            "Qo'llab-quvvatlanadigan formatlar: PDF, Word, Excel, PowerPoint, CSV"
        )
        return

    msg = await update.message.reply_text("⏳ Fayl yuklanmoqda...")

    try:
        # Download file
        tg_file = await document.get_file()
        user_dir = os.path.join(config.upload_dir, str(update.effective_user.id))
        os.makedirs(user_dir, exist_ok=True)

        local_filename = generate_unique_filename(file_name)
        local_path = os.path.join(user_dir, local_filename)
        await tg_file.download_to_drive(custom_path=local_path)

        # Determine file type for display
        ext_lower = get_file_extension(file_name).lower().lstrip(".")
        type_map = {
            "pdf": "PDF",
            "docx": "Word",
            "doc": "Word",
            "xlsx": "Excel",
            "xls": "Excel",
            "pptx": "PowerPoint",
            "ppt": "PowerPoint",
            "csv": "CSV",
        }
        file_type = type_map.get(ext_lower, ext_lower.upper())

        # Store file info in user context
        context.user_data["last_file"] = {
            "path": local_path,
            "type": ext_lower,
            "name": file_name,
            "size": document.file_size,
            "telegram_file_id": document.file_id,
        }

        # Save record in database
        try:
            from bot.database.engine import get_session
            from bot.database import crud
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, update.effective_user.id, update.effective_user.full_name)
                await crud.save_file_record(
                    session=session,
                    user_id=db_user.id,
                    file_name=file_name,
                    file_type=ext_lower,
                    telegram_file_id=document.file_id,
                    local_path=local_path,
                    file_size=document.file_size
                )
                await crud.log_usage(session, db_user.id, "upload_file", file_name)
        except Exception as dbe:
            logger.warning(f"Could not persist file record to DB: {dbe}")

        # Get processor and metadata
        processor = get_processor(local_path)
        meta_text = ""
        if processor:
            try:
                metadata = await processor.get_metadata(local_path)
                if metadata.page_count:
                    meta_text += f"📄 Sahifalar: {metadata.page_count}\n"
                if metadata.word_count:
                    meta_text += f"📝 So'zlar: {metadata.word_count}\n"
            except Exception:
                pass

        expected_tool = context.user_data.pop("expected_tool", None)
        if expected_tool == "pdf_to_word" and ext_lower == "pdf":
            await msg.edit_text("⏳ PDF ni Word (DOCX) ga aylantirish boshlandi...")
            await _convert_to_docx(msg, update, local_path, file_name)
            return
        elif expected_tool == "word_to_pdf" and ext_lower in ("docx", "doc"):
            await msg.edit_text("⏳ Word ni PDF ga aylantirish boshlandi...")
            await _convert_to_pdf(msg, update, local_path, file_name)
            return
        elif expected_tool == "extract_images" and ext_lower == "pdf":
            await msg.edit_text("⏳ PDF dagi barcha rasmlar ajratilmoqda...")
            await _extract_images(msg, update, local_path, file_name)
            return

        info_text = (
            f"✅ Fayl qabul qilindi!\n\n"
            f"📄 Nomi: {file_name}\n"
            f"📊 Hajmi: {format_file_size(document.file_size)}\n"
            f"📁 Turi: {file_type}\n"
            f"{meta_text}\n"
            f"Qanday amal bajaramiz?"
        )
        await msg.edit_text(info_text, reply_markup=file_actions_keyboard(ext_lower))

    except Exception as e:
        logger.error(f"File handling error: {e}")
        await msg.edit_text(f"❌ Faylni yuklab olishda xatolik: {str(e)}")


async def handle_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button callbacks for file actions."""
    query = update.callback_query
    await query.answer()

    action = query.data
    file_info = context.user_data.get("last_file")

    if not file_info:
        await query.message.reply_text(
            "⚠️ Fayl ma'lumotlari topilmadi. Iltimos, faylni qayta yuboring.",
            reply_markup=main_menu_keyboard(),
        )
        return

    file_path = file_info["path"]
    file_type = file_info["type"]
    file_name = file_info["name"]

    msg = await query.message.reply_text("⏳ Ishlanmoqda...")

    try:
        if action == "file_extract_text":
            await _extract_text(msg, query, file_path)

        elif action == "file_ai_analyze":
            await _ai_analyze(msg, query, file_path)

        elif action == "file_to_docx":
            await _convert_to_docx(msg, query, file_path, file_name)

        elif action == "file_extract_images":
            await _extract_images(msg, query, file_path, file_name)

        elif action == "file_to_pdf":
            await _convert_to_pdf(msg, query, file_path, file_name)

        elif action == "file_to_csv":
            await _convert_to_csv(msg, query, file_path, file_name)

        elif action == "file_stats":
            await _show_stats(msg, query, file_path)

        elif action == "file_split":
            await msg.edit_text(
                "✂️ Qaysi sahifalarni ajratmoqchisiz?\n"
                "Boshlanish va tugash sahifasini kiriting.\n"
                "Format: 1-5\n\n"
                "(Bu funksiya faqat PDF fayllar uchun ishlaydi)"
            )

        elif action == "file_merge":
            context.user_data["merge_mode"] = True
            context.user_data["merge_files"] = [file_path]
            await msg.edit_text(
                "🔗 Birlashtirish rejimi yoqildi!\n"
                "Yana PDF fayllar yuboring. Tayyor bo'lganda /merge buyrug'ini yuboring."
            )

        elif action == "file_protect":
            await msg.edit_text(
                "🔒 PDF ga parol o'rnatish.\n"
                "Iltimos, parolni kiriting:"
            )
            context.user_data["awaiting_password"] = True

        elif action == "file_replace":
            await msg.edit_text(
                "✏️ Matn almashtirish (faqat Word fayllar).\n"
                "Formatni kiriting: eski_soz -> yangi_soz\n"
                "Masalan: salom -> hello"
            )

        elif action == "file_quiz":
            await _generate_quiz_from_file(msg, query, file_path, context)

        else:
            await msg.edit_text("⚠️ Noma'lum amal tanlandi.")

    except Exception as e:
        logger.error(f"File callback error: {e}")
        await msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")


# ── Private helper functions ───────────────────────────────────────────────

async def _extract_text(msg, query, file_path: str) -> None:
    """Extract text from file and send to user."""
    processor = get_processor(file_path)
    if not processor:
        await msg.edit_text("❌ Bu fayl turi uchun matn ajratish mumkin emas.")
        return

    text = await processor.extract_text(file_path)
    if not text or not text.strip():
        await msg.edit_text("⚠️ Faylda matn topilmadi.")
        return

    if len(text) <= 4000:
        await msg.edit_text(f"📖 Ajratilgan matn:\n\n{text}")
    else:
        # Send as a .txt file
        text_bytes = text.encode("utf-8")
        text_file = io.BytesIO(text_bytes)
        text_file.name = "extracted_text.txt"
        await msg.edit_text("📖 Matn juda uzun, fayl sifatida yuborilmoqda...")
        await query.message.reply_document(
            document=text_file,
            filename="extracted_text.txt",
            caption=f"📖 Fayldan ajratilgan matn ({len(text)} belgi)",
        )


async def _ai_analyze(msg, query, file_path: str) -> None:
    """Analyze file content with AI."""
    processor = get_processor(file_path)
    if not processor:
        await msg.edit_text("❌ Bu fayl turini tahlil qilish mumkin emas.")
        return

    text = await processor.extract_text(file_path)
    if not text or not text.strip():
        await msg.edit_text("⚠️ Faylda matn topilmadi. AI tahlil qila olmaydi.")
        return

    await msg.edit_text("🧠 AI tahlil qilmoqda...")
    result = await ai_service.analyze_document(text)

    full = f"🧠 AI tahlil natijasi:\n\n{result}"
    if len(full) > 4096:
        chunks = [full[i:i + 4096] for i in range(0, len(full), 4096)]
        await msg.edit_text(chunks[0])
        for chunk in chunks[1:]:
            await query.message.reply_text(chunk)
    else:
        await msg.edit_text(full)


async def _convert_to_docx(msg, query_or_update, file_path: str, file_name: str) -> None:
    """Convert PDF to DOCX (Word)."""
    output_path = os.path.join(
        config.processed_dir,
        os.path.splitext(os.path.basename(file_name))[0] + ".docx",
    )
    reply_target = query_or_update.message if hasattr(query_or_update, "message") and query_or_update.message else msg
    try:
        await converter.pdf_to_word(file_path, output_path)
        await msg.edit_text("✅ Word (DOCX) ga aylantirildi!")
        with open(output_path, "rb") as f:
            await reply_target.reply_document(
                document=f,
                filename=os.path.basename(output_path),
                caption="📝 Word (DOCX) hujjati tayyor!",
            )
    except Exception as e:
        await msg.edit_text(f"❌ Word ga aylantirishda xatolik: {str(e)}")


async def _extract_images(msg, query_or_update, file_path: str, file_name: str) -> None:
    """Extract all images from PDF into a ZIP file."""
    import fitz
    import zipfile
    
    zip_name = f"{os.path.splitext(os.path.basename(file_name))[0]}_rasmlar.zip"
    zip_path = os.path.join(config.processed_dir, zip_name)
    reply_target = query_or_update.message if hasattr(query_or_update, "message") and query_or_update.message else msg
    
    try:
        doc = fitz.open(file_path)
        img_count = 0
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                image_list = page.get_images(full=True)
                for img_idx, img_info in enumerate(image_list):
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    img_filename = f"sahifa_{page_idx+1}_rasm_{img_idx+1}.{image_ext}"
                    zipf.writestr(img_filename, image_bytes)
                    img_count += 1
        doc.close()

        if img_count == 0:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            await msg.edit_text("⚠️ Ushbu PDF ichida hech qanday rasm topilmadi.")
            return

        await msg.edit_text(f"✅ {img_count} ta rasm ajratib olindi!")
        with open(zip_path, "rb") as f:
            await reply_target.reply_document(
                document=f,
                filename=zip_name,
                caption=f"🖼️ PDF dagi {img_count} ta rasm arxivi (ZIP)",
            )
    except Exception as e:
        await msg.edit_text(f"❌ Rasmlarni ajratishda xatolik: {str(e)}")


async def _convert_to_pdf(msg, query_or_update, file_path: str, file_name: str) -> None:
    """Convert file to PDF."""
    output_dir = config.processed_dir
    reply_target = query_or_update.message if hasattr(query_or_update, "message") and query_or_update.message else msg
    try:
        output_path = await converter.convert_to_pdf(file_path, output_dir)
        await msg.edit_text("✅ PDF ga aylantirildi!")
        with open(output_path, "rb") as f:
            pdf_name = os.path.splitext(file_name)[0] + ".pdf"
            await reply_target.reply_document(
                document=f,
                filename=pdf_name,
                caption="📄 Konvertatsiya qilingan PDF fayl",
            )
    except Exception as e:
        await msg.edit_text(f"❌ Konvertatsiya xatosi: {str(e)}")


async def _convert_to_csv(msg, query, file_path: str, file_name: str) -> None:
    """Convert Excel to CSV."""
    output_path = os.path.join(
        config.processed_dir,
        os.path.splitext(os.path.basename(file_name))[0] + ".csv",
    )
    try:
        result = await converter.excel_to_csv(file_path, output_path)
        await msg.edit_text("✅ CSV ga aylantirildi!")
        with open(result, "rb") as f:
            await query.message.reply_document(
                document=f,
                filename=os.path.basename(result),
                caption="📋 CSV fayl",
            )
    except Exception as e:
        await msg.edit_text(f"❌ Konvertatsiya xatosi: {str(e)}")


async def _show_stats(msg, query, file_path: str) -> None:
    """Show Excel statistics."""
    from bot.processors.excel_processor import ExcelProcessor

    processor = ExcelProcessor()
    try:
        stats = await processor.calculate_stats(file_path)
        text = "📊 Statistika:\n\n"
        for col_name, col_stats in stats.items():
            text += f"📌 {col_name}:\n"
            for key, value in col_stats.items():
                text += f"  • {key}: {value}\n"
            text += "\n"
        await msg.edit_text(text if text.strip() != "📊 Statistika:" else "⚠️ Raqamli ma'lumotlar topilmadi.")
    except Exception as e:
        await msg.edit_text(f"❌ Statistika olishda xatolik: {str(e)}")


async def _generate_quiz_from_file(msg, query, file_path: str, context) -> None:
    """Generate quiz from file content."""
    processor = get_processor(file_path)
    if not processor:
        await msg.edit_text("❌ Bu fayl turidan test yaratish mumkin emas.")
        return

    text = await processor.extract_text(file_path)
    if not text or not text.strip():
        await msg.edit_text("⚠️ Faylda matn topilmadi.")
        return

    await msg.edit_text("🧠 AI test yaratmoqda (10 ta savol)...")
    questions = await ai_service.generate_quiz(text, num_questions=10, quiz_type="multiple")

    # Format and send
    result = "📝 Yaratilgan test:\n\n"
    for i, q in enumerate(questions, 1):
        result += f"{i}. {q.get('question', '')}\n"
        options = q.get("options", [])
        for j, opt in enumerate(options):
            letter = chr(65 + j)  # A, B, C, D
            result += f"   {letter}) {opt}\n"
        result += f"   ✅ Javob: {q.get('correct_answer', '')}\n\n"

    if len(result) > 4096:
        chunks = [result[i:i + 4096] for i in range(0, len(result), 4096)]
        await msg.edit_text(chunks[0])
        for chunk in chunks[1:]:
            await query.message.reply_text(chunk)
    else:
        await msg.edit_text(result)

    # Store quiz for export
    context.user_data["last_quiz"] = questions
