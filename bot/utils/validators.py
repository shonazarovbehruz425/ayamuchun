import os

SUPPORTED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt', '.csv'}

def validate_file_size(size: int, max_mb: int = 20) -> bool:
    max_bytes = max_mb * 1024 * 1024
    return size <= max_bytes

def validate_file_type(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_EXTENSIONS

def get_mime_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    mime_types = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xls': 'application/vnd.ms-excel',
        '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        '.ppt': 'application/vnd.ms-powerpoint',
        '.csv': 'text/csv'
    }
    return mime_types.get(ext, 'application/octet-stream')
