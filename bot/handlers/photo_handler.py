"""Photo Handler — Handles incoming photos and photo-related actions (3x4 document photos, print sheets)."""

import os
import io
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes

from bot.config import get_settings
from bot.processors.image_processor import ImageProcessor
from bot.utils.helpers import format_file_size

logger = logging.getLogger(__name__)
config = get_settings()
image_processor = ImageProcessor()


def photo_actions_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📸 3×4 Hujjat fotosi tayyorlash", callback_data="photo_process_3x4")],
        [InlineKeyboardButton("🖼️ PDF ga aylantirish", callback_data="photo_to_pdf")],
    ]
    if config.WEBAPP_URL:
        keyboard.append([
            InlineKeyboardButton("🎨 Mini App 3×4 Studiyada ochish", web_app=WebAppInfo(url=f"{config.WEBAPP_URL}#/?tool=photo3x4"))
        ])
    return InlineKeyboardMarkup(keyboard)


def photo_result_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    if config.WEBAPP_URL:
        keyboard.append([
            InlineKeyboardButton("🎨 Mini App Studiyada boshqarish", web_app=WebAppInfo(url=f"{config.WEBAPP_URL}#/?tool=photo3x4"))
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


async def execute_photo_3x4(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    input_path: str,
    bg_color: str = "#FFFFFF",
    change_bg: bool = False,
    add_corner: bool = False,
    status_msg = None
) -> None:
    """Process image into 3x4 portrait and 10x15 cm 6-photo print sheet and send directly to chat."""
    user = update.effective_user
    user_dir = os.path.join(config.processed_dir, str(user.id))
    os.makedirs(user_dir, exist_ok=True)

    timestamp = int(datetime.now().timestamp())
    single_name = f"hujjat_foto_3x4_{timestamp}.jpg"
    sheet_name = f"chop_etish_varaqasi_10x15_{timestamp}.jpg"
    single_path = os.path.join(user_dir, single_name)
    sheet_path = os.path.join(user_dir, sheet_name)

    if status_msg:
        try:
            await status_msg.edit_text("⏳ <b>3×4 Hujjat fotosi tayyorlanmoqda...</b>\n• Yuz mutanosibligi fokuslanmoqda\n• 300 DPI standart o'rnatilmoqda\n• 10×15 sm varaq shakllantirilmoqda", parse_mode="HTML")
        except Exception:
            pass
    else:
        status_msg = await update.effective_message.reply_text(
            "⏳ <b>3×4 Hujjat fotosi tayyorlanmoqda...</b>\n• Yuz mutanosibligi fokuslanmoqda\n• 300 DPI standart o'rnatilmoqda\n• 10×15 sm varaq shakllantirilmoqda",
            parse_mode="HTML"
        )

    try:
        stats = await image_processor.process_photo_3x4(
            input_path=input_path,
            output_single_path=single_path,
            output_sheet_path=sheet_path,
            bg_color_hex=bg_color,
            change_bg=change_bg,
            add_corner=add_corner,
            brightness=1.0,
            contrast=1.0,
            dpi=300
        )

        bg_label = "Oq (#FFFFFF)" if bg_color.upper() == "#FFFFFF" and change_bg else ("Ko'k (#4A90E2)" if bg_color.upper() in ("#4A90E2", "#0055A5") else ("Kulrang" if change_bg else "Asl fon saqlangan"))
        corner_label = "Mavjud (Doira kesma)" if add_corner else "Burchaksiz (Standart)"

        # 1. Send Single 3x4 photo document
        with open(single_path, "rb") as f_single:
            await update.effective_message.reply_document(
                document=f_single,
                filename="hujjat_foto_3x4.jpg",
                caption=(
                    "📸 <b>3×4 Hujjat Fotosi (Yakka format)</b>\n\n"
                    "✅ <b>O'lchami:</b> 30×40 mm (354×472 px, 3:4 nisbat)\n"
                    "💎 <b>Sifat:</b> 300 DPI (Bosma xalqaro standart)\n"
                    f"🎨 <b>Fon rangi:</b> {bg_label}\n"
                    f"📐 <b>Burchak:</b> {corner_label}\n\n"
                    "📌 <i>Pasport, viza, abituriyent (my.dtm.uz), talaba va haydovchilik guvohnomalariga 100% mos!</i>"
                ),
                parse_mode="HTML"
            )

        # 2. Send 10x15 cm print sheet document
        with open(sheet_path, "rb") as f_sheet:
            await update.effective_message.reply_document(
                document=f_sheet,
                filename="chop_etish_varaqasi_10x15_6ta.jpg",
                caption=(
                    "🖨️ <b>10×15 sm Chop Etish Varaqasi (6 ta Foto)</b>\n\n"
                    "✅ <b>Varaq o'lchami:</b> 10×15 sm (4×6 dyuym, 1181×1772 px, 300 DPI)\n"
                    "✂️ <b>Qulaylik:</b> Qaychi bilan qulay qirqish uchun kesish chiziqlari (crosshairs) mavjud\n"
                    "📸 <b>Miqdori:</b> Bir varaqda 6 dona 3×4 fotosurat\n\n"
                    "🖨️ <i>Istalgan fotoprinterda yoki fotosalonda ushbu faylni berib, arzon va sifatli chop ettirishingiz mumkin!</i>"
                ),
                reply_markup=photo_result_keyboard(),
                parse_mode="HTML"
            )

        try:
            await status_msg.delete()
        except Exception:
            pass

        # Backup to Channel -1003745209875 & Save to DB
        try:
            from bot.services.cloud_storage import get_cloud_storage
            cloud_storage = get_cloud_storage()

            single_file_id, single_msg_id = await cloud_storage.backup_file_to_channel(
                file_path=single_path,
                file_name=single_name,
                telegram_id=user.id,
                user_full_name=user.full_name or "",
                username=user.username or "",
                tool_name="Hujjat_Foto_3x4"
            )
            sheet_file_id, sheet_msg_id = await cloud_storage.backup_file_to_channel(
                file_path=sheet_path,
                file_name=sheet_name,
                telegram_id=user.id,
                user_full_name=user.full_name or "",
                username=user.username or "",
                tool_name="Foto_10x15_Varaq"
            )

            from bot.database.engine import get_session
            from bot.database import crud
            async with get_session() as session:
                db_user = await crud.get_or_create_user(session, user.id, user.full_name)
                await crud.save_file_record(
                    session=session,
                    user_id=db_user.id,
                    file_name=single_name,
                    file_type="jpg",
                    telegram_file_id=single_file_id or "",
                    local_path=single_path,
                    file_size=os.path.getsize(single_path),
                    channel_message_id=single_msg_id
                )
                await crud.save_file_record(
                    session=session,
                    user_id=db_user.id,
                    file_name=sheet_name,
                    file_type="jpg",
                    telegram_file_id=sheet_file_id or "",
                    local_path=sheet_path,
                    file_size=os.path.getsize(sheet_path),
                    channel_message_id=sheet_msg_id
                )
                await crud.log_usage(session, db_user.id, "photo_3x4", single_name)
        except Exception as dbe:
            logger.warning(f"Could not backup photo records to channel/DB: {dbe}")

    except Exception as e:
        logger.error(f"Error in execute_photo_3x4: {e}", exc_info=True)
        if status_msg:
            await status_msg.edit_text(f"❌ 3×4 Foto tayyorlashda xatolik yuz berdi: {str(e)}")
        else:
            await update.effective_message.reply_text(f"❌ Xatolik: {str(e)}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo sent by user."""
    if not update.message.photo:
        return

    photo = update.message.photo[-1]
    user = update.effective_user
    user_dir = os.path.join(config.upload_dir, str(user.id))
    os.makedirs(user_dir, exist_ok=True)

    timestamp = int(datetime.now().timestamp())
    local_path = os.path.join(user_dir, f"photo_{timestamp}.jpg")

    tg_file = await photo.get_file()
    await tg_file.download_to_drive(custom_path=local_path)

    context.user_data["last_photo"] = {
        "path": local_path,
        "file_id": photo.file_id,
        "file_size": photo.file_size or os.path.getsize(local_path),
        "width": photo.width,
        "height": photo.height
    }

    expected_tool = context.user_data.pop("expected_tool", None)

    if expected_tool == "photo_3x4":
        await execute_photo_3x4(update, context, input_path=local_path, bg_color="#FFFFFF", change_bg=False, add_corner=False)
    else:
        await update.message.reply_text(
            "📸 <b>Suratingiz qabul qilindi!</b>\n\n"
            "Ushbu suratdan qanday foydalanamiz?\n"
            "• <b>3×4 Hujjat fotosi</b> — Pasport/viza standarti (yakka va 6 talik varaq)\n"
            "• <b>PDF ga aylantirish</b> — A4 formatidagi PDF hujjat qilish\n"
            "• <b>Mini App</b> — Fon rangini (oq, ko'k) va parametrlarini sozlash",
            reply_markup=photo_actions_keyboard(),
            parse_mode="HTML"
        )


async def handle_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callbacks from photo buttons."""
    query = update.callback_query
    await query.answer()
    data = query.data

    photo_info = context.user_data.get("last_photo")
    if not photo_info or not os.path.exists(photo_info.get("path", "")):
        await query.message.reply_text(
            "⚠️ Surat ma'lumotlari topilmadi. Iltimos, fotosuratni qayta yuboring."
        )
        return

    input_path = photo_info["path"]

    if data == "photo_process_3x4":
        status_msg = await query.message.reply_text("⏳ Ishlanmoqda...")
        await execute_photo_3x4(update, context, input_path=input_path, bg_color="#FFFFFF", change_bg=False, add_corner=False, status_msg=status_msg)

    elif data == "photo_bg_white":
        status_msg = await query.message.reply_text("⏳ Oq fon bilan 3×4 foto tayyorlanmoqda...")
        await execute_photo_3x4(update, context, input_path=input_path, bg_color="#FFFFFF", change_bg=True, add_corner=False, status_msg=status_msg)

    elif data == "photo_bg_blue":
        status_msg = await query.message.reply_text("⏳ Ko'k fon bilan 3×4 foto tayyorlanmoqda...")
        await execute_photo_3x4(update, context, input_path=input_path, bg_color="#4A90E2", change_bg=True, add_corner=False, status_msg=status_msg)

    elif data == "photo_bg_gray":
        status_msg = await query.message.reply_text("⏳ Kulrang fon bilan 3×4 foto tayyorlanmoqda...")
        await execute_photo_3x4(update, context, input_path=input_path, bg_color="#E2E8F0", change_bg=True, add_corner=False, status_msg=status_msg)

    elif data == "photo_toggle_corner":
        status_msg = await query.message.reply_text("⏳ Burchakli (doira kesma) 3×4 foto tayyorlanmoqda...")
        await execute_photo_3x4(update, context, input_path=input_path, bg_color="#FFFFFF", change_bg=False, add_corner=True, status_msg=status_msg)

    elif data == "photo_to_pdf":
        status_msg = await query.message.reply_text("⏳ Rasm A4 PDF ga aylantirilmoqda...")
        try:
            from PIL import Image
            pdf_path = input_path.rsplit(".", 1)[0] + "_document.pdf"
            with Image.open(input_path) as im:
                im_rgb = im.convert("RGB")
                im_rgb.save(pdf_path, "PDF", resolution=100.0)

            with open(pdf_path, "rb") as f_pdf:
                await query.message.reply_document(
                    document=f_pdf,
                    filename="surat_hujjat.pdf",
                    caption="📄 <b>Surat PDF formatiga o'tkazildi!</b>\n\nBosmaga yoki rasmiy topshirishga tayyor.",
                    parse_mode="HTML"
                )
            await status_msg.delete()
        except Exception as err:
            await status_msg.edit_text(f"❌ Xatolik: {err}")
