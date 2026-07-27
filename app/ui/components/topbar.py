"""
app.ui.components.topbar
=========================
Top navigation bar: logo, project name, module name, save status,
search, undo/redo, settings, notifications.
"""

from __future__ import annotations
import customtkinter as ctk
from app.config.constants import APP_SHORT_NAME, APP_VERSION
from app.ui.theme import ColorPalette, FontSystem


class TopBar:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkFrame(parent, fg_color=palette.topbar_bg,
                                  corner_radius=0, height=52)
        self.frame.pack_propagate(False)
        self._build()

    def _build(self) -> None:
        # Logo / app name
        ctk.CTkLabel(
            self.frame, text=f"  {APP_SHORT_NAME}",
            font=(self._fonts.family, self._fonts.size_lg, "bold"),
            text_color=self._palette.accent,
        ).pack(side="left", padx=(12, 4))

        # Version
        ctk.CTkLabel(
            self.frame, text=f"v{APP_VERSION}",
            font=(self._fonts.family, self._fonts.size_xs),
            text_color=self._palette.text_disabled,
        ).pack(side="left", padx=(0, 16))

        # Separator
        ctk.CTkLabel(self.frame, text="│",
                     text_color=self._palette.border).pack(side="left")

        # Project / module name (updated by app._navigate)
        self._project_label = ctk.CTkLabel(
            self.frame, text="No project open",
            font=(self._fonts.family, self._fonts.size_sm),
            text_color=self._palette.text_secondary,
        )
        self._project_label.pack(side="left", padx=8)

        self._module_label = ctk.CTkLabel(
            self.frame, text="Dashboard",
            font=(self._fonts.family, self._fonts.size_sm, "bold"),
            text_color=self._palette.text_primary,
        )
        self._module_label.pack(side="left", padx=4)

        # Save status (right side)
        self._save_label = ctk.CTkLabel(
            self.frame, text="",
            font=(self._fonts.family, self._fonts.size_xs),
            text_color=self._palette.text_disabled,
        )
        self._save_label.pack(side="right", padx=12)

        # Settings button
        ctk.CTkButton(
            self.frame, text="⚙", width=36, height=36,
            fg_color="transparent", hover_color=self._palette.bg_hover,
            text_color=self._palette.topbar_text,
            command=lambda: self._app._navigate("settings"),
        ).pack(side="right", padx=4)

        # Search
        self._search_var = ctk.StringVar()
        ctk.CTkEntry(
            self.frame, placeholder_text="Search...",
            width=200, height=32,
            textvariable=self._search_var,
            fg_color=self._palette.bg_tertiary,
            text_color=self._palette.text_primary,
        ).pack(side="right", padx=8)

    # -----------------------------------------------------------------------
    # Public update methods
    # -----------------------------------------------------------------------

    def set_module_name(self, name: str) -> None:
        self._module_label.configure(text=name)

    def set_project_name(self, name: str) -> None:
        self._project_label.configure(text=name)

    def set_save_status(self, status: str) -> None:
        self._save_label.configure(text=status)
