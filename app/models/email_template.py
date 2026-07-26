"""
app.models.email_template
=========================
Data model for an email template.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailTemplate:
    """
    Stores a named, versioned email template with subject, body, and
    placeholder support.

    Multiple templates can exist per project (Participation, Winner, etc.).
    Each save creates a new version entry in the history.
    """

    # -----------------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------------
    id: int = 0
    project_id: int = 0
    name: str = ""                       # e.g. "Participation Certificate"
    is_active: bool = False              # Only one template active at a time

    # -----------------------------------------------------------------------
    # Content
    # -----------------------------------------------------------------------
    subject: str = ""                    # Supports placeholders: {event_name}
    body_html: str = ""                  # Rich HTML body with placeholders
    version: int = 1

    # -----------------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------------
    description: str = ""

    # -----------------------------------------------------------------------
    # Timestamps
    # -----------------------------------------------------------------------
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        self.updated_at = datetime.now()
        self.version += 1


@dataclass
class TemplateVersion:
    """
    A historical snapshot of a template at a specific save point.
    Allows restoring previous versions.
    """

    id: int = 0
    template_id: int = 0
    version_number: int = 1
    subject: str = ""
    body_html: str = ""
    saved_at: datetime = field(default_factory=datetime.now)
    note: str = ""
