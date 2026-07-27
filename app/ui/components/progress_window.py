"""
app.ui.components.progress_window
===================================
Modal progress dialog for long-running background operations.

Shows: animated progress bar, current item, elapsed/ETA,
live scrollable log, Pause and Cancel buttons.
"""

from __future__ import annotations

import time
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


class ProgressWindow(ctk.CTkToplevel):
    """
    Modal progress dialog.

    Usage::

        pw = ProgressWindow(root, palette, fonts,
                            title="Analyzing Certificates",
                            total=50,
                            on_pause=worker.pause,
                            on_cancel=worker.stop)
        pw.update_progress(12, "Analyzing cert_12.pdf")
        pw.append_log("  → PaddleOCR: 'Debasish Mohanty' (92%)")
        pw.finish("Analysis complete — 50 certificates processed.")
    """

    def __init__(
        self,
        parent,
        palette: ColorPalette,
        fonts: FontSystem,
        title: str = "Processing...",
        total: int = 100,
        on_pause=None,
        on_cancel=None,
        cancelable: bool = True,
        pausable: bool = True,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent accidental close

        self._palette = palette
        self._fonts = fonts
        self._total = max(total, 1)
        self._current = 0
        self._start_time = time.time()
        self._paused = False
        self._on_pause = on_pause
        self._on_cancel = on_cancel

        self.configure(fg_color=palette.bg_secondary)
        self._build(title, cancelable, pausable)
        self._center()

    # -----------------------------------------------------------------------
    # Build
    # -----------------------------------------------------------------------

    def _build(self, title: str, cancelable: bool, pausable: bool) -> None:
        p, f = self._palette, self._fonts

        # Title
        ctk.CTkLabel(self, text=title,
                     font=(f.family, f.size_lg, "bold"),
                     text_color=p.text_primary).pack(padx=24, pady=(20, 4))

        # Current item
        self._item_label = ctk.CTkLabel(self, text="Starting...",
                                         font=(f.family, f.size_sm),
                                         text_color=p.text_secondary,
                                         wraplength=440)
        self._item_label.pack(padx=24, pady=(0, 8))

        # Progress bar + counts
        prog_frame = ctk.CTkFrame(self, fg_color="transparent")
        prog_frame.pack(fill="x", padx=24, pady=4)

        self._progress_bar = ctk.CTkProgressBar(prog_frame, height=12, corner_radius=6)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", side="top")

        stats_row = ctk.CTkFrame(prog_frame, fg_color="transparent")
        stats_row.pack(fill="x", pady=(4, 0))

        self._count_label = ctk.CTkLabel(stats_row, text="0 / 0",
                                          font=(f.family, f.size_xs),
                                          text_color=p.text_disabled)
        self._count_label.pack(side="left")

        self._pct_label = ctk.CTkLabel(stats_row, text="0%",
                                        font=(f.family, f.size_xs, "bold"),
                                        text_color=p.accent)
        self._pct_label.pack(side="left", padx=8)

        self._eta_label = ctk.CTkLabel(stats_row, text="",
                                        font=(f.family, f.size_xs),
                                        text_color=p.text_disabled)
        self._eta_label.pack(side="right")

        # Live log
        log_frame = ctk.CTkFrame(self, fg_color=p.bg_tertiary, corner_radius=8)
        log_frame.pack(fill="both", expand=True, padx=24, pady=8)

        self._log = ctk.CTkTextbox(log_frame, height=160, state="disabled",
                                    fg_color="transparent",
                                    text_color=p.text_secondary,
                                    font=(f.family, f.size_xs),
                                    wrap="word")
        self._log.pack(fill="both", expand=True, padx=8, pady=8)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=24, pady=(4, 20))

        if pausable:
            self._pause_btn = ctk.CTkButton(btn_frame, text="⏸  Pause", width=120,
                                             fg_color="transparent", border_width=1,
                                             text_color=p.text_primary,
                                             command=self._toggle_pause)
            self._pause_btn.pack(side="left", padx=4)

        if cancelable:
            ctk.CTkButton(btn_frame, text="✕  Cancel", width=120,
                          fg_color=p.error,
                          text_color=p.accent_text,
                          command=self._cancel).pack(side="left", padx=4)

        self.geometry("500x420")

    # -----------------------------------------------------------------------
    # Public API (called from UI thread after receiving signals)
    # -----------------------------------------------------------------------

    def update_progress(self, current: int, message: str = "") -> None:
        """Update the progress bar and current item label."""
        self._current = current
        pct = current / self._total
        self._progress_bar.set(pct)
        self._count_label.configure(text=f"{current} / {self._total}")
        self._pct_label.configure(text=f"{pct * 100:.0f}%")
        if message:
            self._item_label.configure(text=message)
        # ETA
        elapsed = time.time() - self._start_time
        if current > 0:
            rate = elapsed / current
            remaining = (self._total - current) * rate
            self._eta_label.configure(
                text=f"~{self._format_time(remaining)} remaining"
            )

    def append_log(self, message: str, level: str = "INFO") -> None:
        """Append a line to the live log."""
        color_tags = {"ERROR": "red", "WARNING": "orange", "SUCCESS": "green"}
        self._log.configure(state="normal")
        self._log.insert("end", message + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def finish(self, message: str = "Done.") -> None:
        """Mark operation as complete. Replaces Pause/Cancel with Close."""
        self._progress_bar.set(1.0)
        self._item_label.configure(text=message)
        self._count_label.configure(text=f"{self._total} / {self._total}")
        self._pct_label.configure(text="100%")
        self._eta_label.configure(text=f"Elapsed: {self._format_time(time.time() - self._start_time)}")

        # Replace buttons with Close
        for widget in self.winfo_children():
            if isinstance(widget, ctk.CTkFrame) and not widget.winfo_children():
                pass
        # Add close button
        ctk.CTkButton(self, text="✓  Close", width=120,
                      fg_color=self._palette.success,
                      command=self.destroy).pack(pady=(0, 20))
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        if self._paused:
            self._pause_btn.configure(text="▶  Resume")
            if self._on_pause:
                self._on_pause()
        else:
            self._pause_btn.configure(text="⏸  Pause")
            if self._on_pause:
                self._on_pause()

    def _cancel(self) -> None:
        if self._on_cancel:
            self._on_cancel()
        self.destroy()

    def _center(self) -> None:
        self.update_idletasks()
        pw, ph = self.winfo_width(), self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - pw) // 2
        y = (sh - ph) // 2
        self.geometry(f"+{x}+{y}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        if s < 3600:
            return f"{s // 60}m {s % 60}s"
        return f"{s // 3600}h {(s % 3600) // 60}m"
