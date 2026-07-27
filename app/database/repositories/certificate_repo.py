"""
app.database.repositories.certificate_repo
==========================================
Database operations for Certificate records.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from app.database.connection import DatabaseConnection
from app.models.certificate import Certificate, ExtractionMethod, CertificateStatus

logger = logging.getLogger(__name__)


class CertificateRepository:
    """CRUD operations for Certificate records."""

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def insert(self, cert: Certificate) -> Certificate:
        with self._db.transaction() as cur:
            cur.execute(
                """
                INSERT INTO certificates (
                    project_id, original_filename, original_file_path,
                    renamed_filename, renamed_file_path, detected_name,
                    extraction_method, confidence, raw_extracted_text, status,
                    original_detected_name, manually_corrected, corrected_at,
                    is_ignored, is_duplicate, duplicate_of_id, failure_reason,
                    created_at, updated_at
                ) VALUES (
                    :project_id, :original_filename, :original_file_path,
                    :renamed_filename, :renamed_file_path, :detected_name,
                    :extraction_method, :confidence, :raw_extracted_text, :status,
                    :original_detected_name, :manually_corrected, :corrected_at,
                    :is_ignored, :is_duplicate, :duplicate_of_id, :failure_reason,
                    :created_at, :updated_at
                )
                """,
                self._to_dict(cert),
            )
            cert.id = cur.lastrowid  # type: ignore[assignment]
        return cert

    def get_by_id(self, cert_id: int) -> Optional[Certificate]:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT * FROM certificates WHERE id = ?", (cert_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def get_by_filename(self, project_id: int, filename: str) -> Optional[Certificate]:
        with self._db.read() as cur:
            row = cur.execute(
                "SELECT * FROM certificates WHERE project_id = ? AND original_filename = ?",
                (project_id, filename),
            ).fetchone()
        return self._from_row(row) if row else None

    def get_all(self, project_id: int) -> list[Certificate]:
        with self._db.read() as cur:
            rows = cur.execute(
                "SELECT * FROM certificates WHERE project_id = ? ORDER BY id",
                (project_id,),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def get_unmatched(self, project_id: int) -> list[Certificate]:
        """Return certificates not yet assigned to any participant."""
        with self._db.read() as cur:
            rows = cur.execute(
                """
                SELECT c.* FROM certificates c
                WHERE c.project_id = ?
                  AND c.is_ignored = 0
                  AND c.id NOT IN (
                    SELECT certificate_id FROM certificate_mappings
                    WHERE project_id = ?
                  )
                ORDER BY c.renamed_filename
                """,
                (project_id, project_id),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def update(self, cert: Certificate) -> None:
        cert.touch()
        with self._db.transaction() as cur:
            cur.execute(
                """
                UPDATE certificates SET
                    renamed_filename = :renamed_filename,
                    renamed_file_path = :renamed_file_path,
                    detected_name = :detected_name,
                    extraction_method = :extraction_method,
                    confidence = :confidence,
                    status = :status,
                    manually_corrected = :manually_corrected,
                    corrected_at = :corrected_at,
                    is_ignored = :is_ignored,
                    failure_reason = :failure_reason,
                    updated_at = :updated_at
                WHERE id = :id
                """,
                self._to_dict(cert),
            )

    def delete_by_project(self, project_id: int) -> None:
        with self._db.transaction() as cur:
            cur.execute("DELETE FROM certificates WHERE project_id = ?", (project_id,))

    def count(self, project_id: int) -> int:
        with self._db.read() as cur:
            return cur.execute(
                "SELECT COUNT(*) FROM certificates WHERE project_id = ? AND is_ignored = 0",
                (project_id,),
            ).fetchone()[0]

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _to_dict(c: Certificate) -> dict:
        return {
            "id": c.id,
            "project_id": c.project_id,
            "original_filename": c.original_filename,
            "original_file_path": c.original_file_path,
            "renamed_filename": c.renamed_filename,
            "renamed_file_path": c.renamed_file_path,
            "detected_name": c.detected_name,
            "extraction_method": c.extraction_method.value,
            "confidence": c.confidence,
            "raw_extracted_text": c.raw_extracted_text,
            "status": c.status.value,
            "original_detected_name": c.original_detected_name,
            "manually_corrected": int(c.manually_corrected),
            "corrected_at": c.corrected_at,
            "is_ignored": int(c.is_ignored),
            "is_duplicate": int(c.is_duplicate),
            "duplicate_of_id": c.duplicate_of_id,
            "failure_reason": c.failure_reason,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }

    @staticmethod
    def _from_row(row: object) -> Certificate:
        return Certificate(
            id=row["id"],
            project_id=row["project_id"],
            original_filename=row["original_filename"],
            original_file_path=row["original_file_path"],
            renamed_filename=row["renamed_filename"] or "",
            renamed_file_path=row["renamed_file_path"] or "",
            detected_name=row["detected_name"] or "",
            extraction_method=ExtractionMethod(row["extraction_method"]),
            confidence=row["confidence"] or 0.0,
            raw_extracted_text=row["raw_extracted_text"] or "",
            status=CertificateStatus(row["status"]),
            original_detected_name=row["original_detected_name"] or "",
            manually_corrected=bool(row["manually_corrected"]),
            corrected_at=row["corrected_at"],
            is_ignored=bool(row["is_ignored"]),
            is_duplicate=bool(row["is_duplicate"]),
            duplicate_of_id=row["duplicate_of_id"] or 0,
            failure_reason=row["failure_reason"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
