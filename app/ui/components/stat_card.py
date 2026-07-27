"""
app.ui.components.stat_card
============================
Reusable statistics card widget.
Shows a metric with icon, title, large value, and optional subtitle.
Used by Dashboard and other summary panels.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


class StatCard(ctk.CTkFrame):
    """
    A compact card displaying a single metric.

    Usage::

        card = StatCard(parent, palette, fonts,
                        icon="👥", title="Participants",
                        value="524", subtitle="Imported",
                        accent_color="#1565C0")
        card.pack(side="left", padx=8)
        card.set_value("526")   # Animate update
    """

    def __init__(
        self,
        parent,
        palette: ColorPalette,
        fonts: FontSystem,
        icon: str = "📊",
        title: str = "Metric",
        value: str = "—",
        subtitle: str = "",
        accent_color: str = "",
        width: int = 180,
        height: int = 110,
    ) -> None:
        accent = accent_color or palette.accent
        super().__init__(
            parent,
            fg_color=palette.bg_secondary,
            corner_radius=12,
            width=width,
            height=height,
            border_width=2,
            border_color=accent,
        )
        self.pack_propagate(False)
        self._palette = palette
        self._fonts = fonts
        self._accent = accent

        # Accent stripe on left
        stripe = ctk.CTkFrame(self, width=4, fg_color=accent, corner_radius=0)
        stripe.pack(side="left", fill="y", padx=(0, 0))

        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=10)

        # Top row: icon + title
        top = ctk.CTkFrame(content, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=icon, font=(fonts.family, fonts.size_md),
                     text_color=accent).pack(side="left")
        ctk.CTkLabel(top, text=f"  {title}",
                     font=(fonts.family, fonts.size_sm),
                     text_color=palette.text_secondary).pack(side="left")

        # Value (large)
        self._value_label = ctk.CTkLabel(
            content, text=value,
            font=(fonts.family, fonts.size_xxl, "bold"),
            text_color=palette.text_primary,
            anchor="w",
        )
        self._value_label.pack(anchor="w", pady=(4, 0))

        # Subtitle
        if subtitle:
            ctk.CTkLabel(content, text=subtitle,
                         font=(fonts.family, fonts.size_xs),
                         text_color=palette.text_disabled).pack(anchor="w")

    def set_value(self, value: str) -> None:
        """Update the displayed metric value."""
        self._value_label.configure(text=value)
