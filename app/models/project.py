"""
app.models.project
==================
Data model representing a single CDMS project.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ProjectStage(str, Enum):
    """The current lifecycle stage of the project."""
    CREATED = "created"
    CERTIFICATES_IMPORTED = "certificates_imported"
    RENAME_COMPLETED = "rename_completed"
    PARTICIPANTS_IMPORTED = "participants_imported"
    MATCHING_COMPLETED = "matching_completed"
    TEMPLATE_READY = "template_ready"
    SENDING_IN_PROGRESS = "sending_in_progress"
    SENDING_COMPLETED = "sending_completed"
    ARCHIVED = "archived"


class ProjectStatus(str, Enum):
    """High-level status shown in the dashboard."""
    DRAFT = "draft"
    READY = "ready"
    SENDING = "sending"
    COMPLETED = "completed"
    ERROR = "error"
    ARCHIVED = "archived"


@dataclass
class Project:
    """
    Represents a single CDMS project (one event = one project).

    All fields are persisted to both the SQLite database and the .cds file.
    """

    # -----------------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------------
    id: int = 0                          # SQLite row id (0 = not yet saved)
    name: str = ""                       # Human-readable project name
    event_name: str = ""                 # Name of the event (e.g. "Future X Design Challenge")
    description: str = ""

    # -----------------------------------------------------------------------
    # File system
    # -----------------------------------------------------------------------
    project_dir: str = ""                # Absolute path to the project folder
    database_path: str = ""              # Absolute path to database.db

    # -----------------------------------------------------------------------
    # Workflow state
    # -----------------------------------------------------------------------
    stage: ProjectStage = ProjectStage.CREATED
    status: ProjectStatus = ProjectStatus.DRAFT

    # -----------------------------------------------------------------------
    # Statistics (cached — source of truth is the DB)
    # -----------------------------------------------------------------------
    total_participants: int = 0
    total_certificates: int = 0
    matched_count: int = 0
    emails_sent: int = 0
    emails_failed: int = 0
    emails_pending: int = 0

    # -----------------------------------------------------------------------
    # Timestamps
    # -----------------------------------------------------------------------
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_opened_at: datetime = field(default_factory=datetime.now)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @property
    def project_path(self) -> Path:
        return Path(self.project_dir)

    @property
    def renamed_certificates_path(self) -> Path:
        from app.config.constants import FOLDER_RENAMED
        return self.project_path / FOLDER_RENAMED

    @property
    def is_ready_to_send(self) -> bool:
        """True only when all participants are matched and have valid emails."""
        return (
            self.total_participants > 0
            and self.matched_count == self.total_participants
            and self.emails_failed == 0
        )

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
