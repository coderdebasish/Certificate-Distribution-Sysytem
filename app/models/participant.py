"""
app.models.participant
======================
Data model for a single event participant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EmailStatus(str, Enum):
    """Tracks the email delivery state for a participant."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


class MatchStatus(str, Enum):
    """Certificate assignment status."""
    NOT_ASSIGNED = "not_assigned"
    UNMATCHED = "not_assigned"
    AUTO_MATCHED = "auto_matched"
    MATCHED = "matched"
    LOW_CONFIDENCE = "low_confidence"
    MANUAL = "manual"
    MISSING = "missing"


@dataclass
class Participant:
    """
    Represents one event participant.

    ``internal_id`` is a permanent, human-readable ID (e.g. PID000001).
    It never changes even if the participant's name is edited.
    """

    # -----------------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------------
    id: int = 0                          # SQLite row id
    internal_id: str = ""               # PID000001 — permanent, never changes
    project_id: int = 0

    # -----------------------------------------------------------------------
    # Required fields
    # -----------------------------------------------------------------------
    full_name: str = ""
    email: str = ""

    # -----------------------------------------------------------------------
    # Optional fields
    # -----------------------------------------------------------------------
    phone: str = ""
    college: str = ""
    department: str = ""
    designation: str = ""
    certificate_type: str = ""
    remarks: str = ""

    # -----------------------------------------------------------------------
    # Assignment & status
    # -----------------------------------------------------------------------
    certificate_id: int = 0             # FK → Certificate.id (0 = none)
    match_status: MatchStatus = MatchStatus.NOT_ASSIGNED
    match_confidence: float = 0.0
    email_status: EmailStatus = EmailStatus.PENDING
    email_sent_at: datetime | None = None
    email_attempts: int = 0
    email_error: str = ""

    # -----------------------------------------------------------------------
    # Soft delete
    # -----------------------------------------------------------------------
    is_deleted: bool = False

    # -----------------------------------------------------------------------
    # Audit
    # -----------------------------------------------------------------------
    import_source: str = ""             # "manual" | "excel:<filename>"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @property
    def display_name(self) -> str:
        return self.full_name or f"(unnamed) {self.internal_id}"

    @property
    def has_certificate(self) -> bool:
        return self.certificate_id > 0

    def touch(self) -> None:
        self.updated_at = datetime.now()
