"""
app.models.email_queue
======================
Data model for items in the email sending queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class QueueItemStatus(str, Enum):
    """Status of a single item in the email sending queue."""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


QueueStatus = QueueItemStatus


@dataclass
class EmailQueueItem:
    """
    Represents one email ready to be sent.

    The queue is generated *before* sending begins so that every email can be
    validated, previewed, and recovered after a crash.

    After every successful send the item status is saved to the database
    immediately — so a crash never causes duplicate sends.
    """

    # Identity
    id: int = 0
    project_id: int = 0
    queue_position: int = 0

    # References
    participant_id: int = 0
    certificate_id: int = 0
    template_id: int = 0

    # Rendered content
    to_email: str = ""
    to_name: str = ""
    subject: str = ""
    body_html: str = ""
    attachment_path: str = ""

    # Status tracking
    status: QueueItemStatus = QueueItemStatus.PENDING
    attempts: int = 0
    last_attempt_at: datetime | None = None
    sent_at: datetime | None = None
    error_message: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        self.updated_at = datetime.now()


QueueItem = EmailQueueItem
