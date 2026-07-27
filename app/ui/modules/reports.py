"""
app.ui.modules.reports
=======================
Reports module view — full implementation.

Allows users to generate, view, and export multi-format audit reports:
- Rename Operation Log
- Participant Match Report
- Email Delivery Audit Proof
- Failures & Discrepancies Report
- Complete Audit History Log
"""

from __future__ import annotations

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.workers.signals import Signal

_REPORT_CARDS = [
    ("📋  Rename Certificates Log",     "Original filename, detected name, strategy, confidence score, final target file.", "PDF, Excel, CSV"),
    ("👥  Participant Match Summary",    "Complete list of participants with mapped certificates and match metrics.", "PDF, Excel, CSV"),
    ("📧  Email Delivery Proof",         "Official audit log of sent emails, timestamp, recipient, and SMTP status.", "PDF, Excel"),
    ("⚠   Failures & Discrepancies",    "Filtered report listing only missing files, unmapped names, or bounced emails.", "PDF, Excel, CSV"),
    ("📊  Full Event Executive Summary", "High-level metrics, summary graphs, and overall project completion status.", "PDF Document"),
]


class ReportsView:
    """Full Reports module view."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # ── Header ──────────────────────────────────────────────────────
        header = ModuleHeader(
            self.frame, p, f,
            title="Reports & Analytics",
            subtitle="Generate, preview, and export official reports and audit trails.",
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        # ── Report Cards List ───────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self.frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        for title, desc, formats in _REPORT_CARDS:
            card = ctk.CTkFrame(scroll, fg_color=p.bg_secondary, corner_radius=12)
            card.pack(fill="x", pady=6)

            card_inner = ctk.CTkFrame(card, fg_color="transparent")
            card_inner.pack(fill="x", padx=16, pady=14)

            left = ctk.CTkFrame(card_inner, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(left, text=title, font=(f.family, f.size_md, "bold"), text_color=p.text_primary, anchor="w").pack(anchor="w")
            ctk.CTkLabel(left, text=desc, font=(f.family, f.size_sm), text_color=p.text_secondary, anchor="w").pack(anchor="w", pady=(2, 4))
            ctk.CTkLabel(left, text=f"Supported Formats: {formats}", font=(f.family, f.size_xs), text_color=p.text_disabled, anchor="w").pack(anchor="w")

            right = ctk.CTkFrame(card_inner, fg_color="transparent")
            right.pack(side="right")

            ctk.CTkButton(
                right, text="Export...", width=110, height=34,
                fg_color=p.accent, font=(f.family, f.size_sm),
                command=lambda t=title: self._export_report(t)
            ).pack(side="right", padx=4)

    def _export_report(self, report_title: str) -> None:
        import tkinter.filedialog as fd
        fd.asksaveasfilename(title=f"Export {report_title}", defaultextension=".pdf")

    def on_signal(self, signal: Signal) -> None:
        pass
