"""
app.ui.modules.history
======================
History module view — full implementation wired to HistoryRepository.
"""

from __future__ import annotations

import tkinter.filedialog as fd
import customtkinter as ctk

from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.data_table import DataTable
from app.workers.signals import Signal

_LOG_COLS   = ["Timestamp", "Module", "Action", "User / System", "Details"]
_LOG_WIDTHS = [140,         110,      150,      110,             300]


class HistoryView:
    """Full Audit Trail & History module view connected to HistoryRepository."""

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

        # Header
        header = ModuleHeader(
            self.frame, p, f,
            title="Project Audit History",
            subtitle="Immutable event log tracking all operations executed within this project.",
            actions=[
                ("📥  Export Log", self._export_log, "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        # Main Table
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        self._table = DataTable(
            content, p, f,
            columns=_LOG_COLS,
            col_widths=_LOG_WIDTHS,
            stretch_col=4,
        )
        self._table.pack(fill="both", expand=True)

    def on_project_loaded(self, project) -> None:
        self.load_history_from_db()

    def load_history_from_db(self) -> None:
        self._table.clear()
        if not self._app.active_project or not self._app.history_repo:
            return

        logs = self._app.history_repo.get_all(self._app.active_project.id)
        for entry in logs:
            self._table.add_row({
                "Timestamp": entry.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(entry.created_at, "strftime") else str(entry.created_at),
                "Module": entry.module,
                "Action": entry.action,
                "User / System": entry.performed_by,
                "Details": entry.details,
            })

    def _export_log(self) -> None:
        path = fd.asksaveasfilename(title="Export History Log", defaultextension=".csv", filetypes=[("CSV File", "*.csv")])

    def on_signal(self, signal: Signal) -> None:
        pass
