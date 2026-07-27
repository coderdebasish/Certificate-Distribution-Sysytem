"""
app.utils.logger
================
Logging configuration for CDMS.

Sets up both a rotating file handler (application.log) and a stream handler
for the console.  Module-level loggers throughout the app inherit this config.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


def setup_logging(
    log_dir: Path | None = None,
    level: int = logging.INFO,
) -> None:
    """
    Configure the root logger.

    :param log_dir: Directory to write application.log.  If None, file logging
                    is disabled and only console output is used.
    :param level:   Minimum log level (e.g. logging.DEBUG).
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers on repeated calls (e.g. during testing)
    if root.handlers:
        return

    fmt = logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(level)
    root.addHandler(console)

    # Rotating file handler
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "application.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,   # 5 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — equivalent to logging.getLogger(name)."""
    return logging.getLogger(name)
