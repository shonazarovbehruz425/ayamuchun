"""File Handler — Handles file uploads and file-related inline button actions."""

import io
import os
import time
import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from bot.config import get_settings
from bot.keyboards.inline import file_actions_keyboard
from bot.keyboards.reply import main_menu_keyboard
from bot.processors import get_processor
from bot.processors.converter import FileConverter
from bot.services.ai_service import AIService
from bot.utils.helpers import format_file_size, get_file_extension, generate_unique_filename, clean_ai_markdown_for_telegram, split_html_message

from bot.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)
config = get_settings()
ai_service = get_ai_service()
converter = FileConverter()


async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming document uploads."""
    expected_tool = context.user_data.pop("expected_tool", None)
    context.user_data.pop("ai_action", None)
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
    raw_ext = get_file_extension(file_name).lower().strip()
    ext_with_dot = raw_ext if raw_ext.startswith('.') else f".{raw_ext}"
    ext_clean = ext_with_dot.lstrip('.')
    supported = {".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".csv", ".jpg", ".jpeg", ".png", ".webp"}

    if ext_with_dot not in supported and ext_clean not in [e.lstrip('.') for e in supported]:
        await update.message.reply_text(
            "❌ Bu fayl formati qo'llab-quvvatlanmaydi.\n"
            "Qo'llab-quvvatlanadigan formatlar: PDF, Word, Excel, PowerPoint, CSV, Rasm (JPG, PNG)"
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

        # Save record in database and backup to cloud storage channel
        try:
            from bot.database.engine import get_session
            from bot.database import crud
            from bot.services.cloud_storage import get_cloud_storage
            cloud_storage = get_cloud_storage()
            chan_file_id, chan_msg_id = await cloud_storage.backup_file_to_channel(
                file_path=local_path,
                file_name=file_name,
                telegram_id=update.effective_user.id,
                user_full_name=update.effective_user.full_name or "",
                username=update.effective_user.username or "",
                tool_name="Telegram_Fayl_Yuklash"
            )
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, update.effective_user.id, update.effective_user.full_name)
                await crud.save_file_record(
                    session=session,
                    user_id=db_user.id,
                    file_name=file_name,
                    file_type=ext_lower,
                    telegram_file_id=chan_file_id or document.file_id,
                    local_path=local_path,
                    file_size=document.file_size,
                    channel_message_id=chan_msg_id
                )
                await crud.log_usage(session, db_user.id, "upload_file", file_name)
        except Exception as dbe:
            logger.warning(f"Could not persist file record or backup to DB: {dbe}")

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

        if ext_lower in ("jpg", "jpeg", "png", "webp"):
            from bot.handlers.photo_handler import execute_photo_3x4, photo_batch_keyboard
            photo_item = {
                "path": local_path,
                "file_id": document.file_id,
                "file_size": document.file_size,
                "time": time.time(),
                "media_group_id": update.message.media_group_id if update.message else None
            }
            batch = context.user_data.get("photo_batch", [])
            now = time.time()
            if batch and (now - batch[-1].get("time", 0) > 4.0):
                batch = []
            if update.message and update.message.media_group_id:
                if batch and batch[-1].get("media_group_id") != update.message.media_group_id:
                    batch = []

            batch.append(photo_item)
            context.user_data["photo_batch"] = batch
            context.user_data["last_photo"] = photo_item

            if expected_tool == "photo_3x4":
                await execute_photo_3x4(update, context, input_path=local_path, bg_color="#FFFFFF", change_bg=False, add_corner=False, status_msg=msg)
                return

            current_token = context.user_data.get("photo_batch_token", 0) + 1
            context.user_data["photo_batch_token"] = current_token

            await asyncio.sleep(1.2)

            if context.user_data.get("photo_batch_token") != current_token:
                try:
                    await msg.delete()
                except Exception:
                    pass
                return

            collected = context.user_data.get("photo_batch", [photo_item])
            count = len(collected)
            context.user_data["waiting_photo_intent"] = True

            if count > 1:
                text = (
                    f"📸 <b>{count} ta rasm qabul qilindi!</b>\n\n"
                    "Ushbu rasmlar bilan nima qilmoqchisiz?\n\n"
                    "Mavjud imkoniyatlar:\n"
                    f"• <b>PDF yaratish</b> — Barcha {count} ta rasmni bitta sifatli PDF hujjatga birlashtirish\n"
                    "• <b>3×4 Hujjat fotosi</b> — Rasmlardan 3×4 hujjat fotosi tayyorlash\n"
                    "• <b>Matnni olish (OCR / AI)</b> — Rasmlardagi yozuvlarni matnga aylantirish\n"
                    "• <b>Fonini almashtirish</b> — Rasmlar fonini oq yoki ko'k rangga o'tkazish\n\n"
                    "✍️ <i>Iltimos, nima qilish kerakligini yozing (masalan: «Barchasini bitta PDF qil», «PDF ga aylantir», «3x4 qil» yoki o'zingiz xohlagan vazifani ayting):</i>"
                )
            else:
                text = (
                    "📸 <b>Suratingiz qabul qilindi!</b>\n\n"
                    "Ushbu rasm bilan nima qilmoqchisiz?\n\n"
                    "Mavjud imkoniyatlar:\n"
                    "• <b>3×4 Hujjat fotosi</b> — Pasport yoki viza uchun foto va 6 talik chop etish varag'i\n"
                    "• <b>PDF ga aylantirish</b> — A4 formatidagi toza PDF hujjat qilish\n"
                    "• <b>Rasm ichidagi matnni olish (OCR / AI tahlil)</b> — Rasmdagi yozuvlarni matnga aylantirish yoki tahlil qilish\n"
                    "• <b>Fonini almashtirish</b> — Oq, ko'k yoki kulrang fonga o'tkazish\n\n"
                    "✍️ <i>Iltimos, nima qilish kerakligini yozing (masalan: «3x4 qilib ber», «PDF qil», «matnini ol» yoki o'zingiz xohlagan vazifani ayting):</i>"
                )

            await msg.edit_text(text, reply_markup=photo_batch_keyboard(count), parse_mode="HTML")
            return

        caption = (update.message.caption or "").lower().strip() if update.message else ""
        has_word_intent = any(k in caption for k in ["doc", "docx", "word", "vord", "wordga", "word qil", "doc qil", "docx qil"])
        has_pdf_intent = any(k in caption for k in ["pdf", "pdfga", "pdf qil"])
        has_img_intent = any(k in caption for k in ["rasm", "rasmlar", "ajrat", "rasmini ol", "extract"])

        if (expected_tool == "pdf_to_word" or has_word_intent) and ext_lower in ("pdf", "xlsx", "xls", "xlsm"):
            await msg.edit_text("⏳ Word (DOCX) ga aylantirish boshlandi...")
            await _convert_to_docx(msg, update, local_path, file_name)
            return
        elif (expected_tool == "word_to_pdf" or has_pdf_intent) and ext_lower in ("docx", "doc", "xlsx", "xls", "xlsm"):
            await msg.edit_text("⏳ PDF ga aylantirish boshlandi...")
            await _convert_to_pdf(msg, update, local_path, file_name)
            return
        elif (expected_tool == "extract_images" or has_img_intent) and ext_lower == "pdf":
            await msg.edit_text("⏳ PDF dagi barcha rasmlar ajratilmoqda...")
            await _extract_images(msg, update, local_path, file_name)
            return
        elif expected_tool == "photo_3x4":
            from bot.handlers.photo_handler import execute_photo_3x4
            await execute_photo_3x4(update, context, input_path=local_path, bg_color="#FFFFFF", change_bg=False, add_corner=False, status_msg=msg)
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

        elif action == "file_compress":
            await _compress_pdf(msg, query, file_path, file_name)

        elif action == "file_watermark":
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
            keyboard = []
            if config.WEBAPP_URL:
                keyboard.append([
                    InlineKeyboardButton("🟦 Suv belgisini Mini App'da sozlash", web_app=WebAppInfo(url=f"{config.WEBAPP_URL}#/?tool=watermark"))
                ])
            await msg.edit_text(
                "🟦 <b>PDF Suv belgisi (Watermark)</b>\n\n"
                "Matn yoki logotipni aniq shaffoflik va burchak bilan joylashtirish uchun quyidagi Mini App asbobidan foydalaning:",
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                parse_mode="HTML"
            )

        elif action == "file_split":
            keyboard = []
            if config.WEBAPP_URL:
                keyboard.append([
                    InlineKeyboardButton("🟧 Sahifalarni Mini App'da ajratish", web_app=WebAppInfo(url=f"{config.WEBAPP_URL}#/?tool=split"))
                ])
            await msg.edit_text(
                "🟧 <b>PDF Bo'lish (Sahifalarni ajratish)</b>\n\n"
                "Qaysi sahifalarni ajratmoqchisiz? Oraliqni kiriting (masalan: 1-5 yoki 1,3,7), yoki Mini App'da vizual ko'ring:",
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                parse_mode="HTML"
            )

        elif action == "file_merge":
            context.user_data["merge_mode"] = True
            context.user_data["merge_files"] = [file_path]
            keyboard = []
            if config.WEBAPP_URL:
                keyboard.append([
                    InlineKeyboardButton("🟥 Mini App'da erkin birlashtirish", web_app=WebAppInfo(url=f"{config.WEBAPP_URL}#/?tool=merge"))
                ])
            await msg.edit_text(
                "🟥 <b>Birlashtirish rejimi yoqildi!</b>\n\n"
                "Birlashtirish uchun yana PDF fayllar yuboring. Tayyor bo'lganda /merge buyrug'ini yuboring yoki Mini App'da oching:",
                reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                parse_mode="HTML"
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

    clean_result = clean_ai_markdown_for_telegram(result)
    full = f"🧠 <b>AI tahlil natijasi:</b>\n\n{clean_result}"
    chunks = split_html_message(full, max_len=3800)
    try:
        await msg.edit_text(chunks[0], parse_mode="HTML")
    except Exception:
        await msg.edit_text(chunks[0])
    for chunk in chunks[1:]:
        try:
            await query.message.reply_text(chunk, parse_mode="HTML")
        except Exception:
            await query.message.reply_text(chunk)


async def _convert_to_docx(msg, query_or_update, file_path: str, file_name: str) -> None:
    """Convert PDF or Excel to DOCX (Word)."""
    output_path = os.path.join(
        config.processed_dir,
        os.path.splitext(os.path.basename(file_name))[0] + ".docx",
    )
    reply_target = query_or_update.message if hasattr(query_or_update, "message") and query_or_update.message else msg
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext in (".xlsx", ".xls", ".xlsm"):
            await converter.excel_to_word(file_path, output_path)
            await msg.edit_text("✅ Excel jadvali Word (DOCX) ga aylantirildi!")
            caption_text = "📊 Excel jadvali asosida Word (DOCX) hujjati tayyorlandi!"
        else:
            await converter.pdf_to_word(file_path, output_path)
            await msg.edit_text("✅ Word (DOCX) ga aylantirildi!")
            caption_text = "📝 Word (DOCX) hujjati tayyor!"

        with open(output_path, "rb") as f:
            await reply_target.reply_document(
                document=f,
                filename=os.path.basename(output_path),
                caption=caption_text,
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


async def _compress_pdf(msg, query_or_update, file_path: str, file_name: str) -> None:
    """Compress PDF file and send back to user."""
    from bot.processors.pdf_processor import PDFProcessor
    output_path = os.path.join(
        config.processed_dir,
        os.path.splitext(os.path.basename(file_name))[0] + "_siqilgan.pdf",
    )
    reply_target = query_or_update.message if hasattr(query_or_update, "message") and query_or_update.message else msg
    try:
        proc = PDFProcessor()
        res = await proc.compress_pdf(file_path, output_path, quality_level="medium")
        saved_pct = res.get("saved_percent", 0)
        orig_mb = res.get("original_size", 0) / (1024 * 1024)
        comp_mb = res.get("compressed_size", 0) / (1024 * 1024)
        await msg.edit_text(f"✅ PDF muvaffaqiyatli siqildi! ({saved_pct}% hajm tejaldi)")
        with open(output_path, "rb") as f:
            await reply_target.reply_document(
                document=f,
                filename=os.path.basename(output_path),
                caption=(
                    f"🟪 <b>PDF siqish natijasi:</b>\n\n"
                    f"📦 Asl hajm: <b>{orig_mb:.2f} MB</b>\n"
                    f"✨ Yangi hajm: <b>{comp_mb:.2f} MB</b>\n"
                    f"📉 Tejaldi: <b>{saved_pct}%</b>\n\n"
                    f"⚡ <i>EduBot orqali tayyorlandi</i>"
                ),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Compress PDF error: {e}")
        await msg.edit_text(f"❌ PDF siqishda xatolik: {str(e)}")


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
    """Show Excel / CSV statistics."""
    from bot.processors.excel_processor import ExcelProcessor

    processor = ExcelProcessor()
    try:
        stats = await processor.calculate_stats(file_path)
        if not stats:
            await msg.edit_text("⚠️ Raqamli ma'lumotlar topilmadi.")
            return

        text = "📊 <b>Statistika:</b>\n\n"

        # Check if stats is a nested dict of columns or a single flat dict
        first_val = next(iter(stats.values())) if stats else None
        if isinstance(first_val, dict):
            for col_name, col_stats in stats.items():
                text += f"📌 <b>{col_name}</b>:\n"
                for key, value in col_stats.items():
                    text += f"  • {key}: <code>{value}</code>\n"
                text += "\n"
        else:
            # Flat dictionary
            for key, value in stats.items():
                text += f"  • {key}: <code>{value}</code>\n"

        await msg.edit_text(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in _show_stats: {e}")
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
