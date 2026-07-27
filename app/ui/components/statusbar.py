"""
app.ui.components.statusbar
============================
Bottom status bar — always visible, never decorative.
"""

from __future__ import annotations
from datetime import datetime
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


class StatusBar:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkFrame(parent, fg_color=palette.statusbar_bg,
                                  corner_radius=0, height=28)
        self.frame.pack_propagate(False)
        self._build()
        self._tick()

    def _build(self) -> None:
        kw = dict(
            font=(self._fonts.family, self._fonts.size_xs),
            text_color=self._palette.statusbar_text,
        )

        self._status_label = ctk.CTkLabel(self.frame, text="  Ready", **kw)
        self._status_label.pack(side="left", padx=8)

        ctk.CTkLabel(self.frame, text="│", text_color=self._palette.border).pack(side="left")

        self._db_label = ctk.CTkLabel(self.frame, text="DB: —", **kw)
        self._db_label.pack(side="left", padx=8)

        ctk.CTkLabel(self.frame, text="│", text_color=self._palette.border).pack(side="left")

        self._bg_label = ctk.CTkLabel(self.frame, text="No background tasks", **kw)
        self._bg_label.pack(side="left", padx=8)

        # Clock (right side)
        self._clock_label = ctk.CTkLabel(self.frame, text="", **kw)
        self._clock_label.pack(side="right", padx=12)

    def set_status(self, text: str) -> None:
        self._status_label.configure(text=f"  {text}")

    def set_db_status(self, connected: bool) -> None:
        text = "DB: Connected" if connected else "DB: Disconnected"
        color = self._palette.success if connected else self._palette.error
        self._db_label.configure(text=text, text_color=color)

    def set_background_task(self, text: str) -> None:
        self._bg_label.configure(text=text)

    def _tick(self) -> None:
        self._clock_label.configure(text=datetime.now().strftime("%H:%M:%S"))
        self.frame.after(1000, self._tick)
