"""
app.ui.modules.templates
=========================
Email Template Editor module view.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal


class TemplatesView:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self.frame, text="Email Templates",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Write one template with {name} placeholders — generates personalized emails for all.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        # Split: editor (left) + preview (right)
        split = ctk.CTkFrame(self.frame, fg_color="transparent")
        split.pack(fill="both", expand=True, padx=24, pady=8)
        split.grid_columnconfigure(0, weight=1)
        split.grid_columnconfigure(1, weight=1)
        split.grid_rowconfigure(0, weight=1)

        editor_frame = ctk.CTkFrame(split, fg_color=self._palette.bg_secondary, corner_radius=12)
        editor_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        ctk.CTkLabel(editor_frame, text="Editor",
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        self._subject_var = ctk.StringVar()
        ctk.CTkEntry(editor_frame, placeholder_text="Email Subject (supports {event_name})",
                     textvariable=self._subject_var, height=36,
                     fg_color=self._palette.bg_tertiary,
                     text_color=self._palette.text_primary).pack(fill="x", padx=16, pady=4)

        self._body_text = ctk.CTkTextbox(editor_frame,
                                         fg_color=self._palette.bg_tertiary,
                                         text_color=self._palette.text_primary)
        self._body_text.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        preview_frame = ctk.CTkFrame(split, fg_color=self._palette.bg_secondary, corner_radius=12)
        preview_frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        ctk.CTkLabel(preview_frame, text="Preview",
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        self._preview_text = ctk.CTkTextbox(preview_frame, state="disabled",
                                             fg_color=self._palette.bg_tertiary,
                                             text_color=self._palette.text_primary)
        self._preview_text.pack(fill="both", expand=True, padx=16, pady=(4, 12))

    def on_signal(self, signal: Signal) -> None:
        pass
