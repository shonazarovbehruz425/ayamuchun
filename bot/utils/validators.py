import os
import time

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


PROMPT_INJECTION_PATTERNS = [
    # English patterns
    r"(?i)\b(?:ignore|disregard|forget|override|bypass)\s+(?:all\s+)?(?:previous|prior|above|former|system)\s+(?:instructions|directions|prompts|rules|commands)",
    r"(?i)\byou\s+are\s+now\s+(?:in\s+)?(?:an?\s+)?(?:admin|administrator|root|dan\b|developer\s+mode|jailbroken)",
    r"(?i)\bact\s+as\s+(?:an?\s+)?(?:admin|root|system\s+administrator|dan\b|unfiltered)",
    r"(?i)(?:^|\n)\s*system\s*:\s*(?:override|new\s+rule|you\s+are)",
    r"(?i)<\|im_start\|>system",
    r"(?i)\[INST\]\s*<<SYS>>",
    r"(?i)\[system\s*(?:message|prompt)?\]",
    r"(?i)\b(?:output|print|show|repeat|display|reveal)\s+(?:your\s+)?(?:initial|system|original|base)\s+(?:prompt|instructions|rules)\b",

    # Uzbek patterns
    r"(?i)\b(?:avvalgi|oldingi|barcha|yuqoridagi)\s+ko['`’]?rsatma(?:lar)?ni\s+(?:unut(?:ing)?|bekor\s+qil(?:ing)?|o['`’]?chir(?:ing)?|tashlab\s+yubor|inkor\s+qil)",
    r"(?i)\b(?:sen\s+)?(?:endi\s+)?adminsan\b",
    r"(?i)\bdan\s+buyon\s+sen\s+adminsan\b",
    r"(?i)\bbarcha\s+qoidalarni\s+(?:chetlab\s+o['`’]?t|unut|buz)",
    r"(?i)\b(?:tizim|boshlang['`’]?ich)\s+(?:promp(?:t)?|ko['`’]?rsatma|qoida)lar(?:ing)?ni\s+(?:ko['`’]?rsat|ochiqla|ayt|yozib\s+ber)\b",

    # Russian patterns
    r"(?i)\b(?:забудь|игнорируй|отмени|сбрось)\s+(?:все\s+)?(?:предыдущие|прошлые|вышеуказанные|системные)\s+(?:инструкции|правила|указания|команды)",
    r"(?i)\bты\s+теперь\s+(?:админ|администратор|в\s+режиме\s+разработчика|dan\b)",
    r"(?i)\bдействуй\s+как\s+(?:админ|администратор|root)",
    r"(?i)\b(?:покажи|выведи|раскрой)\s+(?:свой\s+)?(?:системный\s+промпт|инструкции|правила)\b",
]

import re
_INJECTION_REGEXES = [re.compile(p) for p in PROMPT_INJECTION_PATTERNS]

def is_prompt_injection(text: str) -> bool:
    """Checks if text contains prompt injection or system override attempts."""
    if not text:
        return False
    clean = text.strip()
    for regex in _INJECTION_REGEXES:
        if regex.search(clean):
            return True
    return False


class SlidingWindowRateLimiter:
    """In-memory sliding-window rate limiter per user/key."""

    def __init__(self):
        # key -> list of timestamps
        self._requests = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()

    def _cleanup(self, current_time: float):
        """Periodically remove expired timestamps to prevent memory growth."""
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = current_time
        cutoff = current_time - 600
        keys_to_delete = []
        for key, timestamps in self._requests.items():
            valid = [ts for ts in timestamps if ts > cutoff]
            if valid:
                self._requests[key] = valid
            else:
                keys_to_delete.append(key)
        for key in keys_to_delete:
            self._requests.pop(key, None)

    def is_rate_limited(self, key: str, limit: int, window_seconds: int) -> bool:
        """
        Returns True if key exceeded the rate limit in window_seconds, False otherwise.
        Appends the current timestamp if not rate-limited.
        """
        now = time.time()
        self._cleanup(now)

        window_start = now - window_seconds
        timestamps = self._requests.get(key, [])

        valid_timestamps = [ts for ts in timestamps if ts > window_start]
        self._requests[key] = valid_timestamps

        if len(valid_timestamps) >= limit:
            return True

        self._requests[key].append(now)
        return False

    def check(self, key: str, limit: int = 20, window_seconds: int = 60, action: str = "so'rov"):
        """Checks rate limit and raises HTTPException 429 if exceeded."""
        from fastapi import HTTPException
        if self.is_rate_limited(key, limit, window_seconds):
            raise HTTPException(
                status_code=429,
                detail=f"Juda ko'p {action} yuborildi. Iltimos, biroz kuting va qayta urinib ko'ring (limit: {limit} ta / {window_seconds} soniya)."
            )


# Global rate limiter instance
rate_limiter = SlidingWindowRateLimiter()
