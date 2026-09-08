"""In-memory rolling log buffer and logging handler.
Captures system log records into a thread-safe ring buffer for real-time inspection in the Admin panel.
"""

import collections
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

MAX_LOGS = 1000


class LogEntry:
    __slots__ = ("id", "timestamp", "time_str", "level", "logger_name", "message", "filename", "lineno")

    def __init__(self, entry_id: int, record: logging.LogRecord):
        self.id = entry_id
        self.timestamp = record.created
        self.time_str = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        self.level = record.levelname
        self.logger_name = record.name
        try:
            self.message = record.getMessage()
        except Exception:
            self.message = str(record.msg)
        self.filename = record.filename
        self.lineno = record.lineno

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "time": self.time_str,
            "level": self.level,
            "logger": self.logger_name,
            "message": self.message,
            "file": f"{self.filename}:{self.lineno}"
        }


class InMemoryLogBuffer(logging.Handler):
    """Logging handler that retains the latest N logs and allows querying by since_id or level."""

    def __init__(self, maxlen: int = MAX_LOGS):
        super().__init__()
        self.buffer = collections.deque(maxlen=maxlen)
        self._counter = 0

    def emit(self, record: logging.LogRecord):
        try:
            self._counter += 1
            entry = LogEntry(self._counter, record)
            self.buffer.append(entry)
        except Exception:
            self.handleError(record)

    def get_logs(self, since_id: int = 0, limit: int = 200, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent logs. If since_id > 0, returns only logs created after since_id."""
        results = []
        target_level = level.upper().strip() if level else None

        for entry in self.buffer:
            if entry.id <= since_id:
                continue
            if target_level and entry.level != target_level:
                continue
            results.append(entry.to_dict())

        # If no since_id (initial load), limit to the most recent 'limit' entries
        if since_id == 0 and len(results) > limit:
            results = results[-limit:]

        return results

    def clear(self):
        self.buffer.clear()


# Global shared singleton
log_buffer = InMemoryLogBuffer(maxlen=MAX_LOGS)

def setup_global_logger():
    """Attach the in-memory buffer to the root logger so all logs across the app are captured."""
    root_logger = logging.getLogger()
    if root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    if log_buffer not in root_logger.handlers:
        log_buffer.setLevel(logging.INFO)
        root_logger.addHandler(log_buffer)

# Auto-attach on import
setup_global_logger()
