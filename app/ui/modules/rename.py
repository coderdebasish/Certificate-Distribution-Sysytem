"""
app.ui.modules.rename
======================
Module view for analyzing certificate PDFs, detecting recipient names,
editing names manually, rendering PDF previews, and committing copy-renames.
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePath
import shutil
import tkinter as tk
from tkinter import filedialog as fd
import customtkinter as ctk

from app.models.certificate import Certificate, CertificateStatus, ExtractionMethod
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.ui.components.module_header import ModuleHeader
from app.ui.components.pdf_viewer import PDFViewer
from app.utils.file_utils import sanitize_filename
from app.workers.ocr_worker import OCRWorker
from app.workers.rename_worker import RenameWorker
from app.workers.signals import Signal, SignalType

logger = logging.getLogger(__name__)

_FILTER_TABS = ["All", "Ready", "Needs Review", "Failed", "Ignored"]
_TABLE_COLS  = ["#", "Original File", "Detected Name", "Confidence", "Method", "Status"]
_TABLE_WIDTHS = [35, 140, 160, 75, 75, 90]


class RenameView:
    """Module view for analyzing and batch-renaming certificate PDFs."""

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

        self._build_ui()

    def _build_ui(self) -> None:
        p, f = self._palette, self._fonts

        # Header
        self._header = ModuleHeader(
            self.frame, p, f,
            title="Rename Certificates",
            subtitle="Scan certificate PDFs, extract participant names via OCR/text parsing, and generate renamed copies.",
            actions=[
                ("↺  Dry Run",        self._dry_run,        "secondary"),
                ("✓  Commit Rename",  self._commit_rename,  "primary"),
                ("★  Mark All Ready", self._mark_all_ready, "secondary"),
            ],
        )
        self._header.pack(fill="x", padx=24, pady=(20, 12))
        self._header.set_button_state("↺  Dry Run", "disabled")
        self._header.set_button_state("✓  Commit Rename", "disabled")
        self._header.set_button_state("★  Mark All Ready", "disabled")

        # Import card
        import_card = ctk.CTkFrame(self.frame, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        import_card.pack(fill="x", padx=24, pady=(0, 8))

        import_row = ctk.CTkFrame(import_card, fg_color="transparent")
        import_row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(import_row, text="Source Directory:", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left", padx=(0, 8))

        self._folder_var = ctk.StringVar(value="No folder selected")
        self._folder_entry = ctk.CTkEntry(import_row, textvariable=self._folder_var, font=(f.family, f.size_sm), height=34, fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary)
        self._folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._browse_btn = ctk.CTkButton(
            import_row, text="Browse...", width=100, height=34,
            fg_color=p.bg_secondary, hover_color=p.bg_hover, text_color=p.text_primary,
            command=self._browse_folder,
        )
        self._browse_btn.pack(side="left", padx=(0, 8))

        self._analyze_btn = ctk.CTkButton(
            import_row, text="▶  Analyze Certificates", width=180, height=34, fg_color=p.accent, command=self._start_analysis, state="disabled"
        )
        self._analyze_btn.pack(side="left", padx=8)

        self._file_count_label = ctk.CTkLabel(import_row, text="", font=(f.family, f.size_xs), text_color=p.text_disabled)
        self._file_count_label.pack(side="left")

        # Progress bar frame with Pause and Cancel controls
        self._progress_frame = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=8)
        
        prog_top = ctk.CTkFrame(self._progress_frame, fg_color="transparent")
        prog_top.pack(fill="x", padx=16, pady=(8, 2))
        
        self._progress_label = ctk.CTkLabel(prog_top, text="", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._progress_label.pack(side="left")

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
        self._search_var.trace_add("write", lambda *_: self.load_certificates_from_db())
        self._search_entry = ctk.CTkEntry(
            tab_frame, placeholder_text="🔍 Search file or name...",
            textvariable=self._search_var, width=200, height=30,
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
        detail_header = ctk.CTkFrame(right_frame, fg_color="transparent", height=40)
        detail_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        ctk.CTkLabel(detail_header, text="Certificate Inspector", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left")

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
        self._status_label = ctk.CTkLabel(bottom_bar, text="  Ready.", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._status_label.pack(side="left", padx=16)
        self._summary_label = ctk.CTkLabel(bottom_bar, text="", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary)
        self._summary_label.pack(side="right", padx=16)

        if self._app.active_project:
            imp_dir = Path(self._app.active_project.project_dir) / "Certificates" / "Imported"
            if imp_dir.exists() and list(imp_dir.glob("*.pdf")):
                self._folder_var.set(str(imp_dir))
                count = len(list(imp_dir.glob("*.pdf")))
                self._file_count_label.configure(text=f"  {count} staged PDF(s)", text_color=p.success)
                self._analyze_btn.configure(state="normal")

            self.load_certificates_from_db()

    # -----------------------------------------------------------------------
    # Logic & Event Handlers
    # -----------------------------------------------------------------------

    def load_certificates_from_db(self) -> None:
        self._table.clear()
        if not self._app.active_project or not self._app.certificate_repo:
            return

        certs = self._app.certificate_repo.get_all(self._app.active_project.id)

        # Deduplicate existing database records if any old duplicates exist
        seen_filenames: set[str] = set()
        unique_certs = []
        duplicate_ids_to_remove = []
        for c in certs:
            if c.original_filename in seen_filenames:
                duplicate_ids_to_remove.append(c.id)
            else:
                seen_filenames.add(c.original_filename)
                unique_certs.append(c)

        if duplicate_ids_to_remove and self._app.db:
            with self._app.db.transaction() as cur:
                cur.executemany("DELETE FROM certificates WHERE id = ?", [(did,) for did in duplicate_ids_to_remove])
            certs = unique_certs

        ready, review, failed = 0, 0, 0
        search_query = self._search_var.get().strip().lower()

        for i, c in enumerate(certs, 1):
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
                "Method": c.extraction_method.value.upper(),
                "Status": c.status.value.title().replace("_", " "),
            }, tag=tag)

        if certs:
            self._header.set_button_state("↺  Dry Run", "normal")
            self._header.set_button_state("✓  Commit Rename", "normal")
            self._header.set_button_state("★  Mark All Ready", "normal")
            self._update_summary(ready, review, failed)

    def _browse_folder(self) -> None:
        folder = fd.askdirectory(title="Select Folder Containing Certificate PDFs")
        if not folder:
            return
        self._folder_var.set(folder)
        pdfs = list(Path(folder).glob("*.pdf"))
        count = len(pdfs)
        self._file_count_label.configure(
            text=f"  {count} PDF file{'s' if count != 1 else ''} found" if count > 0 else "  No PDF files found",
            text_color=self._palette.success if count > 0 else self._palette.error,
        )
        if count > 0:
            self._analyze_btn.configure(state="normal")

    def _start_analysis(self) -> None:
        if not self._app.active_project or not self._app.db:
            return

        source_folder = Path(self._folder_var.get())
        if not source_folder.exists():
            return

        # Workspace Import Staging: Copy raw source PDFs into <Project>/Certificates/Imported/
        imported_dir = Path(self._app.active_project.project_dir) / "Certificates" / "Imported"
        imported_dir.mkdir(parents=True, exist_ok=True)

        if source_folder.resolve() != imported_dir.resolve():
            self._set_status("Staging source certificates into project workspace...")
            for pdf_file in source_folder.glob("*.pdf"):
                dest_file = imported_dir / pdf_file.name
                if not dest_file.exists() or dest_file.stat().st_size != pdf_file.stat().st_size:
                    shutil.copy2(str(pdf_file), str(dest_file))
            analysis_folder = imported_dir
        else:
            analysis_folder = source_folder

        self._table.clear()
        self._analysis_running = True
        self._is_paused = False
        self._analyzed_count = 0
        self._pause_btn.configure(text="⏸ Pause")
        self._progress_frame.pack(fill="x", padx=24, pady=(0, 4))
        self._progress_bar.set(0)
        self._analyze_btn.configure(state="disabled", text="Analyzing...")
        self._set_status("Analyzing certificates...")

        self._ocr_worker = OCRWorker(
            signal_queue=self._app._signal_queue,
            pdf_folder=analysis_folder,
            db_conn=self._app.db,
            project_id=self._app.active_project.id,
            ocr_threshold=self._app.settings.ocr_confidence_threshold,
        )
        self._ocr_worker.start()

    def _toggle_pause(self) -> None:
        active_worker = self._ocr_worker or self._rename_worker
        if active_worker and active_worker.is_alive():
            if self._is_paused:
                active_worker.resume()
                self._is_paused = False
                self._pause_btn.configure(text="⏸ Pause")
                self._set_status("Resumed background worker processing.")
            else:
                active_worker.pause()
                self._is_paused = True
                self._pause_btn.configure(text="▶ Resume")
                self._set_status("Paused background worker processing.")

    def _cancel_worker(self) -> None:
        active_worker = self._ocr_worker or self._rename_worker
        if active_worker and active_worker.is_alive():
            active_worker.stop()
            self._set_status("Worker thread cancellation requested...")

    def _commit_rename(self) -> None:
        if not self._app.active_project or not self._app.db:
            return

        from app.ui.components.dialogs import ConfirmDialog
        dialog = ConfirmDialog(
            self.frame.winfo_toplevel(), self._palette, self._fonts,
            title="Confirm Rename",
            message="Rename and copy all Ready certificates to the Renamed folder?",
            confirm_text="Rename Copies", danger=False,
        )
        if dialog.result:
            self._set_status("Renaming certificates...")
            source_dir = Path(self._app.active_project.project_dir) / "Certificates" / "Imported"
            if not source_dir.exists() or not list(source_dir.glob("*.pdf")):
                source_dir = Path(self._folder_var.get())

            # Use the correct project constant folder name for renamed output
            dest_dir = Path(self._app.active_project.project_dir) / "Renamed Certificates"

            self._is_paused = False
            self._pause_btn.configure(text="⏸ Pause")
            self._progress_frame.pack(fill="x", padx=24, pady=(0, 4))
            self._progress_bar.set(0)

            self._rename_worker = RenameWorker(
                signal_queue=self._app._signal_queue,
                db_conn=self._app.db,
                project_id=self._app.active_project.id,
                source_dir=source_dir,
                dest_dir=dest_dir,
                project_dir=Path(self._app.active_project.project_dir),
            )
            self._rename_worker.start()

    def _dry_run(self) -> None:
        if not self._app.active_project or not self._app.certificate_repo:
            self._set_status("No active project loaded.")
            return

        certs = self._app.certificate_repo.get_all(self._app.active_project.id)
        ready_certs = [c for c in certs if c.detected_name and c.status in (CertificateStatus.READY, CertificateStatus.NEEDS_REVIEW)]

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
        from app.ui.components.dialogs import ConfirmDialog
        ConfirmDialog(
            self.frame.winfo_toplevel(), self._palette, self._fonts,
            title="Dry Run Simulation Preview",
            message=f"Simulating rename for {len(ready_certs)} certificate(s) (originals are NOT modified):",
            detail=preview_msg,
            confirm_text="Close Preview",
            danger=False,
        )
        self._set_status(f"Dry run complete: {len(ready_certs)} file(s) ready to rename.")

    def _mark_all_ready(self) -> None:
        if not self._app.active_project or not self._app.certificate_repo:
            return
        certs = self._app.certificate_repo.get_all(self._app.active_project.id)
        count = 0
        for c in certs:
            if c.detected_name and c.status != CertificateStatus.READY:
                c.status = CertificateStatus.READY
                self._app.certificate_repo.update(c)
                count += 1
        self.load_certificates_from_db()
        self._set_status(f"Marked {count} certificate(s) as Ready.")

    def _mark_selected_ready(self) -> None:
        if not self._selected_row or not self._app.certificate_repo or not self._app.active_project:
            return
        filename = self._selected_row.get("Original File")
        cert = self._app.certificate_repo.get_by_filename(self._app.active_project.id, filename)
        if cert:
            cert.status = CertificateStatus.READY
            self._app.certificate_repo.update(cert)
            self.load_certificates_from_db()
            self._set_status(f"Marked '{filename}' as Ready.")

    def _save_manual_name(self) -> None:
        if not self._selected_row or not self._app.certificate_repo or not self._app.active_project:
            return
        new_name = self._edit_name_var.get().strip()
        if not new_name:
            return
        filename = self._selected_row.get("Original File")
        cert = self._app.certificate_repo.get_by_filename(self._app.active_project.id, filename)
        if cert:
            if not cert.original_detected_name:
                cert.original_detected_name = cert.detected_name
            cert.detected_name = new_name
            cert.manually_corrected = True
            cert.status = CertificateStatus.READY
            cert.extraction_method = ExtractionMethod.MANUAL
            self._app.certificate_repo.update(cert)
            self.load_certificates_from_db()
            self._set_status(f"Updated name for '{filename}' to '{new_name}'.")

    def _ignore_selected(self) -> None:
        if not self._selected_row or not self._app.certificate_repo or not self._app.active_project:
            return
        filename = self._selected_row.get("Original File")
        cert = self._app.certificate_repo.get_by_filename(self._app.active_project.id, filename)
        if cert:
            cert.status = CertificateStatus.IGNORED
            cert.is_ignored = True
            self._app.certificate_repo.update(cert)
            self.load_certificates_from_db()
            self._set_status(f"Ignored '{filename}'.")

    def _remove_selected(self) -> None:
        if not self._selected_row or not self._app.certificate_repo or not self._app.active_project:
            return
        filename = self._selected_row.get("Original File")
        cert = self._app.certificate_repo.get_by_filename(self._app.active_project.id, filename)
        if cert and self._app.db:
            with self._app.db.transaction() as cur:
                cur.execute("DELETE FROM certificates WHERE id = ?", (cert.id,))
            self.load_certificates_from_db()
            self._set_status(f"Removed '{filename}' from list.")

    def _set_filter(self, tab: str) -> None:
        self._active_filter = tab
        for name, btn in self._tab_buttons.items():
            active = (name == tab)
            btn.configure(fg_color=self._palette.accent if active else self._palette.bg_secondary, text_color=self._palette.accent_text if active else self._palette.text_secondary)
        self.load_certificates_from_db()

    def _on_row_select(self, row_id: str, values: dict) -> None:
        self._selected_row = values
        self._detail_rows["File"].configure(text=values.get("Original File", "—"))
        self._detail_rows["Detected Name"].configure(text=values.get("Detected Name", "—"))
        self._detail_rows["Method"].configure(text=values.get("Method", "—"))
        self._detail_rows["Confidence"].configure(text=values.get("Confidence", "—"))
        name = values.get("Detected Name", "")
        self._detail_rows["New Filename"].configure(text=f"{sanitize_filename(name)}.pdf" if name else "—")
        self._edit_name_var.set(name)

        folder = self._folder_var.get()
        if folder and folder != "No folder selected":
            pdf_path = Path(folder) / values.get("Original File", "")
            if not pdf_path.exists() and self._app.active_project:
                pdf_path = Path(self._app.active_project.project_dir) / "Certificates" / "Imported" / values.get("Original File", "")
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

    def on_signal(self, signal: Signal) -> None:
        if signal.type == SignalType.PROGRESS_UPDATE:
            curr = signal.payload.get("current", 0)
            tot  = signal.payload.get("total", 1)
            msg  = signal.payload.get("message", "")
            self._progress_bar.set(curr / max(tot, 1))
            self._progress_label.configure(text=msg)
            self._set_status(msg)
        elif signal.type in (SignalType.CERTIFICATE_ANALYZED, SignalType.CERTIFICATE_RENAMED):
            self._analyzed_count += 1
        elif signal.type == SignalType.PROGRESS_COMPLETE:
            self._analysis_running = False
            self._progress_frame.pack_forget()
            self._analyze_btn.configure(state="normal", text="▶  Re-analyze")
            self._header.set_button_state("↺  Dry Run", "normal")
            self._header.set_button_state("✓  Commit Rename", "normal")
            self._header.set_button_state("★  Mark All Ready", "normal")
            self._progress_bar.set(1.0)
            self._set_status(signal.payload.get("message", "Processing complete."))
            self.load_certificates_from_db()
        elif signal.type == SignalType.PROGRESS_ERROR:
            self._analysis_running = False
            self._progress_frame.pack_forget()
            self._set_status(f"Error: {signal.payload.get('message', '')}")
            self._analyze_btn.configure(state="normal", text="▶  Analyze Certificates")
