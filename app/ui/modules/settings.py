"""
app.ui.modules.settings
========================
Settings module view — grouped by category.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal


class SettingsView:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self.frame, text="Settings",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Configure application preferences.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        scroll = ctk.CTkScrollableFrame(self.frame, fg_color=self._palette.bg_primary)
        scroll.pack(fill="both", expand=True, padx=24, pady=8)

        # Appearance
        self._section(scroll, "Appearance")
        theme_row = self._row(scroll, "Theme")
        ctk.CTkOptionMenu(theme_row, values=["dark", "light"], width=140,
                          fg_color=self._palette.bg_tertiary,
                          text_color=self._palette.text_primary).pack(side="right")

        accent_row = self._row(scroll, "Accent Color")
        ctk.CTkOptionMenu(accent_row, values=["blue", "purple", "green", "orange", "gray"],
                          width=140, fg_color=self._palette.bg_tertiary,
                          text_color=self._palette.text_primary).pack(side="right")

        # General
        self._section(scroll, "General")
        autosave_row = self._row(scroll, "Auto Save Interval (seconds)")
        ctk.CTkEntry(autosave_row, width=100, placeholder_text="120",
                     fg_color=self._palette.bg_tertiary,
                     text_color=self._palette.text_primary).pack(side="right")

        # Email
        self._section(scroll, "Email")
        delay_row = self._row(scroll, "Default Send Delay (seconds)")
        ctk.CTkEntry(delay_row, width=100, placeholder_text="5",
                     fg_color=self._palette.bg_tertiary,
                     text_color=self._palette.text_primary).pack(side="right")

        retry_row = self._row(scroll, "Max Retries")
        ctk.CTkEntry(retry_row, width=100, placeholder_text="3",
                     fg_color=self._palette.bg_tertiary,
                     text_color=self._palette.text_primary).pack(side="right")

        # Save button
        ctk.CTkButton(scroll, text="Save Settings", width=160, height=40,
                      fg_color=self._palette.accent,
                      command=self._save).pack(anchor="e", pady=16)

    def _section(self, parent, title: str) -> None:
        ctk.CTkLabel(parent, text=title,
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", pady=(16, 4))

    def _row(self, parent, label: str) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color=self._palette.bg_secondary, corner_radius=8)
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text=label,
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_primary).pack(side="left", padx=12, pady=10)
        return row

    def _save(self) -> None:
        pass  # TODO: read values, update AppSettings, persist

    def on_signal(self, signal: Signal) -> None:
        pass
