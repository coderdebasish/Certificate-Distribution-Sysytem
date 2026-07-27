"""
app.config.settings
===================
Global application settings model.

Settings are stored in a JSON file inside the application directory and are
separate from per-project settings.  Per-project overrides live inside each
project's own Settings/ folder.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal

from app.config.constants import APP_SHORT_NAME, DEFAULT_PROJECTS_DIR


# ---------------------------------------------------------------------------
# Path for the global settings file
# ---------------------------------------------------------------------------
_SETTINGS_DIR: Path = Path.home() / f".{APP_SHORT_NAME.lower()}"
SETTINGS_FILE: Path = _SETTINGS_DIR / "settings.json"


@dataclass
class AppSettings:
    """Persisted application-level settings."""

    # Appearance
    theme: Literal["dark", "light"] = "dark"
    accent_color: Literal["blue", "purple", "green", "orange", "gray"] = "blue"
    font_scale: float = 1.0

    # General
    default_projects_dir: str = str(DEFAULT_PROJECTS_DIR)
    recent_project_count: int = 10
    startup_behavior: Literal["dashboard", "last_project"] = "dashboard"

    # Auto-save
    autosave_enabled: bool = True
    autosave_interval_seconds: int = 120

    # Email defaults
    email_default_delay_seconds: int = 5
    email_max_retries: int = 3
    email_retry_delay_seconds: int = 30
    encrypted_credentials: str = ""

    # OCR
    ocr_engine: Literal["paddleocr"] = "paddleocr"
    ocr_confidence_threshold: float = 70.0
    ocr_language: str = "en"
    ocr_cpu_threads: int = 4
    fuzzy_match_threshold: float = 80.0

    # Backup
    backup_enabled: bool = True
    backup_frequency: Literal["before_major_op", "daily"] = "before_major_op"
    max_backup_count: int = 10

    # Window state (saved on close)
    window_width: int = 1600
    window_height: int = 900
    window_maximized: bool = False
    sidebar_collapsed: bool = False

    # Recent projects (list of absolute path strings)
    recent_projects: list[str] = field(default_factory=list)

    # ---------------------------------------------------------------------------
    # Persistence
    # ---------------------------------------------------------------------------

    @classmethod
    def load(cls) -> "AppSettings":
        """Load settings from disk.  Returns defaults if the file does not exist."""
        if not SETTINGS_FILE.exists():
            return cls()
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            # Only apply keys that exist in the dataclass to avoid crashes on old configs
            valid_keys = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
            filtered = {k: v for k, v in data.items() if k in valid_keys}
            return cls(**filtered)
        except Exception:
            # Corrupted settings — return defaults
            return cls()

    def save(self) -> None:
        """Persist current settings to disk."""
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_recent_project(self, project_path: str) -> None:
        """Prepend *project_path* to the recent projects list (no duplicates)."""
        if project_path in self.recent_projects:
            self.recent_projects.remove(project_path)
        self.recent_projects.insert(0, project_path)
        # Trim to limit
        from app.config.constants import WINDOW_DEFAULT_WIDTH  # avoid circular
        max_count = getattr(self, "recent_project_count", 10)
        self.recent_projects = self.recent_projects[:max_count]
