"""
app.ui.modules.participants
============================
Participant Management module view.

Supports Excel import wizard and manual entry.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal


class ParticipantsView:
    """Participant Management module view."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self.frame, text="Participants",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Manage event participants. Import from Excel or add manually.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        # Toolbar
        toolbar = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=8)
        toolbar.pack(fill="x", padx=24, pady=8)

        ctk.CTkButton(toolbar, text="＋ Add Participant", width=160, height=36,
                      fg_color=self._palette.accent,
                      command=self._add_participant).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(toolbar, text="📥 Import Excel", width=140, height=36,
                      fg_color=self._palette.accent,
                      command=self._import_excel).pack(side="left", padx=4, pady=8)

        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", self._on_search)
        ctk.CTkEntry(toolbar, placeholder_text="Search participants...",
                     textvariable=self._search_var,
                     width=240, height=36,
                     fg_color=self._palette.bg_tertiary,
                     text_color=self._palette.text_primary).pack(side="right", padx=8, pady=8)

        # Empty state
        self._content_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        self._content_frame.pack(fill="both", expand=True, padx=24, pady=8)

        ctk.CTkLabel(self._content_frame,
                     text="No participants yet.\nImport an Excel file or add participants manually.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary,
                     justify="center").pack(expand=True)

    def _add_participant(self) -> None:
        pass  # TODO: open AddParticipantDialog

    def _import_excel(self) -> None:
        pass  # TODO: open ImportWizardDialog → start ImportWorker

    def _on_search(self, *_) -> None:
        pass  # TODO: filter participant table rows

    def on_signal(self, signal: Signal) -> None:
        pass  # TODO: handle IMPORT_ROW_PROCESSED, IMPORT_COMPLETE
