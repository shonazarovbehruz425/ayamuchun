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

def parse_lesson_subject_topic(text: str) -> tuple[str, str]:
    """
    Parse subject and topic from text safely.
    Handles '5-sinf Matematika - Kasrlar' without breaking hyphenated grades.
    Looks for space-padded dashes or em-dashes (' - ', ' — ', ' – ') or colons (': ').
    """
    clean = text.strip()
    # 1. Try dash/em-dash with spaces around it
    parts = re.split(r'\s+[—–-]\s+', clean, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()

    # 2. Try colon with space
    parts = re.split(r':\s+', clean, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()

    # 3. Try em-dash or en-dash without spaces
    parts = re.split(r'[—–]', clean, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()

    # Fallback: Default subject "Umumiy"
    return "Umumiy", clean

def split_html_message(html_text: str, max_len: int = 3800) -> list[str]:
    """
    Splits text or HTML into message-safe chunks avoiding splitting inside tags.
    Tries splitting on double newlines, then newlines, then spaces.
    """
    if len(html_text) <= max_len:
        return [html_text]

    chunks = []
    remaining = html_text.strip()

    while len(remaining) > max_len:
        # Try finding a split point: \n\n first
        split_idx = remaining.rfind("\n\n", 0, max_len)
        if split_idx == -1 or split_idx < max_len // 3:
            # Try single newline
            split_idx = remaining.rfind("\n", 0, max_len)
        if split_idx == -1 or split_idx < max_len // 3:
            # Try space
            split_idx = remaining.rfind(" ", 0, max_len)
        if split_idx == -1 or split_idx < max_len // 3:
            # Fallback hard split
            split_idx = max_len

        chunk = remaining[:split_idx].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_idx:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks

