"""
app.ui.app
===========
Main application controller.

Owns the root CTk window, active Project context, DatabaseConnection,
and Repositories. Swaps module views and handles signal queues.
"""

from __future__ import annotations

import logging
import queue
from pathlib import Path
from typing import Optional

import customtkinter as ctk

from app.config.constants import (
    APP_NAME, APP_SHORT_NAME, APP_VERSION,
    WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_DEFAULT_WIDTH, WINDOW_DEFAULT_HEIGHT,
    WINDOW_TITLE,
)
from app.config.settings import AppSettings
from app.database.connection import DatabaseConnection
from app.database.migrations import SchemaMigrator
from app.database.repositories.project_repo import ProjectRepository
from app.database.repositories.participant_repo import ParticipantRepository
from app.database.repositories.certificate_repo import CertificateRepository
from app.database.repositories.template_repo import TemplateRepository
from app.database.repositories.queue_repo import QueueRepository
from app.database.repositories.history_repo import HistoryRepository

from app.models.project import Project, ProjectStage, ProjectStatus
from app.ui.theme import get_palette, FONTS
from app.ui.dialogs.new_project_dialog import NewProjectDialog
from app.utils.file_utils import create_project_folders, get_database_path
from app.utils.logger import setup_logging

logger = logging.getLogger(__name__)


