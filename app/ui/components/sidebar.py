"""
app.ui.components.sidebar
==========================
Left navigation sidebar component.
Supports expanded (text + icon) and collapsed (icon-only) modes.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem

NAV_ITEMS = [
    ("dashboard",     "🏠",  "Dashboard"),
    ("rename",        "✏️",  "Rename Certificates"),
    ("participants",  "👥",  "Participants"),
    ("matching",      "🔗",  "Certificate Matching"),
    ("templates",     "📄",  "Email Templates"),
    ("sending",       "📧",  "Send Certificates"),
    ("reports",       "📊",  "Reports"),
    ("history",       "🕐",  "History"),
    ("settings",      "⚙️",  "Settings"),
    ("help",          "❓",  "Help"),
]


class Sidebar:
    """Left navigation sidebar with collapse support."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._collapsed = False
        self._active_module = "dashboard"
        self._buttons: dict[str, ctk.CTkButton] = {}

        self.frame = ctk.CTkFrame(parent, fg_color=palette.sidebar_bg, corner_radius=0)
        self._build()

    def _build(self) -> None:
        self.frame.grid_rowconfigure(len(NAV_ITEMS) + 1, weight=1)

        # Collapse toggle
        toggle = ctk.CTkButton(
            self.frame, text="☰", width=40, fg_color="transparent",
            text_color=self._palette.sidebar_text,
            hover_color=self._palette.sidebar_active,
            command=self._toggle_collapse,
        )
        toggle.grid(row=0, column=0, padx=8, pady=(12, 4), sticky="ew")

        for idx, (key, icon, label) in enumerate(NAV_ITEMS, start=1):
            btn = ctk.CTkButton(
                self.frame,
                text=f"  {icon}  {label}",
                anchor="w",
                fg_color="transparent",
                text_color=self._palette.sidebar_text,
                hover_color=self._palette.sidebar_active,
                font=(self._fonts.family, self._fonts.size_sm),
                command=lambda k=key: self._app._navigate(k),
                height=40,
                corner_radius=8,
            )
            btn.grid(row=idx, column=0, padx=8, pady=2, sticky="ew")
            self._buttons[key] = btn

    def set_active(self, module_name: str) -> None:
        for key, btn in self._buttons.items():
            if key == module_name:
                btn.configure(fg_color=self._palette.sidebar_active,
                              text_color=self._palette.sidebar_text_active)
            else:
                btn.configure(fg_color="transparent",
                              text_color=self._palette.sidebar_text)
        self._active_module = module_name

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        for key, btn in self._buttons.items():
            icon = next(i for k, i, _ in NAV_ITEMS if k == key)
            if self._collapsed:
                btn.configure(text=icon, width=40)
            else:
                label = next(l for k, _, l in NAV_ITEMS if k == key)
                btn.configure(text=f"  {icon}  {label}")
