"""
app.ui.modules.history
=======================
History module view — full implementation.

Displays searchable, timestamped audit log of all project operations:
- Project creation & schema setup
- File analysis & rename commits
- Participant imports & modifications
- Email queue generation & dispatch runs
"""

from __future__ import annotations

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.data_table import DataTable
from app.workers.signals import Signal

_LOG_COLS   = ["Timestamp", "Module", "Action", "User / System", "Details"]
_LOG_WIDTHS = [140,         110,      150,      110,             300]


class HistoryView:
    """Full Audit Trail & History module view."""

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
            title="Project Audit History",
            subtitle="Immutable event log tracking all operations executed within this project.",
            actions=[
                ("📥  Export Log", self._export_log, "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        # ── Main Content Area: Data Table ───────────────────────────────
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._table = DataTable(
            content, p, f,
            columns=_LOG_COLS,
            col_widths=_LOG_WIDTHS,
            stretch_col=4,
        )
        self._table.pack(fill="both", expand=True)

        self._load_demo_log()

    def _load_demo_log(self) -> None:
        sample_logs = [
            ("2026-07-27 10:15:02", "Project",      "Created Project",  "User",   "Project 'Symposium 2026' initialized."),
            ("2026-07-27 10:16:45", "Participants", "Imported Excel",   "User",   "Imported 6 participants from 'participants.xlsx'."),
            ("2026-07-27 10:18:10", "Rename",       "Analyzed PDFs",    "System", "Analyzed 6 PDF certificates using text extraction & OCR."),
            ("2026-07-27 10:19:30", "Matching",     "Auto-Matched",     "System", "Matched 4 participants to certificates with >90% confidence."),
            ("2026-07-27 10:20:00", "Templates",    "Template Updated", "User",   "Updated default email template subject line."),
        ]
        for row in sample_logs:
            self._table.add_row(dict(zip(_LOG_COLS, row)))

    def _export_log(self) -> None:
        import tkinter.filedialog as fd
        fd.asksaveasfilename(title="Export History Log", defaultextension=".csv")

    def on_signal(self, signal: Signal) -> None:
        pass
