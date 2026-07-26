"""
Certificate Distribution Management System (CDMS)
==================================================
Entry point for the application.

Run this file to launch CDMS:
    python main.py
"""

import sys
import os

# ---------------------------------------------------------------------------
# Ensure the project root is on the Python path so that `app` is importable
# regardless of the working directory from which main.py is invoked.
# ---------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# ---------------------------------------------------------------------------
# Python version guard
# ---------------------------------------------------------------------------
if sys.version_info < (3, 11):
    print(
        "ERROR: CDMS requires Python 3.11 or newer.\n"
        f"       You are running Python {sys.version_info.major}.{sys.version_info.minor}."
    )
    sys.exit(1)


def main() -> None:
    """Initialize and launch the CDMS application."""

    # Lazy import — keeps startup error messages clean if a dependency
    # is missing before the GUI is available.
    try:
        from app.ui.app import CDMSApplication
    except ImportError as exc:
        print(f"ERROR: Failed to import application modules.\n       {exc}")
        print("\nPlease make sure all dependencies are installed:")
        print("    pip install -r requirements.txt")
        sys.exit(1)

    app = CDMSApplication()
    app.run()


if __name__ == "__main__":
    main()
