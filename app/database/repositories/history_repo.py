"""
app.database.repositories.history_repo
=======================================
Stores and retrieves project history entries (user action audit trail).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

from app.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """A single audited user action."""
    id: int = 0
    project_id: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    module: str = ""      # e.g. "RenameModule", "ParticipantModule"
    action: str = ""      # e.g. "ManualCorrection", "ExcelImport"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class HistoryRepository:
    """Insert and query project history entries."""

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def record(
        self,
        project_id: int,
        module: str,
        action: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append a history entry for *project_id*."""
        with self._db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO history (project_id, timestamp, module, action, description, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    datetime.now(),
                    module,
                    action,
                    description,
                    json.dumps(metadata or {}),
                ),
            )

    def get_all(self, project_id: int, limit: int = 500) -> list[HistoryEntry]:
        with self._db.read() as cur:
            rows = cur.execute(
                """
                SELECT * FROM history
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def search(self, project_id: int, query: str) -> list[HistoryEntry]:
        like = f"%{query}%"
        with self._db.read() as cur:
            rows = cur.execute(
                """
                SELECT * FROM history
                WHERE project_id = ?
                  AND (module LIKE ? OR action LIKE ? OR description LIKE ?)
                ORDER BY timestamp DESC
                """,
                (project_id, like, like, like),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    @staticmethod
    def _from_row(row: object) -> HistoryEntry:
        try:
            meta = json.loads(row["metadata"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return HistoryEntry(
            id=row["id"],
            project_id=row["project_id"],
            timestamp=row["timestamp"],
            module=row["module"],
            action=row["action"],
            description=row["description"],
            metadata=meta,
        )
