"""
app.utils.validators
=====================
Input validation utilities used across all modules.
"""

from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

_EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)


def is_valid_email(email: str) -> bool:
    """Return True if *email* matches a basic RFC-5322-like pattern."""
    return bool(email and _EMAIL_REGEX.match(email.strip()))


# ---------------------------------------------------------------------------
# Name
# ---------------------------------------------------------------------------

def is_valid_name(name: str) -> bool:
    """
    Return True if *name* is acceptable as a participant name.
    Rules: non-empty, 2–100 chars, contains at least one letter.
    """
    stripped = name.strip() if name else ""
    return (
        2 <= len(stripped) <= 100
        and bool(re.search(r"[a-zA-Z]", stripped))
    )


# ---------------------------------------------------------------------------
# File / Path
# ---------------------------------------------------------------------------

def is_valid_pdf(path: str | Path) -> bool:
    """Return True if *path* exists and has a .pdf extension."""
    p = Path(path)
    return p.suffix.lower() == ".pdf" and p.is_file()


def is_valid_folder(path: str | Path) -> bool:
    return Path(path).is_dir()


# ---------------------------------------------------------------------------
# Windows filename
# ---------------------------------------------------------------------------

_INVALID_WIN_CHARS = re.compile(r'[\\/:*?"<>|]')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


def sanitize_filename(name: str) -> str:
    """
    Remove / replace characters that are illegal in Windows filenames.
    Returns an empty string if no valid characters remain.
    """
    # Replace invalid chars with underscore
    sanitized = _INVALID_WIN_CHARS.sub("_", name)
    # Collapse multiple spaces
    sanitized = re.sub(r" {2,}", " ", sanitized).strip()
    # Remove trailing dots and spaces (Windows rules)
    sanitized = sanitized.rstrip(". ")
    # Reject reserved names
    if sanitized.upper() in _RESERVED_NAMES:
        sanitized = f"_{sanitized}"
    return sanitized


def is_valid_windows_filename(name: str) -> bool:
    """Return True if *name* can be used as a Windows filename."""
    return bool(name) and not _INVALID_WIN_CHARS.search(name) and name.upper() not in _RESERVED_NAMES
