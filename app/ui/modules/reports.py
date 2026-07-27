"""
app.ui.modules.reports
=======================
Reports module view.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal


class ReportsView:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self.frame, text="Reports",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Generate and export detailed reports for every operation.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        reports_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        reports_frame.pack(fill="both", expand=True, padx=24, pady=8)

        report_types = [
            ("Rename Report",        "Original filename → detected name → method → confidence"),
            ("Participant Report",   "All participants with match and email status"),
            ("Email Delivery",       "Sent time, status, attempts, errors"),
            ("Failure Report",       "Only failed operations with reasons"),
            ("Project Summary",      "High-level overview with totals"),
            ("History Report",       "Complete user action audit trail"),
        ]

        for title, description in report_types:
            row = ctk.CTkFrame(reports_frame, fg_color=self._palette.bg_tertiary, corner_radius=8)
            row.pack(fill="x", padx=16, pady=4)
            ctk.CTkLabel(row, text=title,
                         font=(self._fonts.family, self._fonts.size_md, "bold"),
                         text_color=self._palette.text_primary).pack(side="left", padx=12, pady=8)
            ctk.CTkLabel(row, text=description,
                         font=(self._fonts.family, self._fonts.size_sm),
                         text_color=self._palette.text_secondary).pack(side="left", padx=4)
            ctk.CTkButton(row, text="Generate", width=100, height=30,
                          fg_color=self._palette.accent,
                          command=lambda t=title: self._generate(t)).pack(side="right", padx=12, pady=8)

    def _generate(self, report_type: str) -> None:
        pass  # TODO: call ReportGenerator

    def on_signal(self, signal: Signal) -> None:
        pass
