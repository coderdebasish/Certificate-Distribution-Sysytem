"""
app.ui.modules.history
=======================
History module view — displays the complete user action audit trail.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal


class HistoryView:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self.frame, text="History",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Complete audit trail of all actions performed in this project.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        toolbar = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=8)
        toolbar.pack(fill="x", padx=24, pady=8)

        self._search_var = ctk.StringVar()
        ctk.CTkEntry(toolbar, placeholder_text="Search history...",
                     textvariable=self._search_var,
                     width=300, height=36,
                     fg_color=self._palette.bg_tertiary,
                     text_color=self._palette.text_primary).pack(side="left", padx=8, pady=8)

        ctk.CTkButton(toolbar, text="Export History", width=140, height=36,
                      fg_color=self._palette.accent,
                      command=self._export).pack(side="right", padx=8, pady=8)

        content = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        content.pack(fill="both", expand=True, padx=24, pady=8)

        self._log_box = ctk.CTkTextbox(content, state="disabled",
                                        fg_color=self._palette.bg_tertiary,
                                        text_color=self._palette.text_primary,
                                        font=(self._fonts.family, self._fonts.size_sm))
        self._log_box.pack(fill="both", expand=True, padx=16, pady=12)

    def _export(self) -> None:
        pass  # TODO: export history via ReportGenerator

    def on_signal(self, signal: Signal) -> None:
        pass
