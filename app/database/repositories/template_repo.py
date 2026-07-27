"""
app.database.repositories.template_repo
========================================
Database operations for EmailTemplate and TemplateVersion records.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.database.connection import DatabaseConnection
from app.models.email_template import EmailTemplate, TemplateVersion

logger = logging.getLogger(__name__)


class TemplateRepository:

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def insert(self, template: EmailTemplate) -> EmailTemplate:
        with self._db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO email_templates
                    (project_id, name, is_active, subject, body_html, version,
                     description, created_at, updated_at)
                VALUES (:project_id, :name, :is_active, :subject, :body_html, :version,
                        :description, :created_at, :updated_at)
                """,
                self._to_dict(template),
            )
            template.id = cur.lastrowid  # type: ignore[assignment]
        return template

    def get_all(self, project_id: int) -> list[EmailTemplate]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT * FROM email_templates WHERE project_id = ? ORDER BY name",
                (project_id,),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def get_active(self, project_id: int) -> Optional[EmailTemplate]:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT * FROM email_templates WHERE project_id = ? AND is_active = 1",
                (project_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def update(self, template: EmailTemplate) -> None:
        template.touch()
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE email_templates SET
                    name = :name, is_active = :is_active, subject = :subject,
                    body_html = :body_html, version = :version,
                    description = :description, updated_at = :updated_at
                WHERE id = :id
                """,
                self._to_dict(template),
            )

    def set_active(self, project_id: int, template_id: int) -> None:
        """Deactivate all templates in the project, then activate the given one."""
        with self._db.transaction() as cur:
            cur.execute(
                "UPDATE email_templates SET is_active = 0 WHERE project_id = ?",
                (project_id,),
            )
            cur.execute(
                "UPDATE email_templates SET is_active = 1 WHERE id = ?",
                (template_id,),
            )

    def save_version(self, template: EmailTemplate, note: str = "") -> None:
        with self._db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO template_versions
                    (template_id, version_number, subject, body_html, saved_at, note)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (template.id, template.version, template.subject,
                 template.body_html, datetime.now(), note),
            )

    def get_versions(self, template_id: int) -> list[TemplateVersion]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT * FROM template_versions WHERE template_id = ? ORDER BY version_number DESC",
                (template_id,),
            ).fetchall()
        return [
            TemplateVersion(
                id=r["id"],
                template_id=r["template_id"],
                version_number=r["version_number"],
                subject=r["subject"],
                body_html=r["body_html"],
                saved_at=r["saved_at"],
                note=r["note"] or "",
            )
            for r in rows
        ]

    def delete(self, template_id: int) -> None:
        with self._db.transaction() as cur:
            cur.execute("DELETE FROM template_versions WHERE template_id = ?", (template_id,))
            cur.execute("DELETE FROM email_templates WHERE id = ?", (template_id,))

    @staticmethod
    def _to_dict(t: EmailTemplate) -> dict:
        return {
            "id": t.id,
            "project_id": t.project_id,
            "name": t.name,
            "is_active": int(t.is_active),
            "subject": t.subject,
            "body_html": t.body_html,
            "version": t.version,
            "description": t.description,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }

    @staticmethod
    def _from_row(row: object) -> EmailTemplate:
        return EmailTemplate(
            id=row["id"],
            project_id=row["project_id"],
            name=row["name"],
            is_active=bool(row["is_active"]),
            subject=row["subject"] or "",
            body_html=row["body_html"] or "",
            version=row["version"] or 1,
            description=row["description"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
