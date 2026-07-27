"""
app.workers.rename_worker
==========================
Background worker that copies and renames analyzed certificate PDFs
into the project's Renamed Certificates folder.

Originals are NEVER modified.
"""

from __future__ import annotations

import csv
import logging
import queue
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.utils.file_utils import sanitize_filename
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
        project_dir: Path | str | None = None,
    ) -> None:
        super().__init__(signal_queue=signal_queue)
        self._jobs = jobs or []
        self._db_conn = db_conn
        self._project_id = project_id
        self._source_dir = Path(source_dir) if source_dir else None
        self._dest_dir = Path(dest_dir) if dest_dir else None
        self._project_dir = Path(project_dir) if project_dir else (self._dest_dir.parent.parent if self._dest_dir else None)

    def _run(self) -> None:
        if not self._jobs and self._db_conn and self._project_id and self._source_dir and self._dest_dir:
            from app.database.repositories.certificate_repo import CertificateRepository
            from app.models.certificate import CertificateStatus
            repo = CertificateRepository(self._db_conn)
            certs = repo.get_all(self._project_id)
            used_dest_paths: set[Path] = set()

            for c in certs:
                if c.detected_name and c.status in (CertificateStatus.READY, CertificateStatus.NEEDS_REVIEW):
                    src = self._source_dir / c.original_filename
                    # fall back to original file path if the staged copy doesn't exist
                    if not src.exists() and c.original_file_path:
                        src = Path(c.original_file_path)
                    clean_name = sanitize_filename(c.detected_name)
                    dst = self._dest_dir / f"{clean_name}.pdf"
                    counter = 1
                    while dst in used_dest_paths or dst.exists():
                        dst = self._dest_dir / f"{clean_name} ({counter}).pdf"
                        counter += 1
                    used_dest_paths.add(dst)
                    self._jobs.append(RenameJob(cert_id=c.id, source_path=src, destination_path=dst))

        total = len(self._jobs)
        if total == 0:
            self._emit(Signal.error("No certificates ready to rename."))
            return

        self._emit(Signal.log(f"Starting rename of {total} certificate(s)..."))
        success = 0
        failed = 0
        audit_rows = []

        for idx, job in enumerate(self._jobs, start=1):
            if self._should_stop():
                self._emit(Signal(type=SignalType.WORKER_STOPPED))
                return
            self._wait_if_paused()

            self._emit(Signal.progress(idx, total, f"Copying {job.source_path.name} ({idx}/{total})"))

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
                        cert.status = CertificateStatus.RENAMED
                        repo.update(cert)
                        audit_rows.append({
                            "original_filename": cert.original_filename,
                            "renamed_filename": cert.renamed_filename,
                            "detected_name": cert.detected_name,
                            "method": cert.extraction_method.value,
                            "confidence": f"{cert.confidence:.1f}%",
                            "status": cert.status.value,
                            "timestamp": datetime.now().isoformat(),
                        })

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

        # Generate CSV Audit Report
        if audit_rows and self._project_dir:
            try:
                reports_dir = self._project_dir / "Reports"
                reports_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = reports_dir / f"Rename_Report_{stamp}.csv"
                with open(report_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        "original_filename", "renamed_filename", "detected_name",
                        "method", "confidence", "status", "timestamp"
                    ])
                    writer.writeheader()
                    writer.writerows(audit_rows)
                self._emit(Signal.log(f"Audit report generated: {report_path.name}"))
            except Exception as r_exc:
                logger.warning("Failed to generate audit report: %s", r_exc)

        self._emit(Signal.complete(
            f"Rename complete — Success: {success} / Failed: {failed}"
        ))
