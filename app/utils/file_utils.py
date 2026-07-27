"""
app.utils.file_utils
=====================
File system helpers used across modules.
"""

from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Iterator

from app.config.constants import (
    FOLDER_CERTIFICATES, FOLDER_RENAMED, FOLDER_PARTICIPANTS,
    FOLDER_REPORTS, FOLDER_LOGS, FOLDER_TEMPLATES,
    FOLDER_CACHE, FOLDER_SETTINGS, FOLDER_BACKUPS,
    DATABASE_NAME,
)


# ---------------------------------------------------------------------------
# Project folder creation
# ---------------------------------------------------------------------------

PROJECT_SUBFOLDERS: list[str] = [
    FOLDER_CERTIFICATES,
    FOLDER_RENAMED,
    FOLDER_PARTICIPANTS,
    FOLDER_REPORTS,
    FOLDER_LOGS,
    FOLDER_TEMPLATES,
    FOLDER_CACHE,
    FOLDER_SETTINGS,
    FOLDER_BACKUPS,
]

WINDOWS_RESERVED_NAMES: set[str] = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def create_project_folders(project_dir: Path) -> None:
    """
    Create the standard project directory structure.
    All sub-folders are created atomically if they do not exist.
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    for subfolder in PROJECT_SUBFOLDERS:
        (project_dir / subfolder).mkdir(exist_ok=True)


def get_database_path(project_dir: Path) -> Path:
    return project_dir / DATABASE_NAME


# ---------------------------------------------------------------------------
# Filename Safety & Sanitization
# ---------------------------------------------------------------------------

def sanitize_filename(filename: str, max_length: int = 120) -> str:
    """
    Sanitize a string for cross-platform and Windows filesystem safety.
    Handles Unicode normalization, reserved names, illegal chars, trailing dots, and length limits.
    Preserves file extensions when present.
    """
    if not filename:
        return "unnamed"
    
    # 1. Unicode NFC Normalization
    filename = unicodedata.normalize("NFC", filename)
    
    # 2. Strip illegal Windows characters: < > : " / \ | ? *
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", filename)
    
    # 3. Separate valid extension if present (e.g. ".pdf")
    ext = ""
    stem = filename
    if "." in filename and not filename.endswith("."):
        parts = filename.rsplit(".", 1)
        if parts[1].isalnum() and len(parts[1]) <= 10:
            stem, ext = parts[0], f".{parts[1]}"

    # 4. Strip leading/trailing spaces and dots from stem
    stem = stem.strip(" .")
    
    if not stem:
        stem = "unnamed"

    # 5. Check Windows reserved names (e.g. CON, PRN, AUX, NUL, COM1)
    if stem.upper() in WINDOWS_RESERVED_NAMES:
        stem = f"{stem}_file"

    # 6. Enforce MAX_PATH length truncation
    if len(stem) > max_length:
        stem = stem[:max_length].rstrip(" .")

    return f"{stem}{ext}"


# ---------------------------------------------------------------------------
# PDF scanning
# ---------------------------------------------------------------------------

def scan_pdf_files(folder: Path, recursive: bool = False) -> list[Path]:
    """
    Return a sorted list of PDF files found in *folder*.
    Non-PDF files, hidden files, and system files are ignored.
    """
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(
        p for p in folder.glob(pattern)
        if p.is_file() and not p.name.startswith(".")
    )


# ---------------------------------------------------------------------------
# Disk space
# ---------------------------------------------------------------------------

def get_free_space_bytes(path: Path) -> int:
    """Return available disk space in bytes for the volume containing *path*."""
    usage = shutil.disk_usage(str(path))
    return usage.free


def has_enough_space(path: Path, required_bytes: int) -> bool:
    return get_free_space_bytes(path) >= required_bytes


# ---------------------------------------------------------------------------
# Safe copy
# ---------------------------------------------------------------------------

def safe_copy(source: Path, destination: Path, overwrite: bool = False) -> None:
    """
    Copy *source* to *destination*. Raises FileExistsError if the destination
    exists and *overwrite* is False.
    """
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(destination))
