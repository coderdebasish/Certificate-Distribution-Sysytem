"""
app.ui.modules.matching
========================
Certificate Matching module view.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal


class MatchingView:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self.frame, text="Certificate Matching",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Match participants to their renamed certificates automatically.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        toolbar = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=8)
        toolbar.pack(fill="x", padx=24, pady=8)
        ctk.CTkButton(toolbar, text="🔗 Auto Match All", width=160, height=36,
                      fg_color=self._palette.accent,
                      command=self._auto_match).pack(side="left", padx=8, pady=8)

        content = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        content.pack(fill="both", expand=True, padx=24, pady=8)
        ctk.CTkLabel(content,
                     text="Complete 'Rename Certificates' and 'Participants' steps first.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary,
                     justify="center").pack(expand=True)

    def _auto_match(self) -> None:
        pass  # TODO: run NameMatcher on participants + certificates

    def on_signal(self, signal: Signal) -> None:
        pass
