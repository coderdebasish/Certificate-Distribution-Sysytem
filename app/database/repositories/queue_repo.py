"""
app.database.repositories.queue_repo
=====================================
Database operations for the EmailQueue table.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.database.connection import DatabaseConnection
from app.models.email_queue import EmailQueueItem, QueueItemStatus

logger = logging.getLogger(__name__)


class QueueRepository:

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def insert_many(self, items: list[EmailQueueItem]) -> None:
        """Bulk-insert all queue items in a single transaction."""
        with self._db.transaction() as cur:
            for item in items:
                cur.execute(
                    """
                    INSERT INTO email_queue (
                        project_id, queue_position, participant_id, certificate_id,
                        template_id, to_email, to_name, subject, body_html,
                        attachment_path, status, attempts, created_at, updated_at
                    ) VALUES (
                        :project_id, :queue_position, :participant_id, :certificate_id,
                        :template_id, :to_email, :to_name, :subject, :body_html,
                        :attachment_path, :status, :attempts, :created_at, :updated_at
                    )
                    """,
                    {
                        "project_id": item.project_id,
                        "queue_position": item.queue_position,
                        "participant_id": item.participant_id,
                        "certificate_id": item.certificate_id,
                        "template_id": item.template_id,
                        "to_email": item.to_email,
                        "to_name": item.to_name,
                        "subject": item.subject,
                        "body_html": item.body_html,
                        "attachment_path": item.attachment_path,
                        "status": item.status.value,
                        "attempts": item.attempts,
                        "created_at": item.created_at,
                        "updated_at": item.updated_at,
                    },
                )

    def get_pending(self, project_id: int) -> list[EmailQueueItem]:
        """Return all items with status PENDING or FAILED (for retry)."""
        with self._db.read() as cur:
            rows = cur.execute(
                """
                SELECT * FROM email_queue
                WHERE project_id = ?
                  AND status IN ('pending', 'failed', 'retrying')
                ORDER BY queue_position
                """,
                (project_id,),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def get_all(self, project_id: int) -> list[EmailQueueItem]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT * FROM email_queue WHERE project_id = ? ORDER BY queue_position",
                (project_id,),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def mark_sent(self, item_id: int) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE email_queue
                SET status = ?, sent_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (QueueItemStatus.SENT.value, datetime.now(), datetime.now(), item_id),
            )

    def mark_failed(self, item_id: int, error: str) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE email_queue
                SET status = ?, error_message = ?,
                    attempts = attempts + 1,
                    last_attempt_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (QueueItemStatus.FAILED.value, error, datetime.now(), datetime.now(), item_id),
            )

    def clear(self, project_id: int) -> None:
        """Delete all queue items for a project (before regenerating queue)."""
        with self._db.transaction() as cur:
            cur.execute("DELETE FROM email_queue WHERE project_id = ?", (project_id,))

    def count_by_status(self, project_id: int) -> dict[str, int]:
        with self._db.read() as cur:
            rows = cur.execute(
                """
                SELECT status, COUNT(*) as cnt FROM email_queue
                WHERE project_id = ?
                GROUP BY status
                """,
                (project_id,),
            ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    @staticmethod
    def _from_row(row: object) -> EmailQueueItem:
        return EmailQueueItem(
            id=row["id"],
            project_id=row["project_id"],
            queue_position=row["queue_position"],
            participant_id=row["participant_id"],
            certificate_id=row["certificate_id"],
            template_id=row["template_id"],
            to_email=row["to_email"],
            to_name=row["to_name"] or "",
            subject=row["subject"],
            body_html=row["body_html"],
            attachment_path=row["attachment_path"],
            status=QueueItemStatus(row["status"]),
            attempts=row["attempts"] or 0,
            last_attempt_at=row["last_attempt_at"],
            sent_at=row["sent_at"],
            error_message=row["error_message"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
