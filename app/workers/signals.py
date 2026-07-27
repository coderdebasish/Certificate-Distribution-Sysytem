"""
app.workers.signals
====================
Thread-safe signal/event definitions for communicating between background
workers and the UI thread.

Workers NEVER touch CustomTkinter widgets directly.  Instead they enqueue
signal objects onto a thread-safe queue that the UI thread polls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SignalType(str, Enum):
    # Progress
    PROGRESS_UPDATE = "progress_update"
    PROGRESS_COMPLETE = "progress_complete"
    PROGRESS_ERROR = "progress_error"

    # Log
    LOG_MESSAGE = "log_message"

    # OCR / Rename
    CERTIFICATE_ANALYZED = "certificate_analyzed"
    CERTIFICATE_RENAMED = "certificate_renamed"
    CERTIFICATE_FAILED = "certificate_failed"

    # Email
    EMAIL_SENT = "email_sent"
    EMAIL_FAILED = "email_failed"
    EMAIL_QUEUE_COMPLETE = "email_queue_complete"

    # Import
    IMPORT_ROW_PROCESSED = "import_row_processed"
    IMPORT_COMPLETE = "import_complete"

    # Worker state
    WORKER_STARTED = "worker_started"
    WORKER_PAUSED = "worker_paused"
    WORKER_STOPPED = "worker_stopped"
    WORKER_CANCELLED = "worker_cancelled"


@dataclass
class Signal:
    """A signal emitted by a background worker."""
    type: SignalType
    payload: dict[str, Any] = field(default_factory=dict)

    # Convenience constructors -----------------------------------------------

    @classmethod
    def progress(cls, current: int, total: int, message: str = "", elapsed_sec: int = 0, eta_sec: int = 0) -> "Signal":
        return cls(
            type=SignalType.PROGRESS_UPDATE,
            payload={
                "current": current,
                "total": total,
                "message": message,
                "elapsed_sec": elapsed_sec,
                "eta_sec": eta_sec,
            },
        )

    @classmethod
    def log(cls, message: str, level: str = "INFO") -> "Signal":
        return cls(
            type=SignalType.LOG_MESSAGE,
            payload={"message": message, "level": level},
        )

    @classmethod
    def complete(cls, message: str = "Completed") -> "Signal":
        return cls(type=SignalType.PROGRESS_COMPLETE, payload={"message": message})

    @classmethod
    def error(cls, message: str, details: str = "") -> "Signal":
        return cls(
            type=SignalType.PROGRESS_ERROR,
            payload={"message": message, "details": details},
        )
