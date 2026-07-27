"""
app.ui.components.module_header
================================
Standard page header used by every module view.
Provides a consistent title, subtitle, and optional action buttons.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


class ModuleHeader(ctk.CTkFrame):
    """
    Consistent module header with title, description, and optional action row.

    Usage::

        header = ModuleHeader(
            parent, palette, fonts,
            title="Rename Certificates",
            subtitle="Analyze PDFs and extract participant names automatically.",
            actions=[("Analyze", callback, "primary")],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))
    """

    def __init__(
        self,
        parent,
        palette: ColorPalette,
        fonts: FontSystem,
        title: str,
        subtitle: str = "",
        actions: list[tuple[str, object, str]] | None = None,
    ) -> None:
        """
        :param actions: List of (label, command, kind) where kind is
                        "primary" | "secondary" | "danger".
        """
        super().__init__(parent, fg_color="transparent")
        self._palette = palette
        self._fonts = fonts
        self._action_buttons: dict[str, ctk.CTkButton] = {}

        # Title row
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x")

        ctk.CTkLabel(
            title_row, text=title,
            font=(fonts.family, fonts.size_xxl, "bold"),
            text_color=palette.text_primary,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Action buttons (top-right)
        if actions:
            for label, cmd, kind in actions:
                color = {
                    "primary": palette.accent,
                    "secondary": "transparent",
                    "danger": palette.error,
                }.get(kind, palette.accent)
                border = 1 if kind == "secondary" else 0
                btn = ctk.CTkButton(
                    title_row, text=label, width=140, height=36,
                    fg_color=color, border_width=border,
                    text_color=palette.text_primary if kind == "secondary" else palette.accent_text,
                    font=(fonts.family, fonts.size_sm),
                    command=cmd,
                )
                btn.pack(side="right", padx=4)
                self._action_buttons[label] = btn

        # Subtitle
        if subtitle:
            ctk.CTkLabel(
                self, text=subtitle,
                font=(fonts.family, fonts.size_sm),
                text_color=palette.text_secondary,
                anchor="w",
            ).pack(anchor="w", pady=(2, 0))

        # Divider
        ctk.CTkFrame(self, height=1, fg_color=palette.border).pack(
            fill="x", pady=(10, 0)
        )

    def set_button_state(self, label: str, state: str) -> None:
        """Enable or disable a header button. state: 'normal' | 'disabled'"""
        if label in self._action_buttons:
            self._action_buttons[label].configure(state=state)