class CDMSApplication:
    """
    Top-level application controller.

    Manages active project context, database connection, and module navigation.
    """

    def __init__(self) -> None:
        self.settings = AppSettings.load()
        setup_logging()

        # Configure appearance (Enforce dark mode globally across entire software)
        self.settings.theme = "dark"
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.palette = get_palette("dark")

        # Root window
        self.root = ctk.CTk(fg_color=self.palette.bg_primary)
        self.root.configure(fg_color=self.palette.bg_primary)
        self.root.title(WINDOW_TITLE)
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.geometry(
            f"{self.settings.window_width}x{self.settings.window_height}"
        )
        if self.settings.window_maximized:
            self.root.state("zoomed")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Active project state
        self.active_project: Optional[Project] = None
        self.db: Optional[DatabaseConnection] = None
        self.project_repo: Optional[ProjectRepository] = None
        self.participant_repo: Optional[ParticipantRepository] = None
        self.certificate_repo: Optional[CertificateRepository] = None
        self.template_repo: Optional[TemplateRepository] = None
        self.queue_repo: Optional[QueueRepository] = None
        self.history_repo: Optional[HistoryRepository] = None

        # Signal queue for background workers
        self._signal_queue: queue.Queue = queue.Queue()
        self._current_module: str = "dashboard"

        # Build layout
        self._build_layout()
        self._bind_shortcuts()
        self._navigate("dashboard")

        # Start signal listener
        self._poll_signals()

        logger.info("CDMS %s initialized.", APP_VERSION)

    def run(self) -> None:
        """Start Tk loop."""
        self.root.mainloop()

    # -----------------------------------------------------------------------
    # Project Lifecycle
    # -----------------------------------------------------------------------

    def create_new_project(self, name: str, event_name: str, location_dir: str) -> None:
        """Create a new project folder, SQLite database, and run migrations."""
        try:
            proj_dir = Path(location_dir) / name.replace(" ", "_")
            create_project_folders(proj_dir)
            db_path = get_database_path(proj_dir)

            # Connect DB and run migrations
            self.db = DatabaseConnection(db_path)
            self.db.open()
            migrator = SchemaMigrator(self.db)
            migrator.migrate()

            # Init repos
            self.project_repo = ProjectRepository(self.db)
            self.participant_repo = ParticipantRepository(self.db)
            self.certificate_repo = CertificateRepository(self.db)
            self.template_repo = TemplateRepository(self.db)
            self.queue_repo = QueueRepository(self.db)
            self.history_repo = HistoryRepository(self.db)

            # Insert project record
            proj = Project(
                name=name,
                event_name=event_name,
                project_dir=str(proj_dir),
                database_path=str(db_path),
                stage=ProjectStage.CREATED,
                status=ProjectStatus.DRAFT,
            )
            self.active_project = self.project_repo.insert(proj)
            self.statusbar.set_db_status(True)
            self.topbar.set_project_name(name)

            # Notify active views
            self._notify_project_loaded()
            logger.info("Created and opened project: %s", name)
        except Exception as exc:
            logger.error("Failed to create project: %s", exc)
            self.statusbar.set_status(f"Error creating project: {exc}")

    def open_project(self, db_path_str: str) -> None:
        """Open an existing project SQLite database file."""
        try:
            db_path = Path(db_path_str)
            if not db_path.exists():
                return

            self.db = DatabaseConnection(db_path)
            self.db.open()
            migrator = SchemaMigrator(self.db)
            migrator.migrate()

            # Init repos
            self.project_repo = ProjectRepository(self.db)
            self.participant_repo = ParticipantRepository(self.db)
            self.certificate_repo = CertificateRepository(self.db)
            self.template_repo = TemplateRepository(self.db)
            self.queue_repo = QueueRepository(self.db)
            self.history_repo = HistoryRepository(self.db)

            projects = self.project_repo.get_all()
            if projects:
                self.active_project = projects[0]
                self.project_repo.touch_opened(self.active_project.id)
                self.topbar.set_project_name(self.active_project.name)

            self.statusbar.set_db_status(True)
            self._notify_project_loaded()
            logger.info("Opened project DB: %s", db_path)
        except Exception as exc:
            logger.error("Failed to open project DB: %s", exc)
            self.statusbar.set_status(f"Error opening project: {exc}")

    def _notify_project_loaded(self) -> None:
        """Inform created view modules that active project changed."""
        for view in self._module_views.values():
            if hasattr(view, "on_project_loaded"):
                view.on_project_loaded(self.active_project)

    # -----------------------------------------------------------------------
    # Layout & Shortcuts
    # -----------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        from app.ui.components.topbar import TopBar
        from app.ui.components.sidebar import Sidebar
        from app.ui.components.statusbar import StatusBar

        self.topbar = TopBar(self.root, self, self.palette, FONTS)
        self.topbar.frame.grid(row=0, column=0, columnspan=2, sticky="ew")

        self.sidebar = Sidebar(self.root, self, self.palette, FONTS)
        self.sidebar.frame.grid(row=1, column=0, sticky="ns")

        self.workspace = ctk.CTkFrame(self.root, fg_color=self.palette.bg_primary)
        self.workspace.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)
        self.workspace.grid_rowconfigure(0, weight=1)
        self.workspace.grid_columnconfigure(0, weight=1)

        self.statusbar = StatusBar(self.root, self, self.palette, FONTS)
        self.statusbar.frame.grid(row=2, column=0, columnspan=2, sticky="ew")

        self._module_views: dict = {}

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-n>", lambda e: self.open_new_project_dialog())
        self.root.bind("<Control-N>", lambda e: self.open_new_project_dialog())
        self.root.bind("<Control-s>", lambda e: self.save_current_project())
        self.root.bind("<Control-S>", lambda e: self.save_current_project())

    def open_new_project_dialog(self) -> None:
        NewProjectDialog(self.root, self.palette, FONTS, on_create=self.create_new_project)

    def save_current_project(self) -> None:
        self.topbar.set_save_status("Saving...")
        if self.active_project and self.project_repo:
            self.project_repo.update(self.active_project)
        self.root.after(600, lambda: self.topbar.set_save_status("All changes saved"))

    def _navigate(self, module_name: str) -> None:
        if self._current_module == module_name and module_name in self._module_views:
            return

        for view in self._module_views.values():
            view.frame.grid_remove()

        if module_name not in self._module_views:
            view_class = self._get_module_class(module_name)
            if view_class is None:
                logger.warning("Unknown module: %s", module_name)
                return
            view_inst = view_class(self.workspace, self, self.palette, FONTS)
            if hasattr(view_inst, "on_project_loaded") and self.active_project:
                view_inst.on_project_loaded(self.active_project)
            self._module_views[module_name] = view_inst

        view = self._module_views[module_name]
        view.frame.grid(row=0, column=0, sticky="nsew")
        self._current_module = module_name
        self.sidebar.set_active(module_name)
        self.topbar.set_module_name(module_name.replace("_", " ").title())

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

    def _poll_signals(self) -> None:
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

    def _on_close(self) -> None:
        self.settings.save()
        if self.db:
            self.db.close()
        logger.info("Application closing.")
        self.root.destroy()
