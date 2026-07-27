"""
app.database.repositories.project_repo
=======================================
Database operations for Project records.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.database.connection import DatabaseConnection
from app.models.project import Project, ProjectStage, ProjectStatus

logger = logging.getLogger(__name__)


class ProjectRepository:
    """CRUD operations for the Project table."""

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def insert(self, project: Project) -> Project:
        with self._db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO projects (
                    name, event_name, description, project_dir, database_path,
                    stage, status, created_at, updated_at, last_opened_at
                ) VALUES (
                    :name, :event_name, :description, :project_dir, :database_path,
                    :stage, :status, :created_at, :updated_at, :last_opened_at
                )
                """,
                self._to_dict(project),
            )
            project.id = cur.lastrowid  # type: ignore[assignment]
        return project

    def get_by_id(self, project_id: int) -> Optional[Project]:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def get_all(self) -> list[Project]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT * FROM projects ORDER BY last_opened_at DESC"
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def update(self, project: Project) -> None:
        project.touch()
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE projects SET
                    name = :name, event_name = :event_name,
                    description = :description, stage = :stage,
                    status = :status,
                    total_participants = :total_participants,
                    total_certificates = :total_certificates,
                    matched_count = :matched_count,
                    emails_sent = :emails_sent,
                    emails_failed = :emails_failed,
                    emails_pending = :emails_pending,
                    updated_at = :updated_at,
                    last_opened_at = :last_opened_at
                WHERE id = :id
                """,
                self._to_dict(project),
            )

    def touch_opened(self, project_id: int) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                "UPDATE projects SET last_opened_at = ? WHERE id = ?",
                (datetime.now(), project_id),
            )

    @staticmethod
    def _to_dict(p: Project) -> dict:
        return {
            "id": p.id,
            "name": p.name,
            "event_name": p.event_name,
            "description": p.description,
            "project_dir": p.project_dir,
            "database_path": p.database_path,
            "stage": p.stage.value,
            "status": p.status.value,
            "total_participants": p.total_participants,
            "total_certificates": p.total_certificates,
            "matched_count": p.matched_count,
            "emails_sent": p.emails_sent,
            "emails_failed": p.emails_failed,
            "emails_pending": p.emails_pending,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "last_opened_at": p.last_opened_at,
        }

    @staticmethod
    def _from_row(row: object) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            event_name=row["event_name"] or "",
            description=row["description"] or "",
            project_dir=row["project_dir"],
            database_path=row["database_path"],
            stage=ProjectStage(row["stage"]),
            status=ProjectStatus(row["status"]),
            total_participants=row["total_participants"] or 0,
            total_certificates=row["total_certificates"] or 0,
            matched_count=row["matched_count"] or 0,
            emails_sent=row["emails_sent"] or 0,
            emails_failed=row["emails_failed"] or 0,
            emails_pending=row["emails_pending"] or 0,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_opened_at=row["last_opened_at"],
        )
