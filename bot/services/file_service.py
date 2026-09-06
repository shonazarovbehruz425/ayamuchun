import os
import time

async def save_uploaded_file(bot, document, user_id) -> tuple[str, str]:
    file = await bot.get_file(document.file_id)
    ext = document.file_name.split('.')[-1] if '.' in document.file_name else ''
    os.makedirs('storage/uploads', exist_ok=True)
    local_path = f"storage/uploads/{user_id}_{int(time.time())}.{ext}"
    await file.download_to_drive(local_path)
    return local_path, ext.lower()

def cleanup_old_files(days=7):
    # Logic to remove files older than 7 days
    pass

def get_file_info(file_path) -> dict:
    return {
        "size": os.path.getsize(file_path),
        "path": file_path
    }
