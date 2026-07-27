"""
app.database.repositories.participant_repo
==========================================
All database operations for Participant records.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.database.connection import DatabaseConnection
from app.models.participant import Participant, EmailStatus, MatchStatus

logger = logging.getLogger(__name__)


class ParticipantRepository:
    """CRUD operations for Participant records."""

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    def insert(self, participant: Participant) -> Participant:
        """Insert a new participant record and return it with the assigned id."""
        if not participant.internal_id:
            import uuid
            participant.internal_id = f"PID-{uuid.uuid4().hex[:8].upper()}"

        with self._db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO participants (
                    internal_id, project_id, full_name, email, phone,
                    college, department, designation, certificate_type,
                    remarks, certificate_id, match_status, match_confidence,
                    email_status, email_attempts, email_error, is_deleted,
                    import_source, created_at, updated_at
                ) VALUES (
                    :internal_id, :project_id, :full_name, :email, :phone,
                    :college, :department, :designation, :certificate_type,
                    :remarks, :certificate_id, :match_status, :match_confidence,
                    :email_status, :email_attempts, :email_error, :is_deleted,
                    :import_source, :created_at, :updated_at
                )
                """,
                self._to_dict(participant),
            )
            participant.id = cur.lastrowid  # type: ignore[assignment]
        return participant

    # -----------------------------------------------------------------------
    # Read
    # -----------------------------------------------------------------------

    def get_by_id(self, participant_id: int) -> Optional[Participant]:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT * FROM participants WHERE id = ?", (participant_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def get_all(self, project_id: int, include_deleted: bool = False) -> list[Participant]:
        sql = "SELECT * FROM participants WHERE project_id = ?"
        params: list = [project_id]
        if not include_deleted:
            sql += " AND is_deleted = 0"
        sql += " ORDER BY id"
        with self._db.read() as cur:
            rows = cur.execute(sql, params).fetchall()
        return [self._from_row(r) for r in rows]

    def get_by_email(self, project_id: int, email: str) -> Optional[Participant]:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT * FROM participants WHERE project_id = ? AND email = ? AND is_deleted = 0",
                (project_id, email),
            ).fetchone()
        return self._from_row(row) if row else None

    def search(self, project_id: int, query: str) -> list[Participant]:
        """Full-text search across name and email."""
        like = f"%{query}%"
        with self._db.read() as cur:
            rows = cur.execute(
                """
                SELECT * FROM participants
                WHERE project_id = ?
                  AND is_deleted = 0
                  AND (full_name LIKE ? OR email LIKE ?)
                ORDER BY full_name
                """,
                (project_id, like, like),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def count(self, project_id: int) -> int:
        with self._db.read() as cur:
            return cur.execute(
                "SELECT COUNT(*) FROM participants WHERE project_id = ? AND is_deleted = 0",
                (project_id,),
            ).fetchone()[0]

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, participant: Participant) -> None:
        participant.touch()
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE participants SET
                    full_name = :full_name,
                    email = :email,
                    phone = :phone,
                    college = :college,
                    department = :department,
                    designation = :designation,
                    certificate_type = :certificate_type,
                    remarks = :remarks,
                    certificate_id = :certificate_id,
                    match_status = :match_status,
                    match_confidence = :match_confidence,
                    email_status = :email_status,
                    email_sent_at = :email_sent_at,
                    email_attempts = :email_attempts,
                    email_error = :email_error,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                self._to_dict(participant),
            )

    def mark_email_sent(self, participant_id: int) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE participants
                SET email_status = ?, email_sent_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (EmailStatus.SENT, datetime.now(), datetime.now(), participant_id),
            )

    def mark_email_failed(self, participant_id: int, error: str) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE participants
                SET email_status = ?, email_error = ?,
                    email_attempts = email_attempts + 1, updated_at = ?
                WHERE id = ?
                """,
                (EmailStatus.FAILED, error, datetime.now(), participant_id),
            )

    # -----------------------------------------------------------------------
    # Soft delete
    # -----------------------------------------------------------------------

    def soft_delete(self, participant_id: int) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                "UPDATE participants SET is_deleted = 1, updated_at = ? WHERE id = ?",
                (datetime.now(), participant_id),
            )

    def restore(self, participant_id: int) -> None:
        with self._db.transaction() as cur:
            cur.execute(
                "UPDATE participants SET is_deleted = 0, updated_at = ? WHERE id = ?",
                (datetime.now(), participant_id),
            )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_dict(p: Participant) -> dict:
        return {
            "id": p.id,
            "internal_id": p.internal_id,
            "project_id": p.project_id,
            "full_name": p.full_name,
            "email": p.email,
            "phone": p.phone,
            "college": p.college,
            "department": p.department,
            "designation": p.designation,
            "certificate_type": p.certificate_type,
            "remarks": p.remarks,
            "certificate_id": p.certificate_id,
            "match_status": p.match_status.value,
            "match_confidence": p.match_confidence,
            "email_status": p.email_status.value,
            "email_sent_at": p.email_sent_at,
            "email_attempts": p.email_attempts,
            "email_error": p.email_error,
            "is_deleted": int(p.is_deleted),
            "import_source": p.import_source,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }

    @staticmethod
    def _from_row(row: object) -> Participant:
        return Participant(
            id=row["id"],
            internal_id=row["internal_id"],
            project_id=row["project_id"],
            full_name=row["full_name"],
            email=row["email"],
            phone=row["phone"] or "",
            college=row["college"] or "",
            department=row["department"] or "",
            designation=row["designation"] or "",
            certificate_type=row["certificate_type"] or "",
            remarks=row["remarks"] or "",
            certificate_id=row["certificate_id"] or 0,
            match_status=MatchStatus(row["match_status"]),
            match_confidence=row["match_confidence"] or 0.0,
            email_status=EmailStatus(row["email_status"]),
            email_sent_at=row["email_sent_at"],
            email_attempts=row["email_attempts"] or 0,
            email_error=row["email_error"] or "",
            is_deleted=bool(row["is_deleted"]),
            import_source=row["import_source"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
