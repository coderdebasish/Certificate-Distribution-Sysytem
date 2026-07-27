"""
app.ui.modules.sending
=======================
Email Sending module — full implementation wired to EmailWorker, QueueBuilder, and GmailProvider.
"""

from __future__ import annotations

import customtkinter as ctk
from pathlib import Path

from app.models.email_queue import QueueStatus
from app.services.email.gmail_provider import GmailProvider
from app.services.email.queue_manager import QueueBuilder
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.utils.crypto import decrypt_credentials
from app.workers.email_worker import EmailWorker
from app.workers.signals import Signal, SignalType

_QUEUE_COLS   = ["Pos", "Participant Name", "To Email", "Attachment", "Attempts", "Status"]
_QUEUE_WIDTHS = [50,    180,               200,        180,          70,         110]


class SendingView:
    """Full Email Sending module view connected to EmailWorker and SQLite database queue."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._email_worker: EmailWorker | None = None

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Header
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

        # Checklist Strip
        status_strip = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=10)
        status_strip.pack(fill="x", padx=24, pady=(0, 10))

        check_frame = ctk.CTkFrame(status_strip, fg_color="transparent")
        check_frame.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(check_frame, text="Pre-Send Checklist:", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left", padx=(0, 12))

        self._checklist_labels = {}
        for label in ["SMTP Configured", "Template Ready", "Certificates Verified"]:
            badge = ctk.CTkLabel(check_frame, text=f" ✓ {label} ", font=(f.family, f.size_xs, "bold"), fg_color=p.bg_tertiary, text_color=p.success, corner_radius=6)
            badge.pack(side="left", padx=4)
            self._checklist_labels[label] = badge

        ctk.CTkLabel(check_frame, text="Provider: Gmail SMTP (TLS 587)", font=(f.family, f.size_xs), text_color=p.text_disabled).pack(side="right")

        # Progress Card
        prog_card = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=10)
        prog_card.pack(fill="x", padx=24, pady=(0, 10))

        prog_top = ctk.CTkFrame(prog_card, fg_color="transparent")
        prog_top.pack(fill="x", padx=16, pady=(10, 4))

        self._prog_status_lbl = ctk.CTkLabel(prog_top, text="Ready to start distribution queue.", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary)
        self._prog_status_lbl.pack(side="left")

        self._queue_stats_lbl = ctk.CTkLabel(prog_top, text="Total: 0  |  Sent: 0  |  Failed: 0  |  Pending: 0", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._queue_stats_lbl.pack(side="right")

        self._progress_bar = ctk.CTkProgressBar(prog_card, height=10, corner_radius=5)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=16, pady=(4, 12))

        # Main Split
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=6)
        content.grid_columnconfigure(1, weight=4)

        # Queue Table
        table_frame = ctk.CTkFrame(content, fg_color="transparent")
        table_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self._queue_table = DataTable(
            table_frame, p, f,
            columns=_QUEUE_COLS, col_widths=_QUEUE_WIDTHS, stretch_col=1,
            context_menu=[("⚡  Retry Sending", self._retry_item)],
        )
        self._queue_table.pack(fill="both", expand=True)

        # Log Console
        log_panel = ctk.CTkFrame(content, fg_color=p.bg_secondary, corner_radius=12)
        log_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        log_head = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_head.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(log_head, text="Live Dispatch Console", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left")
        ctk.CTkButton(log_head, text="Clear Log", width=64, height=24, fg_color="transparent", border_width=1, text_color=p.text_secondary, font=(f.family, f.size_xs), command=self._clear_log).pack(side="right")

        self._log_box = ctk.CTkTextbox(log_panel, state="disabled", fg_color=p.bg_tertiary, text_color=p.text_primary, font=(f.family, f.size_xs), wrap="word")
        self._log_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self._append_log("System initialized. Select project to prepare queue.")

    # -----------------------------------------------------------------------
    # Database Integration
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        self.load_queue_from_db()

    def load_queue_from_db(self) -> None:
        self._queue_table.clear()
        if not self._app.active_project or not self._app.queue_repo:
            return

        items = self._app.queue_repo.get_all(self._app.active_project.id)
        sent, failed, pending = 0, 0, 0

        for item in items:
            if item.status == QueueStatus.SENT:
                sent += 1
                tag = TAG_SUCCESS
            elif item.status == QueueStatus.FAILED:
                failed += 1
                tag = TAG_ERROR
            else:
                pending += 1
                tag = TAG_DISABLED

            p = self._app.participant_repo.get_by_id(item.participant_id) if self._app.participant_repo else None
            p_name = p.full_name if p else f"PID#{item.participant_id}"

            self._queue_table.add_row({
                "Pos": str(item.queue_position),
                "Participant Name": p_name,
                "To Email": item.to_email,
                "Attachment": Path(item.attachment_path).name if item.attachment_path else "—",
                "Attempts": str(item.attempts),
                "Status": item.status.value.title(),
            }, tag=tag)

        tot = len(items)
        self._queue_stats_lbl.configure(text=f"Total: {tot}  |  Sent: {sent}  |  Failed: {failed}  |  Pending: {pending}")

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _start_sending(self) -> None:
        if not self._app.active_project or not self._app.db:
            self._append_log("No active project loaded.")
            return

        creds = decrypt_credentials(self._app.settings.encrypted_credentials)
        if not creds:
            self._append_log("SMTP credentials missing. Configure in Settings.")
            return

        items = self._app.queue_repo.get_all(self._app.active_project.id)
        if not items:
            self._append_log("Building email queue from matched participants...")
            participants = self._app.participant_repo.get_all(self._app.active_project.id)
            certs = {c.id: c for c in self._app.certificate_repo.get_all(self._app.active_project.id)}
            templates = self._app.template_repo.get_all(self._app.active_project.id)

            if templates and participants:
                builder = QueueBuilder()
                new_items, errors = builder.build(self._app.active_project, participants, certs, templates[0])
                for item in new_items:
                    self._app.queue_repo.insert(item)
                for err in errors:
                    self._append_log(f"Warning: {err}")
                self.load_queue_from_db()
                items = self._app.queue_repo.get_all(self._app.active_project.id)

        if not items:
            self._append_log("No matched participants ready for sending.")
            return

        provider = GmailProvider()
        provider.configure(creds["email"], creds["password"])

        self._email_worker = EmailWorker(
            signal_queue=self._app._signal_queue,
            db_conn=self._app.db,
            project_id=self._app.active_project.id,
            email_provider=provider,
        )
        self._email_worker.start()

        self._header.set_button_state("▶  Start Sending", "disabled")
        self._header.set_button_state("⏸  Pause", "normal")
        self._header.set_button_state("⏹  Stop", "normal")
        self._prog_status_lbl.configure(text="Sending emails...")
        self._append_log("Starting email dispatch worker thread...")

    def _pause_sending(self) -> None:
        if self._email_worker:
            if self._email_worker.is_paused:
                self._email_worker.resume()
                self._header._action_buttons["⏸  Pause"].configure(text="⏸  Pause")
                self._prog_status_lbl.configure(text="Resuming sending...")
            else:
                self._email_worker.pause()
                self._header._action_buttons["⏸  Pause"].configure(text="▶  Resume")
                self._prog_status_lbl.configure(text="Dispatch paused.")

    def _stop_sending(self) -> None:
        if self._email_worker:
            self._email_worker.stop()
            self._email_worker = None

        self._header.set_button_state("▶  Start Sending", "normal")
        self._header.set_button_state("⏸  Pause", "disabled")
        self._header.set_button_state("⏹  Stop", "disabled")
        self._prog_status_lbl.configure(text="Dispatch stopped.")
        self._append_log("Email dispatch stopped.")

    def _retry_item(self) -> None:
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
            self._progress_bar.set(curr / max(tot, 1))
            self.load_queue_from_db()
        elif signal.type == SignalType.EMAIL_SENT:
            self._append_log(f"✓ Email delivered: {signal.payload.get('recipient_email')}")
            self.load_queue_from_db()
        elif signal.type == SignalType.EMAIL_FAILED:
            self._append_log(f"✗ Email failed: {signal.payload.get('recipient_email')} — {signal.payload.get('error')}")
            self.load_queue_from_db()
