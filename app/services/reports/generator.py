"""
app.services.reports.generator
================================
Report generation for all major CDMS operations.

Supported formats: PDF (reportlab), Excel (XlsxWriter), CSV, plain text.
Reports are stored in the project's Reports/ folder and never overwrite
previous reports (each run generates a timestamped filename).
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ReportFormat(str, Enum):
    PDF = "pdf"
    EXCEL = "xlsx"
    CSV = "csv"
    TEXT = "txt"


class ReportType(str, Enum):
    RENAME = "rename"
    PARTICIPANT = "participant"
    EMAIL_DELIVERY = "email_delivery"
    FAILURE = "failure"
    DUPLICATE = "duplicate"
    PROJECT_SUMMARY = "project_summary"
    HISTORY = "history"


def _timestamped_filename(report_type: ReportType, fmt: ReportFormat) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{report_type.value}_{ts}.{fmt.value}"


class ReportGenerator:
    """
    Generates reports from structured data.

    Each public method accepts a list of row dicts and a list of column headers,
    then writes the report to ``output_dir`` in the requested format.
    """

    def generate(
        self,
        report_type: ReportType,
        columns: list[str],
        rows: list[dict[str, Any]],
        output_dir: Path,
        fmt: ReportFormat = ReportFormat.EXCEL,
        project_name: str = "",
        event_name: str = "",
    ) -> Path:
        """
        Generate a report file.

        :param report_type: Which kind of report this is.
        :param columns:     Ordered list of column header names.
        :param rows:        List of dicts with keys matching *columns*.
        :param output_dir:  Directory to write the report to.
        :param fmt:         Output format.
        :param project_name / event_name: Metadata for the report header.
        :returns: Path to the generated file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = _timestamped_filename(report_type, fmt)
        output_path = output_dir / filename

        if fmt == ReportFormat.CSV:
            self._write_csv(columns, rows, output_path)
        elif fmt == ReportFormat.EXCEL:
            self._write_excel(columns, rows, output_path, report_type, project_name, event_name)
        elif fmt == ReportFormat.PDF:
            self._write_pdf(columns, rows, output_path, report_type, project_name, event_name)
        elif fmt == ReportFormat.TEXT:
            self._write_text(columns, rows, output_path, project_name)

        logger.info("Report written: %s", output_path)
        return output_path

    # -----------------------------------------------------------------------
    # Writers
    # -----------------------------------------------------------------------

    @staticmethod
    def _write_csv(columns: list[str], rows: list[dict], path: Path) -> None:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _write_excel(
        columns: list[str],
        rows: list[dict],
        path: Path,
        report_type: ReportType,
        project_name: str,
        event_name: str,
    ) -> None:
        try:
            import xlsxwriter
        except ImportError:
            logger.warning("XlsxWriter not installed; falling back to CSV.")
            ReportGenerator._write_csv(columns, rows, path.with_suffix(".csv"))
            return

        workbook = xlsxwriter.Workbook(str(path))
        worksheet = workbook.add_worksheet("Report")

        # Formats
        header_fmt = workbook.add_format({
            "bold": True, "bg_color": "#1E3A5F", "font_color": "white",
            "border": 1, "align": "center",
        })
        cell_fmt = workbook.add_format({"border": 1, "text_wrap": True})
        title_fmt = workbook.add_format({"bold": True, "font_size": 14})

        # Title rows
        worksheet.write(0, 0, f"CDMS Report — {report_type.value.replace('_', ' ').title()}", title_fmt)
        worksheet.write(1, 0, f"Project: {project_name}  |  Event: {event_name}")
        worksheet.write(2, 0, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        row_offset = 4
        for col_idx, col_name in enumerate(columns):
            worksheet.write(row_offset, col_idx, col_name, header_fmt)
            worksheet.set_column(col_idx, col_idx, max(15, len(col_name) + 4))

        for row_idx, row_data in enumerate(rows, start=row_offset + 1):
            for col_idx, col_name in enumerate(columns):
                worksheet.write(row_idx, col_idx, row_data.get(col_name, ""), cell_fmt)

        workbook.close()

    @staticmethod
    def _write_pdf(
        columns: list[str],
        rows: list[dict],
        path: Path,
        report_type: ReportType,
        project_name: str,
        event_name: str,
    ) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
        except ImportError:
            logger.warning("reportlab not installed; falling back to CSV.")
            ReportGenerator._write_csv(columns, rows, path.with_suffix(".csv"))
            return

        doc = SimpleDocTemplate(str(path), pagesize=landscape(A4))
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"CDMS — {report_type.value.replace('_', ' ').title()} Report", styles["Title"]))
        elements.append(Paragraph(f"Project: {project_name} | Event: {event_name}", styles["Normal"]))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        table_data = [columns] + [[str(row.get(col, "")) for col in columns] for row in rows]
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4F8")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        elements.append(table)
        doc.build(elements)

    @staticmethod
    def _write_text(columns: list[str], rows: list[dict], path: Path, project_name: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"CDMS Report — Project: {project_name}\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            col_widths = [max(len(c), 12) for c in columns]
            header = "  ".join(c.ljust(w) for c, w in zip(columns, col_widths))
            f.write(header + "\n")
            f.write("-" * len(header) + "\n")
            for row in rows:
                line = "  ".join(str(row.get(c, "")).ljust(w) for c, w in zip(columns, col_widths))
                f.write(line + "\n")
