"""
app.ui.modules.rename
======================
Rename Certificates module view.

Workflow: Import folder → Analyze (OCR/text) → Dry Run review
          → Manual corrections → Commit rename.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal, SignalType


class RenameView:
    """Rename Certificates module view."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        # Header
        ctk.CTkLabel(self.frame, text="Rename Certificates",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Analyze certificate PDFs and extract participant names automatically.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        # Import area
        import_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        import_frame.pack(fill="x", padx=24, pady=8)

        ctk.CTkLabel(import_frame, text="Step 1 — Import Certificate Folder",
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        row = ctk.CTkFrame(import_frame, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(4, 12))

        self._folder_var = ctk.StringVar(value="No folder selected")
        ctk.CTkEntry(row, textvariable=self._folder_var, state="readonly",
                     width=400, height=36,
                     fg_color=self._palette.bg_tertiary,
                     text_color=self._palette.text_secondary).pack(side="left", padx=(0, 8))

        ctk.CTkButton(row, text="Browse Folder", width=140, height=36,
                      fg_color=self._palette.accent,
                      command=self._browse_folder).pack(side="left", padx=4)

        ctk.CTkButton(row, text="Analyze Certificates", width=180, height=36,
                      fg_color=self._palette.accent,
                      command=self._start_analysis,
                      state="disabled").pack(side="left", padx=4)

        # Results table placeholder
        result_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        result_frame.pack(fill="both", expand=True, padx=24, pady=8)

        ctk.CTkLabel(result_frame, text="Analysis Results",
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        ctk.CTkLabel(result_frame,
                     text="Import a folder of certificate PDFs to begin analysis.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary,
                     justify="center").pack(expand=True)

        # Progress bar (hidden until analysis starts)
        self._progress = ctk.CTkProgressBar(self.frame, width=400)
        self._progress.set(0)

    def _browse_folder(self) -> None:
        import tkinter.filedialog as fd
        folder = fd.askdirectory(title="Select Certificate Folder")
        if folder:
            self._folder_var.set(folder)

    def _start_analysis(self) -> None:
        """Start OCR worker — implemented when wiring up the worker."""
        pass  # TODO: start OCRWorker, wire signal queue

    def on_signal(self, signal: Signal) -> None:
        """Receive signals from OCRWorker / RenameWorker."""
        if signal.type == SignalType.PROGRESS_UPDATE:
            pass  # TODO: update progress bar
        elif signal.type == SignalType.CERTIFICATE_ANALYZED:
            pass  # TODO: add row to results table
        elif signal.type == SignalType.PROGRESS_COMPLETE:
            pass  # TODO: enable commit button
