"""
app.ui.theme
=============
Centralized theme and color system for CDMS.

All UI colors, fonts, and sizes are defined here.
Modules import from this file — never hardcode colors elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    # Background layers
    bg_primary: str      # Main window background
    bg_secondary: str    # Card / panel background
    bg_tertiary: str     # Input field background
    bg_hover: str        # Hover state

    # Sidebar
    sidebar_bg: str
    sidebar_active: str
    sidebar_text: str
    sidebar_text_active: str

    # Topbar
    topbar_bg: str
    topbar_text: str

    # Statusbar
    statusbar_bg: str
    statusbar_text: str

    # Accent
    accent: str
    accent_hover: str
    accent_text: str

    # Semantic colors
    success: str
    warning: str
    error: str
    info: str

    # Text
    text_primary: str
    text_secondary: str
    text_disabled: str

    # Table
    table_row_even: str
    table_row_odd: str
    table_header: str
    table_selected: str

    # Card / Input (aliases)
    bg_card: str
    bg_input: str

    # Border
    border: str


DARK_PALETTE = ColorPalette(
    bg_primary="#1A1A2E",
    bg_secondary="#16213E",
    bg_tertiary="#0F3460",
    bg_hover="#1E2A45",
    sidebar_bg="#0D1B2A",
    sidebar_active="#1565C0",
    sidebar_text="#B0BEC5",
    sidebar_text_active="#FFFFFF",
    topbar_bg="#0D1B2A",
    topbar_text="#ECEFF1",
    statusbar_bg="#0D1B2A",
    statusbar_text="#78909C",
    accent="#1565C0",
    accent_hover="#1976D2",
    accent_text="#FFFFFF",
    success="#2E7D32",
    warning="#E65100",
    error="#C62828",
    info="#1565C0",
    text_primary="#ECEFF1",
    text_secondary="#B0BEC5",
    text_disabled="#546E7A",
    table_row_even="#16213E",
    table_row_odd="#1A2744",
    table_header="#0D1B2A",
    table_selected="#1565C0",
    bg_card="#16213E",
    bg_input="#0F3460",
    border="#37474F",
)

LIGHT_PALETTE = ColorPalette(
    bg_primary="#F5F7FA",
    bg_secondary="#FFFFFF",
    bg_tertiary="#EEF2F7",
    bg_hover="#E3EAF4",
    sidebar_bg="#1E3A5F",
    sidebar_active="#1565C0",
    sidebar_text="#B0C4DE",
    sidebar_text_active="#FFFFFF",
    topbar_bg="#1E3A5F",
    topbar_text="#FFFFFF",
    statusbar_bg="#E8EDF4",
    statusbar_text="#546E7A",
    accent="#1565C0",
    accent_hover="#1976D2",
    accent_text="#FFFFFF",
    success="#2E7D32",
    warning="#E65100",
    error="#C62828",
    info="#1565C0",
    text_primary="#1A1A2E",
    text_secondary="#546E7A",
    text_disabled="#90A4AE",
    table_row_even="#FFFFFF",
    table_row_odd="#F5F7FA",
    table_header="#1E3A5F",
    table_selected="#BBDEFB",
    bg_card="#FFFFFF",
    bg_input="#EEF2F7",
    border="#CFD8DC",
)


@dataclass(frozen=True)
class FontSystem:
    family: str = "Segoe UI"
    size_xs: int = 10
    size_sm: int = 12
    size_md: int = 14
    size_lg: int = 18
    size_xl: int = 24
    size_xxl: int = 32


FONTS = FontSystem()


def get_palette(theme: str) -> ColorPalette:
    return DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
