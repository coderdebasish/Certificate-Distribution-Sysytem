"""
app.workers.rename_worker
==========================
Background worker that copies and renames analyzed certificate PDFs
into the project's Renamed Certificates folder.

Originals are NEVER modified.
"""

from __future__ import annotations

import logging
import queue
import shutil
from pathlib import Path
from typing import Optional

from app.workers.base_worker import BaseWorker
from app.workers.signals import Signal, SignalType

logger = logging.getLogger(__name__)


class RenameJob:
    """One rename operation: source → destination."""
    def __init__(self, cert_id: int, source_path: Path, destination_path: Path) -> None:
        self.cert_id = cert_id
        self.source_path = source_path
        self.destination_path = destination_path


class RenameWorker(BaseWorker):
    """
    Copies PDFs from their original location to the renamed destination.

    On success: emits CERTIFICATE_RENAMED with cert_id and new path.
    On failure: emits CERTIFICATE_FAILED with reason.
    """

    def __init__(
        self,
        jobs: list[RenameJob] | None = None,
        signal_queue: Optional[queue.Queue[Signal]] = None,
        db_conn=None,
        project_id: int = 0,
        source_dir: Path | str | None = None,
        dest_dir: Path | str | None = None,
    ) -> None:
        super().__init__(signal_queue=signal_queue)
        self._jobs = jobs or []
        self._db_conn = db_conn
        self._project_id = project_id
        self._source_dir = Path(source_dir) if source_dir else None
        self._dest_dir = Path(dest_dir) if dest_dir else None

    def _run(self) -> None:
        if not self._jobs and self._db_conn and self._project_id and self._source_dir and self._dest_dir:
            from app.database.repositories.certificate_repo import CertificateRepository
            from app.models.certificate import CertificateStatus
            repo = CertificateRepository(self._db_conn)
            certs = repo.get_all(self._project_id)
            for c in certs:
                if c.detected_name and c.status in (CertificateStatus.READY, CertificateStatus.NEEDS_REVIEW):
                    src = self._source_dir / c.original_filename
                    dst = self._dest_dir / f"{c.detected_name}.pdf"
                    self._jobs.append(RenameJob(cert_id=c.id, source_path=src, destination_path=dst))

        total = len(self._jobs)
        if total == 0:
            self._emit(Signal.error("No certificates ready to rename."))
            return

        self._emit(Signal.log(f"Starting rename of {total} certificate(s)..."))
        success = 0
        failed = 0

        for idx, job in enumerate(self._jobs, start=1):
            if self._should_stop():
                self._emit(Signal(type=SignalType.WORKER_STOPPED))
                return
            self._wait_if_paused()

            self._emit(Signal.progress(idx, total, f"Copying {job.source_path.name}"))

            try:
                job.destination_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(job.source_path), str(job.destination_path))
                success += 1

                if self._db_conn:
                    from app.database.repositories.certificate_repo import CertificateRepository
                    from app.models.certificate import CertificateStatus
                    repo = CertificateRepository(self._db_conn)
                    cert = repo.get_by_id(job.cert_id)
                    if cert:
                        cert.renamed_filename = job.destination_path.name
                        cert.renamed_file_path = str(job.destination_path)
                        cert.status = CertificateStatus.READY
                        repo.update(cert)

                self._emit(Signal(
                    type=SignalType.CERTIFICATE_RENAMED,
                    payload={
                        "cert_id": job.cert_id,
                        "destination": str(job.destination_path),
                        "filename": job.destination_path.name,
                    },
                ))
                self._emit(Signal.log(
                    f"  ✓ {job.source_path.name} → {job.destination_path.name}"
                ))
            except Exception as exc:
                failed += 1
                logger.error("Rename failed for %s: %s", job.source_path, exc)
                self._emit(Signal(
                    type=SignalType.CERTIFICATE_FAILED,
                    payload={"filename": job.source_path.name, "error": str(exc)},
                ))

        self._emit(Signal.complete(
            f"Rename complete — Success: {success} / Failed: {failed}"
        ))
