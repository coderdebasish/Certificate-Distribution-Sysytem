"""
app.ui.modules.sending
=======================
Email Sending module — full UI implementation.

Features:
- Pre-send checklist (Validation overview: Credentials, Template, Attachments)
- Credentials & Provider status strip
- Real-time Email Sending Queue Table
- Live progress stats & progress bar
- Sending controls (Start, Pause, Resume, Stop)
- Interactive live log console
"""

from __future__ import annotations

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.workers.signals import Signal, SignalType

_QUEUE_COLS   = ["Pos", "Participant Name", "To Email", "Attachment", "Attempts", "Status"]
_QUEUE_WIDTHS = [50,    180,               200,        180,          70,         110]


class SendingView:
    """Full Email Sending module view."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._is_sending = False
        self._is_paused = False

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build()

    # -----------------------------------------------------------------------
    # Build
    # -----------------------------------------------------------------------

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # ── Header ──────────────────────────────────────────────────────
        header = ModuleHeader(
            self.frame, p, f,
            title="Send Certificates",
            subtitle="Dispatch personalized certificates directly to participants via Gmail SMTP.",
            actions=[
                ("▶  Start Sending", self._start_sending, "primary"),
                ("⏸  Pause",         self._pause_sending, "secondary"),
                ("⏹  Stop",          self._stop_sending,  "danger"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))
        self._header = header
        header.set_button_state("⏸  Pause", "disabled")
        header.set_button_state("⏹  Stop", "disabled")

        # ── Status Strip & Checklist ────────────────────────────────────
        status_strip = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=10)
        status_strip.pack(fill="x", padx=24, pady=(0, 10))

        # Checklist Items
        check_frame = ctk.CTkFrame(status_strip, fg_color="transparent")
        check_frame.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(check_frame, text="Pre-Send Checklist:",
                     font=(f.family, f.size_sm, "bold"),
                     text_color=p.text_primary).pack(side="left", padx=(0, 12))

        for label, status_ok in [("SMTP Configured", True), ("Template Ready", True), ("Certificates Verified", True)]:
            icon = "✓" if status_ok else "✗"
            color = p.success if status_ok else p.error
            badge = ctk.CTkLabel(
                check_frame, text=f" {icon} {label} ",
                font=(f.family, f.size_xs, "bold"),
                fg_color=p.bg_tertiary, text_color=color, corner_radius=6
            )
            badge.pack(side="left", padx=4)

        # Provider Info (Right side)
        ctk.CTkLabel(
            check_frame, text="Provider: Gmail SMTP (TLS 587)",
            font=(f.family, f.size_xs), text_color=p.text_disabled
        ).pack(side="right")

        # ── Progress & Queue Stats ──────────────────────────────────────
        prog_card = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=10)
        prog_card.pack(fill="x", padx=24, pady=(0, 10))

        prog_top = ctk.CTkFrame(prog_card, fg_color="transparent")
        prog_top.pack(fill="x", padx=16, pady=(10, 4))

        self._prog_status_lbl = ctk.CTkLabel(
            prog_top, text="Ready to start distribution queue.",
            font=(f.family, f.size_sm, "bold"), text_color=p.text_primary
        )
        self._prog_status_lbl.pack(side="left")

        self._queue_stats_lbl = ctk.CTkLabel(
            prog_top, text="Total: 6  |  Sent: 0  |  Failed: 0  |  Pending: 6",
            font=(f.family, f.size_xs), text_color=p.text_secondary
        )
        self._queue_stats_lbl.pack(side="right")

        # Progress Bar
        self._progress_bar = ctk.CTkProgressBar(prog_card, height=10, corner_radius=5)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=16, pady=(4, 12))

        # ── Main Content Split (Queue Table left, Live Log right) ────────
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=6)
        content.grid_columnconfigure(1, weight=4)

        # Left: Queue Table
        table_frame = ctk.CTkFrame(content, fg_color="transparent")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self._queue_table = DataTable(
            table_frame, p, f,
            columns=_QUEUE_COLS,
            col_widths=_QUEUE_WIDTHS,
            stretch_col=1,
            context_menu=[
                ("⚡  Retry Sending", self._retry_item),
                ("---", None),
                ("👁  View Log for Row", self._view_row_log),
            ]
        )
        self._queue_table.pack(fill="both", expand=True)

        # Populate demo queue data
        self._load_demo_queue()

        # Right: Live Log Console
        log_panel = ctk.CTkFrame(content, fg_color=p.bg_secondary, corner_radius=12)
        log_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        log_head = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_head.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(log_head, text="Live Dispatch Console",
                     font=(f.family, f.size_sm, "bold"),
                     text_color=p.text_primary).pack(side="left")

        ctk.CTkButton(log_head, text="Clear Log", width=64, height=24,
                      fg_color="transparent", border_width=1,
                      text_color=p.text_secondary, font=(f.family, f.size_xs),
                      command=self._clear_log).pack(side="right")

        self._log_box = ctk.CTkTextbox(
            log_panel, state="disabled", fg_color=p.bg_tertiary,
            text_color=p.text_primary, font=(f.family, f.size_xs), wrap="word"
        )
        self._log_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self._append_log("System initialized. Pre-send validation passed.")
        self._append_log("SMTP server response: 220 smtp.gmail.com ESMTP ready")

    # -----------------------------------------------------------------------
    # Demo Queue Setup
    # -----------------------------------------------------------------------

    def _load_demo_queue(self) -> None:
        demo = [
            ("1", "Debasish Mohanty", "debasish@example.com", "Debasish Mohanty.pdf", "0", "Pending"),
            ("2", "Priya Sharma",      "priya@example.com",    "Priya Sharma.pdf",      "0", "Pending"),
            ("3", "Ravi Kumar",        "ravi@example.com",     "Ravi Kumar.pdf",        "0", "Pending"),
            ("4", "Ananya Das",        "ananya@example.com",   "Ananya Das.pdf",        "0", "Pending"),
            ("5", "Souvik Chatterjee", "souvik@example.com",   "Souvik Chatterjee.pdf", "0", "Pending"),
            ("6", "Monika Pal",        "monika@example.com",   "Monika Pal.pdf",        "0", "Pending"),
        ]
        for row in demo:
            self._queue_table.add_row(dict(zip(_QUEUE_COLS, row)), tag=TAG_DISABLED)

    # -----------------------------------------------------------------------
    # Actions & Logging
    # -----------------------------------------------------------------------

    def _start_sending(self) -> None:
        self._is_sending = True
        self._is_paused = False
        self._header.set_button_state("▶  Start Sending", "disabled")
        self._header.set_button_state("⏸  Pause", "normal")
        self._header.set_button_state("⏹  Stop", "normal")
        self._prog_status_lbl.configure(text="Sending emails...")
        self._append_log("Starting batch dispatch...")

    def _pause_sending(self) -> None:
        if not self._is_paused:
            self._is_paused = True
            self._header.set_button_state("⏸  Pause", "normal")
            self._header._action_buttons["⏸  Pause"].configure(text="▶  Resume")
            self._prog_status_lbl.configure(text="Dispatch paused.")
            self._append_log("Dispatch paused by user.")
        else:
            self._is_paused = False
            self._header._action_buttons["⏸  Pause"].configure(text="⏸  Pause")
            self._prog_status_lbl.configure(text="Resuming sending...")
            self._append_log("Resuming dispatch...")

    def _stop_sending(self) -> None:
        self._is_sending = False
        self._is_paused = False
        self._header.set_button_state("▶  Start Sending", "normal")
        self._header.set_button_state("⏸  Pause", "disabled")
        self._header.set_button_state("⏹  Stop", "disabled")
        self._header._action_buttons["⏸  Pause"].configure(text="⏸  Pause")
        self._prog_status_lbl.configure(text="Dispatch stopped.")
        self._append_log("Dispatch process stopped.")

    def _retry_item(self) -> None:
        pass

    def _view_row_log(self) -> None:
        pass

    def _append_log(self, text: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"• {text}\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def on_signal(self, signal: Signal) -> None:
        if signal.type == SignalType.LOG_MESSAGE:
            self._append_log(signal.payload.get("message", ""))
        elif signal.type == SignalType.PROGRESS_UPDATE:
            curr = signal.payload.get("current", 0)
            tot = signal.payload.get("total", 1)
            self._progress_bar.set(curr / tot)
            self._queue_stats_lbl.configure(
                text=f"Total: {tot}  |  Sent: {curr}  |  Failed: 0  |  Pending: {tot - curr}"
            )
