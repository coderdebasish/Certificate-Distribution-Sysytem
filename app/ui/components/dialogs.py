"""
app.ui.components.dialogs
==========================
Reusable dialog boxes: confirmation, error, info, input.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


class ConfirmDialog(ctk.CTkToplevel):
    """
    Modal confirmation dialog.

    Usage::

        dialog = ConfirmDialog(parent, palette, fonts,
                               title="Delete Participant",
                               message="Are you sure you want to delete Debasish Mohanty?",
                               detail="This action can be undone.")
        if dialog.result:
            ...
    """

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem,
                 title: str, message: str, detail: str = "",
                 confirm_text: str = "Confirm", danger: bool = False) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result = False

        self._palette = palette
        self._fonts = fonts

        self.configure(fg_color=palette.bg_secondary)
        self._build(title, message, detail, confirm_text, danger)
        self.wait_window()

    def _build(self, title, message, detail, confirm_text, danger) -> None:
        pad = {"padx": 24, "pady": 8}

        ctk.CTkLabel(self, text=title,
                     font=(self._fonts.family, self._fonts.size_lg, "bold"),
                     text_color=self._palette.text_primary).pack(**pad, pady=(20, 4))

        ctk.CTkLabel(self, text=message,
                     font=(self._fonts.family, self._fonts.size_md),
                     text_color=self._palette.text_primary).pack(**pad)

        if detail:
            ctk.CTkLabel(self, text=detail,
                         font=(self._fonts.family, self._fonts.size_sm),
                         text_color=self._palette.text_secondary).pack(**pad)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=24, pady=(12, 20))

        ctk.CTkButton(btn_frame, text="Cancel", width=100,
                      fg_color="transparent", border_width=1,
                      text_color=self._palette.text_primary,
                      command=self._cancel).pack(side="left", padx=4)

        confirm_color = self._palette.error if danger else self._palette.accent
        ctk.CTkButton(btn_frame, text=confirm_text, width=100,
                      fg_color=confirm_color,
                      command=self._confirm).pack(side="left", padx=4)

    def _confirm(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()


class ErrorDialog(ctk.CTkToplevel):
    """Display a user-friendly error message."""

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem,
                 title: str, message: str, details: str = "") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=palette.bg_secondary)

        ctk.CTkLabel(self, text="⚠  " + title,
                     font=(fonts.family, fonts.size_lg, "bold"),
                     text_color=palette.error).pack(padx=24, pady=(20, 4))
        ctk.CTkLabel(self, text=message,
                     font=(fonts.family, fonts.size_md),
                     text_color=palette.text_primary,
                     wraplength=380).pack(padx=24, pady=4)
        if details:
            ctk.CTkLabel(self, text=details,
                         font=(fonts.family, fonts.size_sm),
                         text_color=palette.text_secondary,
                         wraplength=380).pack(padx=24, pady=4)

        ctk.CTkButton(self, text="OK", width=100,
                      fg_color=palette.accent,
                      command=self.destroy).pack(pady=(12, 20))
        self.wait_window()
