"""
app.ui.modules.dashboard
=========================
Dashboard view — first screen shown on launch.

Displays: welcome card, project statistics, quick actions,
progress timeline, recent projects, and project health warnings.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal


class DashboardView:
    """Dashboard module view."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        # Module header
        ctk.CTkLabel(
            self.frame,
            text="Dashboard",
            font=(self._fonts.family, self._fonts.size_xxl, "bold"),
            text_color=self._palette.text_primary,
        ).pack(anchor="w", padx=24, pady=(24, 4))

        ctk.CTkLabel(
            self.frame,
            text="Overview of your certificate distribution projects.",
            font=(self._fonts.family, self._fonts.size_sm),
            text_color=self._palette.text_secondary,
        ).pack(anchor="w", padx=24, pady=(0, 16))

        # Quick actions row
        action_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        action_frame.pack(fill="x", padx=24, pady=8)

        ctk.CTkLabel(action_frame, text="Quick Actions",
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        btn_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 12))

        actions = [
            ("＋ New Project", lambda: print("New project")),
            ("📂 Open Project", lambda: print("Open project")),
            ("▶ Resume Last", lambda: print("Resume")),
        ]
        for text, cmd in actions:
            ctk.CTkButton(btn_row, text=text, width=160, height=40,
                          fg_color=self._palette.accent,
                          font=(self._fonts.family, self._fonts.size_sm),
                          command=cmd).pack(side="left", padx=6)

        # Recent projects placeholder
        recent_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        recent_frame.pack(fill="both", expand=True, padx=24, pady=8)

        ctk.CTkLabel(recent_frame, text="Recent Projects",
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        ctk.CTkLabel(recent_frame,
                     text="No recent projects.\nCreate a new project to get started.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary,
                     justify="center").pack(expand=True)

    def on_signal(self, signal: Signal) -> None:
        """Handle signals from background workers."""
        pass  # TODO: update statistics cards on relevant signals
