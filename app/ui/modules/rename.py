"""
app.ui.modules.rename
======================
Rename Certificates module — full implementation wired to OCRWorker, RenameWorker, and CertificateRepository.
"""

from __future__ import annotations

import tkinter.filedialog as fd
import customtkinter as ctk
from pathlib import Path

from app.models.certificate import CertificateStatus, ExtractionMethod
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.ui.components.pdf_viewer import PDFViewer
from app.workers.ocr_worker import OCRWorker
from app.workers.rename_worker import RenameWorker
from app.workers.signals import Signal, SignalType

_FILTER_TABS = ["All", "Ready", "Needs Review", "Failed", "Duplicates", "Ignored"]
_TABLE_COLS   = ["#", "Original File", "Detected Name", "Confidence", "Method", "Status"]
_TABLE_WIDTHS = [40,  180,             180,             90,           90,       100]


class RenameView:
    """Rename Certificates module — full UI implementation with worker background processing."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._active_filter = "All"
        self._selected_row: dict | None = None
        self._analysis_running = False
        self._total_analyzed = 0
        self._analyzed_count = 0
        self._ocr_worker: OCRWorker | None = None
        self._rename_worker: RenameWorker | None = None

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Header
        header = ModuleHeader(
            self.frame, p, f,
            title="Rename Certificates",
            subtitle="Extract participant names from PDFs and rename them automatically.",
            actions=[
                ("✓  Commit Rename", self._commit_rename, "primary"),
                ("↺  Dry Run",       self._dry_run,       "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))
        self._header = header
        header.set_button_state("✓  Commit Rename", "disabled")
        header.set_button_state("↺  Dry Run", "disabled")

        # Folder strip
        import_strip = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=10)
        import_strip.pack(fill="x", padx=24, pady=(0, 8))

        import_row = ctk.CTkFrame(import_strip, fg_color="transparent")
        import_row.pack(fill="x", padx=16, pady=12)

        ctk.CTkLabel(import_row, text="Certificate Folder:", font=(f.family, f.size_sm), text_color=p.text_secondary).pack(side="left")

        self._folder_var = ctk.StringVar(value="No folder selected")
        ctk.CTkEntry(import_row, textvariable=self._folder_var, state="readonly", width=380, height=34, fg_color=p.bg_tertiary, text_color=p.text_secondary, font=(f.family, f.size_sm)).pack(side="left", padx=8)

        ctk.CTkButton(import_row, text="Browse...", width=100, height=34, fg_color="transparent", border_width=1, text_color=p.text_primary, command=self._browse_folder).pack(side="left")

        self._analyze_btn = ctk.CTkButton(
            import_row, text="▶  Analyze Certificates", width=180, height=34, fg_color=p.accent, command=self._start_analysis, state="disabled"
        )
        self._analyze_btn.pack(side="left", padx=8)

        self._file_count_label = ctk.CTkLabel(import_row, text="", font=(f.family, f.size_xs), text_color=p.text_disabled)
        self._file_count_label.pack(side="left")

        # Progress bar
        self._progress_frame = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=8)
        self._progress_label = ctk.CTkLabel(self._progress_frame, text="", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._progress_label.pack(anchor="w", padx=16, pady=(8, 2))
        self._progress_bar = ctk.CTkProgressBar(self._progress_frame, height=6)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=16, pady=(0, 8))

        # Filter Tabs
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
                ("✏  Edit Name",     self._edit_selected),
                ("👁  Ignore",        self._ignore_selected),
                ("---", None),
                ("🗑  Remove Row",    self._remove_selected),
            ],
        )
        self._table.pack(fill="both", expand=True)

        # Right: viewer & details
        right_frame = ctk.CTkFrame(content, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right_frame.grid_rowconfigure(0, weight=3)
        right_frame.grid_rowconfigure(1, weight=2)
        right_frame.grid_columnconfigure(0, weight=1)

        self._pdf_viewer = PDFViewer(right_frame, p, f)
        self._pdf_viewer.grid(row=0, column=0, sticky="nsew", pady=(0, 6))

        details_frame = ctk.CTkFrame(right_frame, fg_color=p.bg_secondary, corner_radius=12)
        details_frame.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(details_frame, text="Detection Details", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(anchor="w", padx=12, pady=(10, 4))

        self._detail_rows: dict[str, ctk.CTkLabel] = {}
        for field in ["File", "Detected Name", "Method", "Confidence", "New Filename"]:
            row = ctk.CTkFrame(details_frame, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=1)
            ctk.CTkLabel(row, text=f"{field}:", font=(f.family, f.size_xs), text_color=p.text_secondary, width=90, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="—", font=(f.family, f.size_xs), text_color=p.text_primary, anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            self._detail_rows[field] = lbl

        edit_row = ctk.CTkFrame(details_frame, fg_color="transparent")
        edit_row.pack(fill="x", padx=12, pady=(6, 10))
        ctk.CTkLabel(edit_row, text="Correct Name:", font=(f.family, f.size_xs), text_color=p.text_secondary, width=90, anchor="w").pack(side="left")
        self._edit_name_var = ctk.StringVar()
        self._edit_entry = ctk.CTkEntry(edit_row, textvariable=self._edit_name_var, height=28, width=120, fg_color=p.bg_tertiary, text_color=p.text_primary, font=(f.family, f.size_xs))
        self._edit_entry.pack(side="left", padx=4)
        ctk.CTkButton(edit_row, text="Apply", width=60, height=28, fg_color=p.accent, command=self._apply_name_edit).pack(side="left", padx=2)

        # Status Bar
        status_bar = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=0)
        status_bar.pack(fill="x", padx=24, pady=(0, 8))

        self._status_label = ctk.CTkLabel(status_bar, text="  Import a certificate folder to begin.", font=(f.family, f.size_xs), text_color=p.text_disabled)
        self._status_label.pack(side="left", padx=8, pady=8)

        self._summary_label = ctk.CTkLabel(status_bar, text="", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary)
        self._summary_label.pack(side="right", padx=12)

    # -----------------------------------------------------------------------
    # Database Integration
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        self.load_certificates_from_db()

    def load_certificates_from_db(self) -> None:
        self._table.clear()
        if not self._app.active_project or not self._app.certificate_repo:
            return

        certs = self._app.certificate_repo.get_all(self._app.active_project.id)
        ready, review, failed = 0, 0, 0

        for i, c in enumerate(certs, 1):
            if c.status == CertificateStatus.READY:
                ready += 1
            elif c.status == CertificateStatus.NEEDS_REVIEW:
                review += 1
            elif c.status == CertificateStatus.FAILED:
                failed += 1

            tag = TAG_SUCCESS if c.status == CertificateStatus.READY else \
                  TAG_WARNING if c.status == CertificateStatus.NEEDS_REVIEW else \
                  TAG_ERROR if c.status == CertificateStatus.FAILED else TAG_DISABLED

            self._table.add_row({
                "#": str(i),
                "Original File": c.original_filename,
                "Detected Name": c.detected_name or "???",
                "Confidence": f"{c.confidence:.0f}%",
                "Method": c.extraction_method.value.upper(),
                "Status": c.status.value.title(),
            }, tag=tag)

        if certs:
            self._header.set_button_state("↺  Dry Run", "normal")
            self._header.set_button_state("✓  Commit Rename", "normal")
            self._update_summary(ready, review, failed)

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

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
            self._total_analyzed = count

    def _start_analysis(self) -> None:
        if not self._app.active_project or not self._app.db:
            return

        folder = Path(self._folder_var.get())
        if not folder.exists():
            return

        self._table.clear()
        self._analysis_running = True
        self._analyzed_count = 0
        self._progress_frame.pack(fill="x", padx=24, pady=(0, 4))
        self._progress_bar.set(0)
        self._analyze_btn.configure(state="disabled", text="Analyzing...")
        self._set_status("Analyzing certificates...")

        self._ocr_worker = OCRWorker(
            signal_queue=self._app._signal_queue,
            pdf_folder=folder,
            db_conn=self._app.db,
            project_id=self._app.active_project.id,
            ocr_threshold=self._app.settings.ocr_confidence_threshold,
        )
        self._ocr_worker.start()

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
            source_dir = Path(self._folder_var.get())
            dest_dir = Path(self._app.active_project.project_dir) / "Certificates" / "Renamed"

            self._rename_worker = RenameWorker(
                signal_queue=self._app._signal_queue,
                db_conn=self._app.db,
                project_id=self._app.active_project.id,
                source_dir=source_dir,
                dest_dir=dest_dir,
            )
            self._rename_worker.start()

    def _dry_run(self) -> None:
        self._set_status("Dry run: rename preview — originals NOT modified.")

    def _set_filter(self, tab: str) -> None:
        self._active_filter = tab
        for name, btn in self._tab_buttons.items():
            active = (name == tab)
            btn.configure(fg_color=self._palette.accent if active else self._palette.bg_secondary, text_color=self._palette.accent_text if active else self._palette.text_secondary)

    def _on_row_select(self, row_id: str, values: dict) -> None:
        self._selected_row = values
        self._detail_rows["File"].configure(text=values.get("Original File", "—"))
        self._detail_rows["Detected Name"].configure(text=values.get("Detected Name", "—"))
        self._detail_rows["Method"].configure(text=values.get("Method", "—"))
        self._detail_rows["Confidence"].configure(text=values.get("Confidence", "—"))
        name = values.get("Detected Name", "")
        self._detail_rows["New Filename"].configure(text=f"{name}.pdf" if name else "—")
        self._edit_name_var.set(name)

        folder = self._folder_var.get()
        if folder and folder != "No folder selected":
            pdf_path = Path(folder) / values.get("Original File", "")
            if pdf_path.exists():
                self._pdf_viewer.load(pdf_path)

    def _on_row_double_click(self, row_id: str, values: dict) -> None:
        self._edit_entry.focus()

    def _edit_selected(self) -> None:
        self._edit_entry.focus()

    def _apply_name_edit(self) -> None:
        new_name = self._edit_name_var.get().strip()
        if self._selected_row and new_name:
            sel = self._table.get_selected()
            if sel:
                row_id = self._table._tree.selection()[0]
                updated = dict(sel[0])
                updated["Detected Name"] = new_name
                updated["New Filename"]  = f"{new_name}.pdf"
                updated["Status"] = "Ready"
                self._table.update_row(row_id, updated, tag=TAG_SUCCESS)
                self._detail_rows["Detected Name"].configure(text=new_name)
                self._set_status(f"Name corrected to '{new_name}'.")

    def _ignore_selected(self) -> None:
        sel = self._table.get_selected()
        if sel:
            row_id = self._table._tree.selection()[0]
            updated = dict(sel[0])
            updated["Status"] = "Ignored"
            self._table.update_row(row_id, updated, tag=TAG_DISABLED)

    def _remove_selected(self) -> None:
        sel = self._table._tree.selection()
        for iid in sel:
            self._table._tree.delete(iid)

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
        elif signal.type == SignalType.PROGRESS_COMPLETE:
            self._analysis_running = False
            self._analyze_btn.configure(state="normal", text="▶  Re-analyze")
            self._header.set_button_state("↺  Dry Run", "normal")
            self._header.set_button_state("✓  Commit Rename", "normal")
            self._progress_bar.set(1.0)
            self._set_status(signal.payload.get("message", "Processing complete."))
            self.load_certificates_from_db()
        elif signal.type == SignalType.PROGRESS_ERROR:
            self._set_status(f"Error: {signal.payload.get('message', '')}")
            self._analyze_btn.configure(state="normal", text="▶  Analyze Certificates")
