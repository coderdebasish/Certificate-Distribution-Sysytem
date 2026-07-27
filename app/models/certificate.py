"""
app.models.certificate
======================
Data model for a single certificate PDF file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path


class ExtractionMethod(str, Enum):
    """How the participant name was extracted from the PDF."""
    TEXT = "text"          # PyMuPDF / pdfplumber selectable text
    OCR = "ocr"            # PaddleOCR
    MANUAL = "manual"      # User manually typed / corrected the name
    FAILED = "failed"      # Could not extract


class CertificateStatus(str, Enum):
    """Processing status of the certificate."""
    PENDING = "pending"         # Imported, not yet analyzed
    ANALYZING = "analyzing"     # OCR/text extraction in progress
    READY = "ready"             # Name detected, ready for rename
    NEEDS_REVIEW = "needs_review" # Name detected with low confidence or manual review needed
    RENAMED = "renamed"         # Renamed copy exists
    IGNORED = "ignored"         # User marked as ignore (cover page, etc.)
    FAILED = "failed"           # Analysis or rename failed


@dataclass
class Certificate:
    """
    Represents one certificate PDF file and the result of name extraction.

    Originals are NEVER modified.  The ``renamed_file_path`` points to a copy
    inside the project's ``Renamed Certificates/`` folder.
    """

    # -----------------------------------------------------------------------
    # Identity
    # -----------------------------------------------------------------------
    id: int = 0                          # SQLite row id
    project_id: int = 0

    # -----------------------------------------------------------------------
    # File information
    # -----------------------------------------------------------------------
    original_filename: str = ""          # e.g. "1.pdf"
    original_file_path: str = ""         # Full path to original (read-only)
    renamed_filename: str = ""           # e.g. "Debasish Mohanty.pdf"
    renamed_file_path: str = ""          # Full path inside project Renamed/

    # -----------------------------------------------------------------------
    # Extraction result
    # -----------------------------------------------------------------------
    detected_name: str = ""
    extraction_method: ExtractionMethod = ExtractionMethod.FAILED
    confidence: float = 0.0              # 0.0 – 100.0
    raw_extracted_text: str = ""         # Full raw text from PDF/OCR
    status: CertificateStatus = CertificateStatus.PENDING

    # -----------------------------------------------------------------------
    # Manual correction audit
    # -----------------------------------------------------------------------
    original_detected_name: str = ""    # Preserved if user corrects name
    manually_corrected: bool = False
    corrected_at: datetime | None = None

    # -----------------------------------------------------------------------
    # Duplicate / ignore flags
    # -----------------------------------------------------------------------
    is_ignored: bool = False
    is_duplicate: bool = False
    duplicate_of_id: int = 0            # FK → Certificate.id

    # -----------------------------------------------------------------------
    # Failure tracking
    # -----------------------------------------------------------------------
    failure_reason: str = ""

    # -----------------------------------------------------------------------
    # Timestamps
    # -----------------------------------------------------------------------
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 90:
            return "High"
        if self.confidence >= 70:
            return "Medium"
        return "Low"

    @property
    def new_filename(self) -> str:
        """Proposed filename for the renamed copy."""
        if self.detected_name:
            return f"{self.detected_name}.pdf"
        return ""

    def touch(self) -> None:
        self.updated_at = datetime.now()
