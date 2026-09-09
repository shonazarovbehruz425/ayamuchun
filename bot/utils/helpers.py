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
    if not filename:
        return "file"
    sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', filename)
    if not sanitized or not sanitized.strip('_-'):
        return "file"
    return sanitized[:100]

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


def clean_ai_markdown_for_telegram(text: str) -> str:
    """
    Safely convert AI raw Markdown into clean Telegram HTML entities.
    - Removes raw markdown artifacts like **, ##, ***, __, etc.
    - Cleans up excessive blank lines / whitespace ('bosh joy').
    - Preserves code blocks as <pre><code>.
    - Preserves existing valid Telegram HTML tags (<b>, <i>, etc.).
    - Converts bullet lists cleanly (• and ▫️).
    - Safely escapes raw angle brackets (<, >) and ampersands (&) to prevent parse errors.
    """
    if not text:
        return ""

    import html as html_lib

    # 1. Normalize line breaks
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Extract and protect code blocks
    code_blocks = []
    def save_code_block(match):
        lang = match.group(1) or ""
        code = match.group(2)
        idx = len(code_blocks)
        code_blocks.append(html_lib.escape(code.strip("\n"), quote=False))
        return f"QQQCODEBLOCK{idx}QQQ"

    text = re.sub(r"```(\w*)\n?(.*?)```", save_code_block, text, flags=re.DOTALL)

    # 2b. Extract and preserve existing valid Telegram HTML tags
    valid_tags = []
    def save_valid_tag(match):
        idx = len(valid_tags)
        valid_tags.append(match.group(0))
        return f"QQQVALIDTAG{idx}QQQ"

    tag_pattern = r"</?(?:b|strong|i|em|u|ins|s|strike|del|code|pre|blockquote)(?:\s+[^>]*?)?>|<a\s+href=\"[^\"]+\">|</a>"
    text = re.sub(tag_pattern, save_valid_tag, text, flags=re.IGNORECASE)

    # 3. HTML escape raw text (<, >, & only; preserve quotes and apostrophes like o'zbek)
    text = html_lib.escape(text, quote=False)

    # 4. Headings: # Heading, ## Heading, ### Heading -> <b>Heading</b>
    text = re.sub(r"^[ \t]*#{1,6}[ \t]*(.+?)[ \t]*$", r"<b>\1</b>", text, flags=re.MULTILINE)

    # 5. Bold & Italic: ***text*** -> <b><i>text</i></b>
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", text)
    text = re.sub(r"___(.+?)___", r"<b><i>\1</i></b>", text)

    # 6. Bold: **text** or __text__ -> <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)__(.+?)__(?!\w)", r"<b>\1</b>", text)

    # 7. Italic: *text* or _text_ -> <i>text</i>
    text = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_\n]+?)_(?!\w)", r"<i>\1</i>", text)

    # 8. Inline code: `code` -> <code>code</code>
    text = re.sub(r"`([^`\n]+?)`", r"<code>\1</code>", text)

    # 9. Strikethrough: ~~text~~ -> <s>text</s>
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 10. Horizontal rules: --- or *** or ___ -> ──────────
    text = re.sub(r"^[ \t]*[\*\-_]{3,}[ \t]*$", "──────────", text, flags=re.MULTILINE)

    # 11. Bullet lists:
    # Sub-bullets (indented):
    text = re.sub(r"^[ \t]{2,}[\*\-][ \t]+", "   ▫️ ", text, flags=re.MULTILINE)
    # Top-level bullets:
    text = re.sub(r"^[ \t]*[\*\-][ \t]+", "• ", text, flags=re.MULTILINE)

    # 12. Restore code blocks
    for idx, cb in enumerate(code_blocks):
        text = text.replace(f"QQQCODEBLOCK{idx}QQQ", f"<pre><code>{cb}</code></pre>")

    # 12b. Restore preserved valid Telegram HTML tags
    for idx, vt in enumerate(valid_tags):
        text = text.replace(f"QQQVALIDTAG{idx}QQQ", vt)

    # 13. Clean excessive whitespace and blank lines ("bosh joy bor")
    lines = [line.rstrip() for line in text.split("\n")]
    text = "\n".join(lines)
    # Collapse 3 or more newlines into max 2 (one blank line between blocks)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()

