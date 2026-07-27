"""
app.ui.modules.rename
======================
Standalone module view for analyzing certificate PDFs, detecting recipient names,
rendering live PDF page previews during sequential processing, displaying ETA,
and batch copying renamed files to an output directory.

Works 100% standalone — no active project database required!
"""

from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path
import shutil
import time
import tkinter as tk
from tkinter import filedialog as fd
import customtkinter as ctk

from app.models.certificate import Certificate, CertificateStatus, ExtractionMethod
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.ui.components.module_header import ModuleHeader
from app.ui.components.pdf_viewer import PDFViewer
from app.ui.components.dialogs import ConfirmDialog
from app.utils.file_utils import sanitize_filename
from app.workers.ocr_worker import OCRWorker
from app.workers.rename_worker import RenameWorker, RenameJob
from app.workers.signals import Signal, SignalType

logger = logging.getLogger(__name__)

_FILTER_TABS = ["All", "Ready", "Needs Review", "Failed", "Ignored"]
_TABLE_COLS  = ["#", "Original File", "Detected Name", "Confidence", "Method", "Status"]
_TABLE_WIDTHS = [35, 140, 160, 75, 75, 90]


def format_seconds(seconds: int) -> str:
    """Format seconds into MM:SS or HH:MM:SS string."""
    if seconds < 0:
        seconds = 0
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class RenameView:
    """Standalone module view for analyzing and batch-renaming certificate PDFs."""

    def __init__(self, parent: ctk.CTkFrame, app, palette, fonts) -> None:
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary, corner_radius=0)
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self._active_filter = "All"
        self._analysis_running = False
        self._is_paused = False
        self._analyzed_count = 0
        self._selected_row: dict | None = None
        self._ocr_worker: OCRWorker | None = None
        self._rename_worker: RenameWorker | None = None

        # Standalone in-memory dataset
        self._certificates: list[Certificate] = []
        self._cert_map: dict[str, Certificate] = {}  # filename -> Certificate

        self._build_ui()

    def _build_ui(self) -> None:
        p, f = self._palette, self._fonts

        # Header with Reset Session action
        self._header = ModuleHeader(
            self.frame, p, f,
            title="Rename Certificates",
            subtitle="Scan certificate PDFs, extract recipient names via OCR & layout analysis, and generate renamed files.",
            actions=[
                ("↺  Reset Session",   self._reset_session,  "secondary"),
                ("↺  Dry Run",         self._dry_run,        "secondary"),
                ("✓  Commit Rename",   self._commit_rename,  "primary"),
                ("★  Mark All Ready",  self._mark_all_ready, "secondary"),
            ],
        )
        self._header.pack(fill="x", padx=24, pady=(16, 10))
        self._header.set_button_state("↺  Dry Run", "disabled")
        self._header.set_button_state("✓  Commit Rename", "disabled")
        self._header.set_button_state("★  Mark All Ready", "disabled")

        # Import Card with Dual Directory Selectors (Source & Output)
        import_card = ctk.CTkFrame(self.frame, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        import_card.pack(fill="x", padx=24, pady=(0, 8))

        # Row 1: Source Directory
        src_row = ctk.CTkFrame(import_card, fg_color="transparent")
        src_row.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(src_row, text="Source Directory:", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary, width=130, anchor="w").pack(side="left")
        self._source_folder_var = ctk.StringVar(value="")
        self._source_entry = ctk.CTkEntry(
            src_row, textvariable=self._source_folder_var, font=(f.family, f.size_sm), height=32,
            fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary,
            placeholder_text="Select folder containing PDF certificates..."
        )
        self._source_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._browse_src_btn = ctk.CTkButton(
            src_row, text="Browse Source...", width=120, height=32,
            fg_color=p.bg_secondary, hover_color=p.bg_hover, text_color=p.text_primary,
            command=self._browse_source_folder,
        )
        self._browse_src_btn.pack(side="left", padx=(0, 8))

        self._analyze_btn = ctk.CTkButton(
            src_row, text="▶  Start Analysis", width=160, height=32, fg_color=p.accent,
            text_color=p.accent_text, command=self._start_analysis, state="disabled"
        )
        self._analyze_btn.pack(side="left")

        # Row 2: Output Directory
        out_row = ctk.CTkFrame(import_card, fg_color="transparent")
        out_row.pack(fill="x", padx=16, pady=(4, 10))

        ctk.CTkLabel(out_row, text="Output Directory:", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary, width=130, anchor="w").pack(side="left")
        self._output_folder_var = ctk.StringVar(value="")
        self._output_entry = ctk.CTkEntry(
            out_row, textvariable=self._output_folder_var, font=(f.family, f.size_sm), height=32,
            fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary,
            placeholder_text="Destination folder for renamed certificates..."
        )
        self._output_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._browse_out_btn = ctk.CTkButton(
            out_row, text="Browse Output...", width=120, height=32,
            fg_color=p.bg_secondary, hover_color=p.bg_hover, text_color=p.text_primary,
            command=self._browse_output_folder,
        )
        self._browse_out_btn.pack(side="left", padx=(0, 8))

        self._file_count_label = ctk.CTkLabel(out_row, text="", font=(f.family, f.size_xs), text_color=p.text_disabled, width=160, anchor="w")
        self._file_count_label.pack(side="left")

        # Progress bar frame with Pause/Cancel controls and real-time ETA
        self._progress_frame = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=8)
        
        prog_top = ctk.CTkFrame(self._progress_frame, fg_color="transparent")
        prog_top.pack(fill="x", padx=16, pady=(8, 2))
        
        self._progress_label = ctk.CTkLabel(prog_top, text="", font=(f.family, f.size_xs, "bold"), text_color=p.text_primary)
        self._progress_label.pack(side="left")

        self._eta_label = ctk.CTkLabel(prog_top, text="", font=(f.family, f.size_xs), text_color=p.accent)
        self._eta_label.pack(side="left", padx=(16, 0))

        self._cancel_btn = ctk.CTkButton(
            prog_top, text="⏹ Cancel", width=70, height=22, fg_color=p.error, hover_color=p.error,
            font=(f.family, f.size_xs, "bold"), command=self._cancel_worker
        )
        self._cancel_btn.pack(side="right", padx=(4, 0))

        self._pause_btn = ctk.CTkButton(
            prog_top, text="⏸ Pause", width=70, height=22, fg_color=p.bg_input, hover_color=p.bg_hover,
            text_color=p.text_primary, font=(f.family, f.size_xs), command=self._toggle_pause
        )
        self._pause_btn.pack(side="right", padx=4)

        self._progress_bar = ctk.CTkProgressBar(self._progress_frame, height=6)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=16, pady=(0, 8))

        # Filter Tabs & Search
        tab_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        tab_frame.pack(fill="x", padx=24, pady=(0, 4))
        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        for tab in _FILTER_TABS:
            btn = ctk.CTkButton(
                tab_frame, text=tab, height=30, width=110,
                fg_color=p.bg_secondary if tab != "All" else p.accent,
                hover_color=p.bg_hover,
                text_color=p.accent_text if tab == "All" else p.text_secondary,
                font=(f.family, f.size_xs, "bold"), corner_radius=6,
                command=lambda t=tab: self._set_filter(t),
            )
            btn.pack(side="left", padx=2)
            self._tab_buttons[tab] = btn

        # Search Entry
        self._search_var = ctk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh_table())
        self._search_entry = ctk.CTkEntry(
            tab_frame, placeholder_text="🔍 Search file or name...",
            textvariable=self._search_var, width=220, height=30,
            fg_color=p.bg_input, border_color=p.border, font=(f.family, f.size_xs)
        )
        self._search_entry.pack(side="right", padx=(8, 0))

        # Main content
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=6)
        content.grid_columnconfigure(1, weight=4)

        # Left: table
        left_frame = ctk.CTkFrame(content, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self._table = DataTable(
            left_frame, p, f,
            columns=_TABLE_COLS,
            col_widths=_TABLE_WIDTHS,
            stretch_col=2,
            on_select=self._on_row_select,
            on_double_click=self._on_row_double_click,
            context_menu=[
                ("✓  Mark as Ready",  self._mark_selected_ready),
                ("✏  Edit Name",      self._edit_selected),
                ("👁  Ignore",         self._ignore_selected),
                ("---", None),
                ("🗑  Remove Row",     self._remove_selected),
            ],
        )
        self._table.pack(fill="both", expand=True)

        # Right: PDF preview + edit panel
        right_frame = ctk.CTkFrame(content, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Detail header
        detail_header = ctk.CTkFrame(right_frame, fg_color="transparent", height=36)
        detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        ctk.CTkLabel(detail_header, text="Certificate Inspector & Live Preview", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left")

        # PDF preview canvas
        preview_frame = ctk.CTkFrame(right_frame, fg_color=p.bg_secondary, corner_radius=6)
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        self._pdf_viewer = PDFViewer(preview_frame, palette=p, fonts=f)
        self._pdf_viewer.pack(fill="both", expand=True)

        # Inspector controls
        edit_panel = ctk.CTkFrame(right_frame, fg_color="transparent")
        edit_panel.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 12))

        labels = [("File", "—"), ("Detected Name", "—"), ("Method", "—"), ("Confidence", "—"), ("New Filename", "—")]
        self._detail_rows: dict[str, ctk.CTkLabel] = {}
        for lbl_text, default_val in labels:
            r = ctk.CTkFrame(edit_panel, fg_color="transparent", height=22)
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text=f"{lbl_text}:", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary, width=110, anchor="w").pack(side="left")
            val_lbl = ctk.CTkLabel(r, text=default_val, font=(f.family, f.size_xs), text_color=p.text_primary, anchor="w")
            val_lbl.pack(side="left", fill="x", expand=True)
            self._detail_rows[lbl_text] = val_lbl

        # Edit Name Entry
        edit_name_row = ctk.CTkFrame(edit_panel, fg_color="transparent")
        edit_name_row.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(edit_name_row, text="Correct Name:", font=(f.family, f.size_xs, "bold"), text_color=p.text_primary).pack(anchor="w")
        self._edit_name_var = ctk.StringVar()
        self._edit_entry = ctk.CTkEntry(
            edit_name_row, textvariable=self._edit_name_var,
            font=(f.family, f.size_sm), height=32,
            fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary
        )
        self._edit_entry.pack(fill="x", pady=(2, 4))

        btn_row = ctk.CTkFrame(edit_panel, fg_color="transparent")
        btn_row.pack(fill="x")
        self._save_name_btn = ctk.CTkButton(
            btn_row, text="✓ Save Name", height=30,
            fg_color=p.accent, text_color=p.accent_text,
            command=self._save_manual_name,
        )
        self._save_name_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self._mark_ready_btn = ctk.CTkButton(
            btn_row, text="★ Mark Ready", height=30,
            fg_color=p.success, text_color="#FFFFFF",
            command=self._mark_selected_ready,
        )
        self._mark_ready_btn.pack(side="right", fill="x", expand=True, padx=(4, 0))

        # Bottom status bar
        bottom_bar = ctk.CTkFrame(self.frame, fg_color=p.bg_card, height=36, corner_radius=0)
        bottom_bar.pack(fill="x", side="bottom")
        self._status_label = ctk.CTkLabel(bottom_bar, text="  Select a source folder containing PDF certificates to begin.", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._status_label.pack(side="left", padx=16)
        self._summary_label = ctk.CTkLabel(bottom_bar, text="", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary)
        self._summary_label.pack(side="right", padx=16)

        # Check if project context is loaded (optional enhancement)
        if hasattr(self._app, "active_project") and self._app.active_project:
            imp_dir = Path(self._app.active_project.project_dir) / "Certificates" / "Imported"
            if imp_dir.exists() and list(imp_dir.glob("*.pdf")):
                self._source_folder_var.set(str(imp_dir))
                self._output_folder_var.set(str(Path(self._app.active_project.project_dir) / "Renamed Certificates"))
                count = len(list(imp_dir.glob("*.pdf")))
                self._file_count_label.configure(text=f"  {count} staged PDF(s)", text_color=p.success)
                self._analyze_btn.configure(state="normal")

    # -----------------------------------------------------------------------
    # Directory & Session Controls
    # -----------------------------------------------------------------------

    def _browse_source_folder(self) -> None:
        folder = fd.askdirectory(title="Select Source Folder Containing Certificate PDFs")
        if not folder:
            return
        src_path = Path(folder)
        self._source_folder_var.set(str(src_path))
        
        # Auto-default output folder if empty or using previous auto-path
        if not self._output_folder_var.get() or "Renamed_Certificates" in self._output_folder_var.get():
            self._output_folder_var.set(str(src_path / "Renamed_Certificates"))

        pdfs = list(src_path.glob("*.pdf"))
        count = len(pdfs)
        self._file_count_label.configure(
            text=f"  {count} PDF file{'s' if count != 1 else ''} found" if count > 0 else "  No PDF files found",
            text_color=self._palette.success if count > 0 else self._palette.error,
        )
        if count > 0:
            self._analyze_btn.configure(state="normal")
        else:
            self._analyze_btn.configure(state="disabled")

    def _browse_output_folder(self) -> None:
        folder = fd.askdirectory(title="Select Output Folder for Renamed Certificates")
        if folder:
            self._output_folder_var.set(folder)

    def _reset_session(self) -> None:
        """Reset the session to allow analyzing a new folder cleanly."""
        self._cancel_worker()
        self._certificates.clear()
        self._cert_map.clear()
        self._table.clear()
        self._pdf_viewer.clear()
        self._selected_row = None

        self._source_folder_var.set("")
        self._output_folder_var.set("")
        self._file_count_label.configure(text="")
        self._analyze_btn.configure(state="disabled", text="▶  Start Analysis")

        for lbl in self._detail_rows.values():
            lbl.configure(text="—")
        self._edit_name_var.set("")

        self._header.set_button_state("↺  Dry Run", "disabled")
        self._header.set_button_state("✓  Commit Rename", "disabled")
        self._header.set_button_state("★  Mark All Ready", "disabled")

        self._progress_frame.pack_forget()
        self._set_status("Session reset. Select a source folder to start.")
        self._summary_label.configure(text="")

    # -----------------------------------------------------------------------
    # Analysis Workflow
    # -----------------------------------------------------------------------

    def _start_analysis(self) -> None:
        src_path_str = self._source_folder_var.get().strip()
        if not src_path_str:
            return

        source_folder = Path(src_path_str)
        if not source_folder.exists():
            self._set_status("Error: Source folder does not exist.")
            return

        out_path_str = self._output_folder_var.get().strip()
        if not out_path_str:
            out_path_str = str(source_folder / "Renamed_Certificates")
            self._output_folder_var.set(out_path_str)

        Path(out_path_str).mkdir(parents=True, exist_ok=True)

        self._certificates.clear()
        self._cert_map.clear()
        self._table.clear()
        self._analysis_running = True
        self._is_paused = False
        self._analyzed_count = 0

        self._pause_btn.configure(text="⏸ Pause")
        self._progress_frame.pack(fill="x", padx=24, pady=(0, 4))
        self._progress_bar.set(0)
        self._progress_label.configure(text="Initializing worker...")
        self._eta_label.configure(text="")
        self._analyze_btn.configure(state="disabled", text="Analyzing...")
        self._set_status("Analyzing certificates sequentially...")

        self._ocr_worker = OCRWorker(
            signal_queue=self._app._signal_queue,
            pdf_folder=source_folder,
            db_conn=getattr(self._app, "db", None),
            project_id=self._app.active_project.id if getattr(self._app, "active_project", None) else 0,
            ocr_threshold=getattr(self._app.settings, "ocr_confidence_threshold", 70.0),
        )
        self._ocr_worker.start()

    def _toggle_pause(self) -> None:
        active_worker = self._ocr_worker or self._rename_worker
        if active_worker and active_worker.is_running():
            if self._is_paused:
                active_worker.resume()
                self._is_paused = False
                self._pause_btn.configure(text="⏸ Pause")
                self._set_status("Resumed processing.")
            else:
                active_worker.pause()
                self._is_paused = True
                self._pause_btn.configure(text="▶ Resume")
                self._set_status("Paused processing.")

    def _cancel_worker(self) -> None:
        active_worker = self._ocr_worker or self._rename_worker
        if active_worker and active_worker.is_running():
            active_worker.stop()
            self._set_status("Cancelling background process...")

    # -----------------------------------------------------------------------
    # Table Rendering & Category Filtering
    # -----------------------------------------------------------------------

    def _refresh_table(self) -> None:
        self._table.clear()
        search_query = self._search_var.get().strip().lower()

        ready, review, failed = 0, 0, 0

        for i, c in enumerate(self._certificates, start=1):
            if c.status == CertificateStatus.READY:
                ready += 1
            elif c.status in (CertificateStatus.NEEDS_REVIEW, CertificateStatus.PENDING):
                review += 1
            elif c.status in (CertificateStatus.FAILED, CertificateStatus.ENCRYPTED_PDF, CertificateStatus.CORRUPTED_FILE):
                failed += 1

            tag = TAG_SUCCESS if c.status == CertificateStatus.READY else \
                  TAG_WARNING if c.status in (CertificateStatus.NEEDS_REVIEW, CertificateStatus.PENDING) else \
                  TAG_ERROR if c.status in (CertificateStatus.FAILED, CertificateStatus.ENCRYPTED_PDF, CertificateStatus.CORRUPTED_FILE) else TAG_DISABLED

            if self._active_filter != "All":
                if self._active_filter == "Ready" and c.status != CertificateStatus.READY:
                    continue
                if self._active_filter == "Needs Review" and c.status not in (CertificateStatus.NEEDS_REVIEW, CertificateStatus.PENDING):
                    continue
                if self._active_filter == "Failed" and c.status not in (CertificateStatus.FAILED, CertificateStatus.ENCRYPTED_PDF, CertificateStatus.CORRUPTED_FILE):
                    continue
                if self._active_filter == "Ignored" and c.status != CertificateStatus.IGNORED:
                    continue

            if search_query:
                if search_query not in c.original_filename.lower() and search_query not in c.detected_name.lower():
                    continue

            self._table.add_row({
                "#": str(i),
                "Original File": c.original_filename,
                "Detected Name": c.detected_name or "???",
                "Confidence": f"{c.confidence:.0f}%",
                "Method": c.extraction_method.value.upper() if hasattr(c.extraction_method, "value") else str(c.extraction_method).upper(),
                "Status": c.status.value.title().replace("_", " ") if hasattr(c.status, "value") else str(c.status).title().replace("_", " "),
            }, tag=tag)

        if self._certificates:
            self._header.set_button_state("↺  Dry Run", "normal")
            self._header.set_button_state("✓  Commit Rename", "normal")
            self._header.set_button_state("★  Mark All Ready", "normal")
            self._update_summary(ready, review, failed)

    def _set_filter(self, tab: str) -> None:
        self._active_filter = tab
        for name, btn in self._tab_buttons.items():
            active = (name == tab)
            btn.configure(
                fg_color=self._palette.accent if active else self._palette.bg_secondary,
                text_color=self._palette.accent_text if active else self._palette.text_secondary
            )
        self._refresh_table()

    # -----------------------------------------------------------------------
    # Commit Rename & Dry Run
    # -----------------------------------------------------------------------

    def _commit_rename(self) -> None:
        src_dir_str = self._source_folder_var.get().strip()
        out_dir_str = self._output_folder_var.get().strip()
        if not src_dir_str or not out_dir_str:
            self._set_status("Please select valid Source and Output directories.")
            return

        source_dir = Path(src_dir_str)
        dest_dir = Path(out_dir_str)
        dest_dir.mkdir(parents=True, exist_ok=True)

        ready_certs = [c for c in self._certificates if c.detected_name and c.status in (CertificateStatus.READY, CertificateStatus.NEEDS_REVIEW)]
        if not ready_certs:
            self._set_status("No certificates ready to rename.")
            return

        dialog = ConfirmDialog(
            self.frame.winfo_toplevel(), self._palette, self._fonts,
            title="Confirm Rename",
            message=f"Copy and rename {len(ready_certs)} certificate(s) to the output directory?\n\nDestination: {dest_dir.name}",
            confirm_text="Rename Files", danger=False,
        )
        if not dialog.result:
            return

        self._set_status("Renaming certificates...")
        self._is_paused = False
        self._pause_btn.configure(text="⏸ Pause")
        self._progress_frame.pack(fill="x", padx=24, pady=(0, 4))
        self._progress_bar.set(0)

        # Build RenameJobs
        jobs = []
        used_dest_paths: set[Path] = set()
        for c in ready_certs:
            src = source_dir / c.original_filename
            if not src.exists() and c.original_file_path:
                src = Path(c.original_file_path)
            clean_name = sanitize_filename(c.detected_name)
            dst = dest_dir / f"{clean_name}.pdf"
            counter = 1
            while dst in used_dest_paths or dst.exists():
                dst = dest_dir / f"{clean_name} ({counter}).pdf"
                counter += 1
            used_dest_paths.add(dst)
            jobs.append(RenameJob(cert_id=c.id, source_path=src, destination_path=dst))

        self._rename_worker = RenameWorker(
            jobs=jobs,
            signal_queue=self._app._signal_queue,
            db_conn=getattr(self._app, "db", None),
            project_id=self._app.active_project.id if getattr(self._app, "active_project", None) else 0,
            source_dir=source_dir,
            dest_dir=dest_dir,
            project_dir=dest_dir,
        )
        self._rename_worker.start()

    def _dry_run(self) -> None:
        ready_certs = [c for c in self._certificates if c.detected_name and c.status in (CertificateStatus.READY, CertificateStatus.NEEDS_REVIEW)]

        if not ready_certs:
            self._set_status("Dry run: No certificates ready to rename.")
            return

        used_names: dict[str, int] = {}
        lines = []
        for c in ready_certs:
            name = sanitize_filename(c.detected_name)
            used_names[name] = used_names.get(name, 0) + 1
            suffix = f" ({used_names[name] - 1})" if used_names[name] > 1 else ""
            if len(lines) < 12:
                lines.append(f"{c.original_filename}  ➔  {name}{suffix}.pdf")

        if len(ready_certs) > 12:
            lines.append(f"... and {len(ready_certs) - 12} more certificate(s)")

        preview_msg = "\n".join(lines)
        ConfirmDialog(
            self.frame.winfo_toplevel(), self._palette, self._fonts,
            title="Dry Run Simulation Preview",
            message=f"Simulating rename for {len(ready_certs)} certificate(s) (originals will NOT be modified):",
            detail=preview_msg,
            confirm_text="Close Preview",
            danger=False,
        )
        self._set_status(f"Dry run complete: {len(ready_certs)} file(s) ready to rename.")

    def _mark_all_ready(self) -> None:
        count = 0
        for c in self._certificates:
            if c.detected_name and c.status != CertificateStatus.READY:
                c.status = CertificateStatus.READY
                count += 1
        self._refresh_table()
        self._set_status(f"Marked {count} certificate(s) as Ready.")

    def _mark_selected_ready(self) -> None:
        if not self._selected_row:
            return
        filename = self._selected_row.get("Original File")
        cert = self._cert_map.get(filename)
        if cert:
            cert.status = CertificateStatus.READY
            self._refresh_table()
            self._set_status(f"Marked '{filename}' as Ready.")

    def _save_manual_name(self) -> None:
        if not self._selected_row:
            return
        new_name = self._edit_name_var.get().strip()
        if not new_name:
            return
        filename = self._selected_row.get("Original File")
        cert = self._cert_map.get(filename)
        if cert:
            if not cert.original_detected_name:
                cert.original_detected_name = cert.detected_name
            cert.detected_name = new_name
            cert.manually_corrected = True
            cert.status = CertificateStatus.READY
            cert.extraction_method = ExtractionMethod.MANUAL
            self._refresh_table()
            self._set_status(f"Updated name for '{filename}' to '{new_name}'.")

    def _ignore_selected(self) -> None:
        if not self._selected_row:
            return
        filename = self._selected_row.get("Original File")
        cert = self._cert_map.get(filename)
        if cert:
            cert.status = CertificateStatus.IGNORED
            cert.is_ignored = True
            self._refresh_table()
            self._set_status(f"Ignored '{filename}'.")

    def _remove_selected(self) -> None:
        if not self._selected_row:
            return
        filename = self._selected_row.get("Original File")
        if filename in self._cert_map:
            cert = self._cert_map.pop(filename)
            if cert in self._certificates:
                self._certificates.remove(cert)
            self._refresh_table()
            self._set_status(f"Removed '{filename}' from list.")

    def _on_row_select(self, row_id: str, values: dict) -> None:
        self._selected_row = values
        filename = values.get("Original File", "")
        self._detail_rows["File"].configure(text=filename or "—")
        self._detail_rows["Detected Name"].configure(text=values.get("Detected Name", "—"))
        self._detail_rows["Method"].configure(text=values.get("Method", "—"))
        self._detail_rows["Confidence"].configure(text=values.get("Confidence", "—"))
        name = values.get("Detected Name", "")
        self._detail_rows["New Filename"].configure(text=f"{sanitize_filename(name)}.pdf" if name else "—")
        self._edit_name_var.set(name)

        folder = self._source_folder_var.get()
        if folder:
            pdf_path = Path(folder) / filename
            if pdf_path.exists():
                self._pdf_viewer.load(pdf_path)

    def _on_row_double_click(self, row_id: str, values: dict) -> None:
        self._edit_entry.focus()

    def _edit_selected(self) -> None:
        self._edit_entry.focus()

    def _set_status(self, text: str) -> None:
        self._status_label.configure(text=f"  {text}")

    def _update_summary(self, ready: int, review: int, failed: int) -> None:
        self._summary_label.configure(text=f"✓ {ready} Ready   ⚠ {review} Review   ✗ {failed} Failed")

    # -----------------------------------------------------------------------
    # Worker Signal Listener (Live PDF Preview & ETA Updates)
    # -----------------------------------------------------------------------

    def on_signal(self, signal: Signal) -> None:
        if signal.type == SignalType.PROGRESS_UPDATE:
            curr = signal.payload.get("current", 0)
            tot  = signal.payload.get("total", 1)
            msg  = signal.payload.get("message", "")
            elapsed = signal.payload.get("elapsed_sec", 0)
            eta = signal.payload.get("eta_sec", 0)

            self._progress_bar.set(curr / max(tot, 1))
            self._progress_label.configure(text=msg)
            
            if tot > 0:
                self._eta_label.configure(text=f"⏱ Elapsed: {format_seconds(elapsed)}  |  Est. Remaining: {format_seconds(eta)}")

            self._set_status(msg)

        elif signal.type == SignalType.CERTIFICATE_ANALYZED:
            self._analyzed_count += 1
            payload = signal.payload
            filename = payload.get("filename", "")
            file_path = payload.get("file", "")
            detected_name = payload.get("detected_name", "")
            confidence = payload.get("confidence", 0.0)
            method_str = payload.get("method", "failed")

            # Determine CertificateStatus
            status = CertificateStatus.READY if (confidence >= 50.0 and detected_name) else CertificateStatus.NEEDS_REVIEW
            if method_str == "encrypted":
                status = CertificateStatus.ENCRYPTED_PDF
            elif method_str == "corrupt":
                status = CertificateStatus.CORRUPTED_FILE
            elif method_str == "failed":
                status = CertificateStatus.FAILED

            method_enum = ExtractionMethod.TEXT if method_str in ("text", "font_size", "keyword", "layout") else \
                          ExtractionMethod.OCR if method_str == "ocr" else ExtractionMethod.FAILED

            cert = Certificate(
                id=self._analyzed_count,
                project_id=0,
                original_filename=filename,
                original_file_path=file_path,
                detected_name=detected_name,
                confidence=confidence,
                extraction_method=method_enum,
                status=status,
            )

            if filename not in self._cert_map:
                self._certificates.append(cert)
                self._cert_map[filename] = cert
            else:
                # Update existing record
                old_cert = self._cert_map[filename]
                idx = self._certificates.index(old_cert)
                self._certificates[idx] = cert
                self._cert_map[filename] = cert

            self._refresh_table()

            # LIVE PREVIEW UPDATE: Load currently analyzed PDF into viewer automatically
            if file_path and Path(file_path).exists():
                self._pdf_viewer.load(Path(file_path))

        elif signal.type == SignalType.CERTIFICATE_RENAMED:
            cert_id = signal.payload.get("cert_id")
            for c in self._certificates:
                if c.id == cert_id:
                    c.status = CertificateStatus.RENAMED
            self._refresh_table()

        elif signal.type == SignalType.PROGRESS_COMPLETE:
            self._analysis_running = False
            self._progress_frame.pack_forget()
            self._analyze_btn.configure(state="normal", text="▶  Re-analyze")
            self._header.set_button_state("↺  Dry Run", "normal")
            self._header.set_button_state("✓  Commit Rename", "normal")
            self._header.set_button_state("★  Mark All Ready", "normal")
            self._progress_bar.set(1.0)
            self._set_status(signal.payload.get("message", "Processing complete."))
            self._refresh_table()

        elif signal.type == SignalType.PROGRESS_ERROR:
            self._analysis_running = False
            self._progress_frame.pack_forget()
            self._set_status(f"Error: {signal.payload.get('message', '')}")
            self._analyze_btn.configure(state="normal", text="▶  Start Analysis")
