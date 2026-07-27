"""
app.ui.components.notification
===============================
Toast-style notification system (bottom-right, auto-dismiss).
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


class NotificationManager:
    """
    Manages a stack of toast notifications anchored to the bottom-right
    of the parent window.

    Usage::

        notif = NotificationManager(root, palette, fonts)
        notif.show("Project Saved", kind="success")
        notif.show("Email Sent", kind="info")
        notif.show("Certificate Missing", kind="error", auto_dismiss=False)
    """

    def __init__(self, parent: ctk.CTk, palette: ColorPalette, fonts: FontSystem) -> None:
        self._parent = parent
        self._palette = palette
        self._fonts = fonts
        self._toasts: list[ctk.CTkToplevel] = []

    def show(self, message: str, kind: str = "info", auto_dismiss: bool = True,
             duration_ms: int = 3500) -> None:
        color_map = {
            "success": self._palette.success,
            "warning": self._palette.warning,
            "error":   self._palette.error,
            "info":    self._palette.accent,
        }
        icon_map = {"success": "✓", "warning": "⚠", "error": "✗", "info": "ℹ"}
        color = color_map.get(kind, self._palette.accent)
        icon = icon_map.get(kind, "ℹ")

        toast = ctk.CTkToplevel(self._parent)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=self._palette.bg_secondary)

        ctk.CTkLabel(
            toast,
            text=f" {icon}  {message}",
            font=(self._fonts.family, self._fonts.size_sm),
            text_color=color,
        ).pack(padx=16, pady=10)

        if kind != "error":
            ctk.CTkButton(toast, text="✕", width=20, height=20,
                          fg_color="transparent",
                          text_color=self._palette.text_secondary,
                          command=lambda t=toast: self._dismiss(t)).pack(
                side="right", padx=4, pady=4)

        self._position_toast(toast)
        self._toasts.append(toast)

        if auto_dismiss and kind != "error":
            toast.after(duration_ms, lambda t=toast: self._dismiss(t))

    def _dismiss(self, toast: ctk.CTkToplevel) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        try:
            toast.destroy()
        except Exception:
            pass

    def _position_toast(self, toast: ctk.CTkToplevel) -> None:
        self._parent.update_idletasks()
        px = self._parent.winfo_x() + self._parent.winfo_width() - 320
        py = self._parent.winfo_y() + self._parent.winfo_height() - 100 - len(self._toasts) * 60
        toast.geometry(f"300x50+{px}+{py}")
