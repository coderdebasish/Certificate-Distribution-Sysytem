"""
app.config.constants
====================
Application-wide constants.  Import from here — never hardcode values in
other modules.
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Application Identity
# ---------------------------------------------------------------------------
APP_NAME: str = "Certificate Distribution Management System"
APP_SHORT_NAME: str = "CDMS"
APP_VERSION: str = "0.1.0"
APP_AUTHOR: str = "CDMS Team"

# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------
WINDOW_MIN_WIDTH: int = 1366
WINDOW_MIN_HEIGHT: int = 768
WINDOW_DEFAULT_WIDTH: int = 1600
WINDOW_DEFAULT_HEIGHT: int = 900
WINDOW_TITLE: str = f"{APP_SHORT_NAME} — {APP_NAME}"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parents[2]
ASSETS_DIR: Path = ROOT_DIR / "app" / "assets"
ICONS_DIR: Path = ASSETS_DIR / "icons"
FONTS_DIR: Path = ASSETS_DIR / "fonts"

# Default location for new projects (user can override in settings)
DEFAULT_PROJECTS_DIR: Path = Path.home() / "Documents" / "CDMS Projects"

# ---------------------------------------------------------------------------
# Auto-save
# ---------------------------------------------------------------------------
AUTOSAVE_INTERVAL_SECONDS: int = 120  # 2 minutes (configurable per project)

# ---------------------------------------------------------------------------
# File extensions
# ---------------------------------------------------------------------------
PROJECT_EXTENSION: str = ".cds"
DATABASE_NAME: str = "database.db"
SUPPORTED_CERTIFICATE_EXTENSION: str = ".pdf"
SUPPORTED_EXCEL_EXTENSIONS: tuple[str, ...] = (".xlsx", ".xls")

# ---------------------------------------------------------------------------
# Project sub-folder names (created automatically)
# ---------------------------------------------------------------------------
FOLDER_CERTIFICATES: str = "Certificates"
FOLDER_RENAMED: str = "Renamed Certificates"
FOLDER_PARTICIPANTS: str = "Participants"
FOLDER_REPORTS: str = "Reports"
FOLDER_LOGS: str = "Logs"
FOLDER_TEMPLATES: str = "Templates"
FOLDER_CACHE: str = "Cache"
FOLDER_SETTINGS: str = "Settings"
FOLDER_BACKUPS: str = "Backups"

# ---------------------------------------------------------------------------
# OCR Confidence thresholds
# ---------------------------------------------------------------------------
OCR_CONFIDENCE_HIGH: float = 90.0    # Green
OCR_CONFIDENCE_MEDIUM: float = 70.0  # Orange
# Below OCR_CONFIDENCE_MEDIUM → Red (needs manual review)

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_DEFAULT_DELAY_SECONDS: int = 5
EMAIL_MAX_RETRIES: int = 3
EMAIL_RETRY_DELAY_SECONDS: int = 30

# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------
MATCH_EXACT_SCORE: int = 100
MATCH_HIGH_THRESHOLD: int = 90
MATCH_MEDIUM_THRESHOLD: int = 75
# Below MATCH_MEDIUM_THRESHOLD → Low confidence (requires review)

# ---------------------------------------------------------------------------
# Participant ID format
# ---------------------------------------------------------------------------
PARTICIPANT_ID_PREFIX: str = "PID"
PARTICIPANT_ID_PADDING: int = 6  # PID000001

# ---------------------------------------------------------------------------
# Supported email placeholders
# ---------------------------------------------------------------------------
SUPPORTED_PLACEHOLDERS: tuple[str, ...] = (
    "{name}",
    "{email}",
    "{certificate}",
    "{event_name}",
    "{project_name}",
    "{college}",
    "{department}",
    "{designation}",
    "{date}",
    "{year}",
)
