import os
import uuid
import re
from datetime import datetime

def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()

def get_file_type_emoji(file_type: str) -> str:
    emojis = {
        '.pdf': '📄',
        '.docx': '📝',
        '.doc': '📝',
        '.xlsx': '📊',
        '.xls': '📊',
        '.pptx': '🗂️',
        '.ppt': '🗂️',
        '.csv': '📈'
    }
    return emojis.get(file_type, '📁')

def format_file_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def is_supported_file(filename: str) -> bool:
    from bot.utils.validators import SUPPORTED_EXTENSIONS
    ext = get_file_extension(filename)
    return ext in SUPPORTED_EXTENSIONS

def generate_unique_filename(original: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    name, ext = os.path.splitext(original)
    sanitized_name = sanitize_filename(name)
    return f"{sanitized_name}_{timestamp}_{unique_id}{ext}"

def sanitize_filename(filename: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', filename)

def truncate_text(text: str, max_length: int = 4096) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
