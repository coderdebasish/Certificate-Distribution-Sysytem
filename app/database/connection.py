"""
app.database.connection
=======================
SQLite connection manager.

Each project has its own database.db file.  This module provides a
thread-safe connection context manager and a singleton per database path.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


class DatabaseConnection:
    """
    Manages a single SQLite connection for one project database.

    Thread safety: SQLite connections are not thread-safe by default.
    We use ``check_same_thread=False`` together with a threading.Lock to
    serialize writes.  Reads can be concurrent when WAL mode is enabled.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.Lock()
        self._connection: sqlite3.Connection | None = None

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def open(self) -> None:
        """Open the SQLite connection and apply recommended pragmas."""
        if self._connection is not None:
            return
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        self._connection.row_factory = sqlite3.Row
        self._apply_pragmas()

    def close(self) -> None:
        """Close the connection cleanly."""
        if self._connection:
            self._connection.close()
            self._connection = None

    # -----------------------------------------------------------------------
    # Context manager
    # -----------------------------------------------------------------------

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager that yields a cursor inside an auto-committed
        transaction.  On exception the transaction is rolled back.

        Usage::

            with db.transaction() as cur:
                cur.execute("INSERT INTO ...")
        """
        assert self._connection is not None, "Database is not open."
        with self._lock:
            cursor = self._connection.cursor()
            try:
                yield cursor
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            finally:
                cursor.close()

    @contextmanager
    def read(self) -> Generator[sqlite3.Cursor, None, None]:
        """
        Context manager for read-only queries (no commit/rollback).

        Usage::

            with db.read() as cur:
                rows = cur.execute("SELECT ...").fetchall()
        """
        assert self._connection is not None, "Database is not open."
        cursor = self._connection.cursor()
        try:
            yield cursor
        finally:
            cursor.close()

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _apply_pragmas(self) -> None:
        assert self._connection is not None
        self._connection.executescript("""
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;
            PRAGMA synchronous = NORMAL;
            PRAGMA temp_store = MEMORY;
            PRAGMA cache_size = -8000;
        """)
