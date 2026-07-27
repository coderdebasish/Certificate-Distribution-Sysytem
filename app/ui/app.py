"""
app.ui.app
===========
Main application window.

CDMSApplication is the entry point for the entire UI. It:
  - Configures CustomTkinter
  - Creates the 4-zone layout (topbar, sidebar, workspace, statusbar)
  - Manages module switching
  - Polls background worker signal queues via after()
  - Binds global keyboard shortcuts
"""

from __future__ import annotations

import logging
import queue

import customtkinter as ctk

from app.config.constants import (
    APP_NAME, APP_SHORT_NAME, APP_VERSION,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    WINDOW_TITLE,
)
from app.config.settings import AppSettings
from app.ui.theme import get_palette, FONTS
from app.ui.dialogs.new_project_dialog import NewProjectDialog
from app.utils.logger import setup_logging

logger = logging.getLogger(__name__)


class CDMSApplication:
    """
    Top-level application controller.

    Owns the root CTk window and all child frames.
    Module views are created lazily and swapped in/out of the workspace frame.
    """

    def __init__(self) -> None:
        # Load settings first
        self.settings = AppSettings.load()
        setup_logging()

        # Configure CTk theme
        ctk.set_appearance_mode(self.settings.theme)
        ctk.set_default_color_theme("blue")

        self.palette = get_palette(self.settings.theme)

        # Root window
        self.root = ctk.CTk()
        self.root.title(WINDOW_TITLE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.geometry(
            f"{self.settings.window_width}x{self.settings.window_height}"
        )
        if self.settings.window_maximized:
            self.root.state("zoomed")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Signal queue for background workers
        self._signal_queue: queue.Queue = queue.Queue()

        # Current module name
        self._current_module: str = "dashboard"

        # Build layout
        self._build_layout()
        self._bind_shortcuts()
        self._navigate("dashboard")

        # Start polling worker signals
        self._poll_signals()

        logger.info("CDMS %s started.", APP_VERSION)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def run(self) -> None:
        """Start the Tk event loop."""
        self.root.mainloop()

    # -----------------------------------------------------------------------
    # Layout & Keyboard Shortcuts
    # -----------------------------------------------------------------------

    def _build_layout(self) -> None:
        """Construct the 4-zone layout."""
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        from app.ui.components.topbar import TopBar
        from app.ui.components.sidebar import Sidebar
        from app.ui.components.statusbar import StatusBar

        self.topbar = TopBar(self.root, self, self.palette, FONTS)
        self.topbar.frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.sidebar = Sidebar(self.root, self, self.palette, FONTS)
        self.sidebar.frame.grid(row=1, column=0, sticky="ns")

        # Workspace — module views are placed here
        self.workspace = ctk.CTkFrame(self.root, fg_color=self.palette.bg_primary)
        self.workspace.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.workspace.grid_rowconfigure(0, weight=1)
        self.workspace.grid_columnconfigure(0, weight=1)

        self.statusbar = StatusBar(self.root, self, self.palette, FONTS)
        self.statusbar.frame.grid(row=2, column=0, columnspan=2, sticky="ew")

        # Module view cache
        self._module_views: dict = {}

    def _bind_shortcuts(self) -> None:
        """Bind application-wide keyboard shortcuts."""
        self.root.bind("<Control-n>", lambda e: self.open_new_project_dialog())
        self.root.bind("<Control-N>", lambda e: self.open_new_project_dialog())
        self.root.bind("<Control-s>", lambda e: self.save_current_project())
        self.root.bind("<Control-S>", lambda e: self.save_current_project())

    # -----------------------------------------------------------------------
    # Navigation & Dialogs
    # -----------------------------------------------------------------------

    def open_new_project_dialog(self) -> None:
        NewProjectDialog(self.root, self.palette, FONTS, on_create=self._on_project_created)

    def _on_project_created(self, name: str, event: str, location: str) -> None:
        logger.info("Created project %s at %s", name, location)
        self.topbar.set_project_name(name)
        dashboard = self._module_views.get("dashboard")
        if dashboard:
            dashboard.set_project(name, event, stage_idx=0, status="draft")

    def save_current_project(self) -> None:
        self.topbar.set_save_status("Saving...")
        self.root.after(800, lambda: self.topbar.set_save_status("All changes saved"))

    def _navigate(self, module_name: str) -> None:
        """Switch the workspace to *module_name*."""
        if self._current_module == module_name and module_name in self._module_views:
            return

        # Hide previous
        for view in self._module_views.values():
            view.frame.grid_remove()

        # Create view lazily
        if module_name not in self._module_views:
            view_class = self._get_module_class(module_name)
            if view_class is None:
                logger.warning("Unknown module: %s", module_name)
                return
            self._module_views[module_name] = view_class(
                self.workspace, self, self.palette, FONTS
            )

        view = self._module_views[module_name]
        view.frame.grid(row=0, column=0, sticky="nsew")
        self._current_module = module_name
        self.sidebar.set_active(module_name)
        self.topbar.set_module_name(module_name.replace("_", " ").title())
        logger.debug("Navigated to: %s", module_name)

    @staticmethod
    def _get_module_class(name: str):
        from app.ui.modules.dashboard import DashboardView
        from app.ui.modules.rename import RenameView
        from app.ui.modules.participants import ParticipantsView
        from app.ui.modules.matching import MatchingView
        from app.ui.modules.templates import TemplatesView
        from app.ui.modules.sending import SendingView
        from app.ui.modules.reports import ReportsView
        from app.ui.modules.history import HistoryView
        from app.ui.modules.settings import SettingsView

        mapping = {
            "dashboard": DashboardView,
            "rename": RenameView,
            "participants": ParticipantsView,
            "matching": MatchingView,
            "templates": TemplatesView,
            "sending": SendingView,
            "reports": ReportsView,
            "history": HistoryView,
            "settings": SettingsView,
        }
        return mapping.get(name)

    # -----------------------------------------------------------------------
    # Signal polling
    # -----------------------------------------------------------------------

    def _poll_signals(self) -> None:
        """Check signal queue every 50 ms and dispatch to active view."""
        try:
            while True:
                signal = self._signal_queue.get_nowait()
                active_view = self._module_views.get(self._current_module)
                if active_view and hasattr(active_view, "on_signal"):
                    active_view.on_signal(signal)
        except queue.Empty:
            pass
        finally:
            self.root.after(50, self._poll_signals)

    # -----------------------------------------------------------------------
    # Close handler
    # -----------------------------------------------------------------------

    def _on_close(self) -> None:
        self.settings.save()
        logger.info("Application closing.")
        self.root.destroy()
