"""
app.ui.modules.reports
======================
Reports module view — full implementation wired to ReportGenerator and active project database.
"""

from __future__ import annotations

import tkinter.filedialog as fd
import customtkinter as ctk
from pathlib import Path

from app.services.reports.generator import ReportGenerator, ReportType, ReportFormat
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.workers.signals import Signal

_REPORT_CARDS = [
    ("📋  Rename Certificates Log",     ReportType.RENAME,          "Original filename, detected name, strategy, confidence score, final target file."),
    ("👥  Participant Match Summary",    ReportType.PARTICIPANT,     "Complete list of participants with mapped certificates and match metrics."),
    ("📧  Email Delivery Proof",         ReportType.EMAIL_DELIVERY,  "Official audit log of sent emails, timestamp, recipient, and SMTP status."),
    ("⚠   Failures & Discrepancies",    ReportType.FAILURE,         "Filtered report listing only missing files, unmapped names, or bounced emails."),
    ("📊  Full Event Executive Summary", ReportType.PROJECT_SUMMARY, "High-level metrics, summary graphs, and overall project completion status."),
]


class ReportsView:
    """Full Reports module view connected to ReportGenerator."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._generator = ReportGenerator()

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Header
        header = ModuleHeader(
            self.frame, p, f,
            title="Reports & Analytics",
            subtitle="Generate, preview, and export official reports and audit trails.",
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        # Cards
        scroll = ctk.CTkScrollableFrame(self.frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        for title, r_type, desc in _REPORT_CARDS:
            card = ctk.CTkFrame(scroll, fg_color=p.bg_secondary, corner_radius=12)
            card.pack(fill="x", pady=6)

            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="x", padx=16, pady=14)

            left = ctk.CTkFrame(card_inner, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(left, text=title, font=(f.family, f.size_md, "bold"), text_color=p.text_primary, anchor="w").pack(anchor="w")
            ctk.CTkLabel(left, text=desc, font=(f.family, f.size_sm), text_color=p.text_secondary, anchor="w").pack(anchor="w", pady=(2, 4))
            ctk.CTkLabel(left, text="Supported Formats: PDF, Excel, CSV, Plain Text", font=(f.family, f.size_xs), text_color=p.text_disabled, anchor="w").pack(anchor="w")

            right = ctk.CTkFrame(card_inner, fg_color="transparent")
            right.pack(side="right")

            ctk.CTkButton(
                right, text="Export PDF", width=95, height=32,
                fg_color=p.accent, font=(f.family, f.size_xs, "bold"),
                command=lambda rt=r_type: self._export_report(rt, ReportFormat.PDF)
            ).pack(side="right", padx=2)

            ctk.CTkButton(
                right, text="Export Excel", width=95, height=32,
                fg_color=p.bg_tertiary, text_color=p.text_primary, font=(f.family, f.size_xs, "bold"),
                command=lambda rt=r_type: self._export_report(rt, ReportFormat.EXCEL)
            ).pack(side="right", padx=2)

    def _export_report(self, report_type: ReportType, fmt: ReportFormat) -> None:
        if not self._app.active_project:
            self._app.statusbar.set_status("Open a project to export reports.")
            return

        proj = self._app.active_project
        out_dir = Path(proj.project_dir) / "Reports"

        # Build columns and rows from DB
        cols, rows = self._gather_report_data(report_type)

        try:
            path = self._generator.generate(
                report_type=report_type,
                columns=cols,
                rows=rows,
                output_dir=out_dir,
                fmt=fmt,
                project_name=proj.name,
                event_name=proj.event_name,
            )
            self._app.statusbar.set_status(f"Report exported to {path.name}")
        except Exception as exc:
            self._app.statusbar.set_status(f"Report export failed: {exc}")

    def _gather_report_data(self, report_type: ReportType) -> tuple[list[str], list[dict]]:
        proj_id = self._app.active_project.id
        if report_type == ReportType.PARTICIPANT:
            cols = ["ID", "Name", "Email", "College", "Match Status", "Email Status"]
            participants = self._app.participant_repo.get_all(proj_id) if self._app.participant_repo else []
            rows = [{
                "ID": str(p.id), "Name": p.full_name, "Email": p.email,
                "College": p.college, "Match Status": p.match_status.value,
                "Email Status": p.email_status.value,
            } for p in participants]
            return cols, rows

        elif report_type == ReportType.RENAME:
            cols = ["Original File", "Detected Name", "Confidence", "Method", "Status"]
            certs = self._app.certificate_repo.get_all(proj_id) if self._app.certificate_repo else []
            rows = [{
                "Original File": c.original_filename, "Detected Name": c.detected_name,
                "Confidence": f"{c.confidence:.0f}%", "Method": c.extraction_method.value,
                "Status": c.status.value,
            } for c in certs]
            return cols, rows

        else:
            cols = ["Metric", "Value"]
            rows = [
                {"Metric": "Project Name", "Value": self._app.active_project.name},
                {"Metric": "Event Name", "Value": self._app.active_project.event_name},
                {"Metric": "Total Participants", "Value": str(self._app.active_project.participant_count)},
                {"Metric": "Emails Sent", "Value": str(self._app.active_project.emails_sent)},
            ]
            return cols, rows

    def on_signal(self, signal: Signal) -> None:
        pass
