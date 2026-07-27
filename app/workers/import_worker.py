"""
app.workers.import_worker
==========================
Background worker for importing participants from an Excel file.

Validates every row, detects duplicates, and emits progress signals.
The UI thread never blocks during large imports.
"""

from __future__ import annotations

import logging
import queue
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from app.workers.base_worker import BaseWorker
from app.workers.signals import Signal, SignalType

logger = logging.getLogger(__name__)


@dataclass
class ImportRow:
    """One validated participant row ready for database insertion."""
    row_number: int
    name: str
    email: str
    phone: str = ""
    college: str = ""
    department: str = ""
    designation: str = ""
    remarks: str = ""
    is_valid: bool = True
    error_message: str = ""


class ImportWorker(BaseWorker):
    """
    Reads an Excel file, validates rows, and emits ImportRow signals.

    The actual database insertion is handled by the module controller
    that listens to ``IMPORT_ROW_PROCESSED`` signals.

    Column mapping is provided by the caller (result of the import wizard).
    """

    def __init__(
        self,
        file_path: Path | str,
        column_mapping: dict[str, str] | None = None,
        existing_emails: set[str] | None = None,
        signal_queue: Optional[queue.Queue[Signal]] = None,
        db_conn=None,
        project_id: int = 0,
    ) -> None:
        super().__init__(signal_queue=signal_queue)
        self._file_path = Path(file_path)
        self._column_mapping = column_mapping or {}
        self._existing_emails = existing_emails or set()
        self._db_conn = db_conn
        self._project_id = project_id

    def _run(self) -> None:
        self._emit(Signal.log(f"Opening {self._file_path.name}..."))

        try:
            rows = self._read_excel()
        except Exception as exc:
            self._emit(Signal.error(
                message=f"Cannot read Excel file: {self._file_path.name}",
                details=str(exc),
            ))
            return

        total = len(rows)
        self._emit(Signal.log(f"{total} row(s) found in spreadsheet."))

        valid = 0
        invalid = 0

        for idx, raw_row in enumerate(rows, start=1):
            if self._should_stop():
                self._emit(Signal(type=SignalType.WORKER_STOPPED))
                return

            self._emit(Signal.progress(idx, total, f"Processing row {idx}"))
            import_row = self._validate_row(idx, raw_row)

            if import_row.is_valid:
                valid += 1
                if self._db_conn and self._project_id:
                    try:
                        from app.database.repositories.participant_repo import ParticipantRepository
                        from app.models.participant import Participant
                        repo = ParticipantRepository(self._db_conn)
                        p = Participant(
                            project_id=self._project_id,
                            full_name=import_row.name,
                            email=import_row.email,
                            phone=import_row.phone,
                            college=import_row.college,
                            department=import_row.department,
                            designation=import_row.designation,
                            remarks=import_row.remarks,
                            import_source=self._file_path.name,
                        )
                        repo.insert(p)
                    except Exception as exc:
                        logger.warning("Failed to save participant into database: %s", exc)
            else:
                invalid += 1

            self._emit(Signal(
                type=SignalType.IMPORT_ROW_PROCESSED,
                payload={
                    "row": import_row,
                    "is_valid": import_row.is_valid,
                    "error": import_row.error_message,
                },
            ))

        self._emit(Signal(
            type=SignalType.IMPORT_COMPLETE,
            payload={"total": total, "valid": valid, "invalid": invalid},
        ))
        self._emit(Signal.complete(
            f"Import parsed — Valid: {valid} / Invalid: {invalid} / Total: {total}"
        ))

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _read_excel(self) -> list[dict[str, Any]]:
        ext = self._file_path.suffix.lower()
        if ext == ".csv":
            import csv
            data = []
            with open(self._file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.reader(f)
                try:
                    headers = [str(h).strip() for h in next(reader)]
                except StopIteration:
                    return []
                for row in reader:
                    if not row or not any(row):
                        continue
                    row_dict = {headers[i]: (str(row[i]).strip() if i < len(row) and row[i] is not None else "") for i in range(len(headers))}
                    data.append(row_dict)
            return data
        else:
            import openpyxl
            wb = openpyxl.load_workbook(str(self._file_path), read_only=True, data_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            try:
                headers = [str(h).strip() if h else "" for h in next(rows_iter)]
            except StopIteration:
                wb.close()
                return []
            data = []
            for row in rows_iter:
                if not row or not any(row):
                    continue
                row_dict = {headers[i]: (str(cell).strip() if i < len(row) and cell is not None else "") for i, cell in enumerate(row) if i < len(headers)}
                data.append(row_dict)
            wb.close()
            return data

    def _validate_row(self, row_number: int, raw_row: dict[str, Any]) -> ImportRow:
        def get(field: str) -> str:
            target_col = self._column_mapping.get(field, field)
            if not target_col or target_col == "(Skip Column)":
                return ""
            target_clean = str(target_col).strip().lower()

            if target_col in raw_row and raw_row[target_col] is not None:
                val = str(raw_row[target_col]).strip()
                if val:
                    return val

            for k, v in raw_row.items():
                if k and str(k).strip().lower() == target_clean:
                    return str(v or "").strip()
            return ""

        name = get("full_name")
        email = get("email")

        if not name:
            return ImportRow(row_number=row_number, name=name, email=email,
                             is_valid=False, error_message="Name is required.")
        if not email or "@" not in email:
            return ImportRow(row_number=row_number, name=name, email=email,
                             is_valid=False, error_message=f"Invalid email: '{email}'")
        if email.lower() in {e.lower() for e in self._existing_emails}:
            return ImportRow(row_number=row_number, name=name, email=email,
                             is_valid=False, error_message=f"Duplicate email: {email}")

        return ImportRow(
            row_number=row_number,
            name=name,
            email=email,
            phone=get("phone"),
            college=get("college"),
            department=get("department"),
            designation=get("designation"),
            remarks=get("remarks"),
            is_valid=True,
        )
