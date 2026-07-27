"""
app.ui.modules.sending
======================
Email Sending Module — Rate-Limited Gmail Dispatcher with live stream logs,
ETA progress tracking, and CSV audit report generation.
"""

from __future__ import annotations

import csv
import time
from datetime import datetime
from pathlib import Path
import customtkinter as ctk

from app.models.email_queue import QueueStatus, EmailQueueItem
from app.models.email_template import EmailTemplate
from app.models.certificate import Certificate
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
    """Full Email Sending module view with rate-limiting safeguards & live console."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._email_worker: EmailWorker | None = None
        self._start_time: float = 0.0

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
            subtitle="Dispatch personalized certificates safely via Gmail SMTP with rate-limiting safeguards.",
            actions=[
                ("▶  Start Sending", self._start_sending, "primary"),
                ("⏸  Pause",         self._pause_sending, "secondary"),
                ("⏹  Stop",          self._stop_sending,  "danger"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(16, 8))
        self._header = header
        header.set_button_state("⏸  Pause", "disabled")
        header.set_button_state("⏹  Stop", "disabled")

        # Rate Limiting & Safeguard Control Strip
        rate_strip = ctk.CTkFrame(self.frame, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        rate_strip.pack(fill="x", padx=24, pady=(0, 8))

        rf = ctk.CTkFrame(rate_strip, fg_color="transparent")
        rf.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(rf, text="🛡 Rate-Limiting Safeguards:", font=(f.family, f.size_xs, "bold"), text_color=p.text_primary).pack(side="left", padx=(0, 12))

        ctk.CTkLabel(rf, text="Per-Email Delay:", font=(f.family, f.size_xs), text_color=p.text_secondary).pack(side="left", padx=(0, 4))
        self._delay_var = ctk.StringVar(value="5 sec")
        self._delay_combo = ctk.CTkComboBox(
            rf, values=["2 sec", "5 sec", "10 sec", "15 sec", "30 sec"], variable=self._delay_var,
            width=90, height=28, font=(f.family, f.size_xs), fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary
        )
        self._delay_combo.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(rf, text="Batch Pause:", font=(f.family, f.size_xs), text_color=p.text_secondary).pack(side="left", padx=(0, 4))
        self._batch_size_var = ctk.StringVar(value="Every 25 emails")
        self._batch_size_combo = ctk.CTkComboBox(
            rf, values=["Every 15 emails", "Every 25 emails", "Every 50 emails", "Disabled"], variable=self._batch_size_var,
            width=130, height=28, font=(f.family, f.size_xs), fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary
        )
        self._batch_size_combo.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(rf, text="Provider: Gmail SMTP (TLS 587)", font=(f.family, f.size_xs, "bold"), text_color=p.success).pack(side="right")

        # Progress & ETA Card
        prog_card = ctk.CTkFrame(self.frame, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        prog_card.pack(fill="x", padx=24, pady=(0, 8))

        prog_top = ctk.CTkFrame(prog_card, fg_color="transparent")
        prog_top.pack(fill="x", padx=16, pady=(10, 4))

        self._prog_status_lbl = ctk.CTkLabel(prog_top, text="Ready to start distribution queue.", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary)
        self._prog_status_lbl.pack(side="left")

        self._eta_lbl = ctk.CTkLabel(prog_top, text="ETA: —", font=(f.family, f.size_xs, "bold"), text_color=p.accent)
        self._eta_lbl.pack(side="right", padx=(12, 0))

        self._queue_stats_lbl = ctk.CTkLabel(prog_top, text="Total: 0  |  Sent: 0  |  Failed: 0  |  Pending: 0", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._queue_stats_lbl.pack(side="right")

        self._progress_bar = ctk.CTkProgressBar(prog_card, height=10, corner_radius=5)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=16, pady=(4, 12))

        # Split Main Workspace
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
        log_panel = ctk.CTkFrame(content, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        log_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        log_head = ctk.CTkFrame(log_panel, fg_color="transparent")
        log_head.pack(fill="x", padx=14, pady=(10, 6))

        ctk.CTkLabel(log_head, text="Live Dispatch Log Stream", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left")
        ctk.CTkButton(log_head, text="Clear Log", width=64, height=24, fg_color="transparent", border_width=1, border_color=p.border, text_color=p.text_secondary, font=(f.family, f.size_xs), command=self._clear_log).pack(side="right")

        self._log_box = ctk.CTkTextbox(log_panel, state="disabled", fg_color=p.bg_input, text_color=p.text_primary, font=(f.family, f.size_xs), wrap="word")
        self._log_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

        self._append_log("System initialized.")

    # -----------------------------------------------------------------------
    # DB Integration & Queue Auto-Building
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        self.load_queue_from_db()

    def load_queue_from_db(self) -> None:
        self._queue_table.clear()
        if not self._app.active_project or not self._app.queue_repo:
            return

        items = self._app.queue_repo.get_all(self._app.active_project.id)

        # Auto-generate queue if currently empty
        if not items and self._app.participant_repo:
            participants = self._app.participant_repo.get_all(self._app.active_project.id)
            if participants:
                # 1. Ensure email template exists in DB
                templates = self._app.template_repo.get_all(self._app.active_project.id) if self._app.template_repo else []
                if templates:
                    active_tmpl = templates[0]
                else:
                    active_tmpl = EmailTemplate(
                        project_id=self._app.active_project.id,
                        name="Default Email Template",
                        subject="Certificate of Participation for {name} - {event_name}",
                        body_html="Dear {name},<br><br>Please find your official Certificate of Participation attached to this email.<br><br>Best regards,<br>Organizing Team<br>{college}",
                    )
                    if self._app.template_repo:
                        active_tmpl = self._app.template_repo.insert(active_tmpl)

                # 2. Map existing certificates
                certs = {c.id: c for c in self._app.certificate_repo.get_all(self._app.active_project.id)} if self._app.certificate_repo else {}

                builder = QueueBuilder()
                new_items, errors = builder.build(self._app.active_project, participants, certs, active_tmpl)

                # 3. Ensure every item has a valid certificate_id in DB (foreign key safety)
                if self._app.certificate_repo:
                    for item in new_items:
                        if item.certificate_id == 0 and item.attachment_path:
                            p_path = Path(item.attachment_path)
                            c_obj = Certificate(
                                project_id=self._app.active_project.id,
                                original_filename=p_path.name,
                                original_file_path=str(p_path),
                                renamed_filename=p_path.name,
                                renamed_file_path=str(p_path),
                                detected_name=p_path.stem,
                            )
                            inserted_cert = self._app.certificate_repo.insert(c_obj)
                            item.certificate_id = inserted_cert.id

                if new_items:
                    self._app.queue_repo.insert_many(new_items)

                if errors:
                    for err in errors[:5]:
                        self._append_log(f"⚠️ {err}")

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
            p_name = p.full_name if p else item.to_name or f"PID#{item.participant_id}"

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
    # Actions & Worker Dispatch
    # -----------------------------------------------------------------------

    def _start_sending(self) -> None:
        if not self._app.active_project or not self._app.db:
            self._append_log("No active project loaded.")
            return

        # Reload latest settings from file
        self._app.settings.load()

        creds = decrypt_credentials(self._app.settings.encrypted_credentials)
        if not creds or not creds.get("email") or not creds.get("password"):
            self._append_log("❌ SMTP credentials missing. Go to Settings and click 'Save Settings' or 'Test Connection'.")
            return

        items = self._app.queue_repo.get_all(self._app.active_project.id)
        if not items:
            self.load_queue_from_db()
            items = self._app.queue_repo.get_all(self._app.active_project.id)

        if not items:
            self._append_log("No participants available in distribution queue.")
            return

        delay_sec = int(self._delay_var.get().split()[0])
        batch_str = self._batch_size_var.get()
        batch_size = 0
        if "15" in batch_str:
            batch_size = 15
        elif "25" in batch_str:
            batch_size = 25
        elif "50" in batch_str:
            batch_size = 50

        provider = GmailProvider()
        provider.configure(creds["email"], creds["password"])

        self._start_time = time.time()
        self._email_worker = EmailWorker(
            signal_queue=self._app._signal_queue,
            db_conn=self._app.db,
            project_id=self._app.active_project.id,
            email_provider=provider,
            delay_seconds=delay_sec,
            batch_size=batch_size,
        )
        self._email_worker.start()

        self._header.set_button_state("▶  Start Sending", "disabled")
        self._header.set_button_state("⏸  Pause", "normal")
        self._header.set_button_state("⏹  Stop", "normal")
        self._prog_status_lbl.configure(text="Dispatching certificates via Gmail SMTP...")
        self._append_log("🚀 Distribution pipeline started.")

    def _pause_sending(self) -> None:
        if self._email_worker:
            if self._email_worker.is_paused():
                self._email_worker.resume_worker()
                self._header.set_button_text("⏸  Pause", "⏸  Pause")
                self._append_log("▶ Distribution resumed.")
            else:
                self._email_worker.pause_worker()
                self._header.set_button_text("⏸  Pause", "▶  Resume")
                self._append_log("⏸ Distribution paused.")

    def _stop_sending(self) -> None:
        if self._email_worker:
            self._email_worker.stop_worker()
            self._header.set_button_state("▶  Start Sending", "normal")
            self._header.set_button_state("⏸  Pause", "disabled")
            self._header.set_button_state("⏹  Stop", "disabled")
            self._prog_status_lbl.configure(text="Distribution stopped by user.")
            self._append_log("⏹ Distribution stopped.")

    def _retry_item(self) -> None:
        sel = self._queue_table._tree.selection()
        if not sel or not self._app.active_project or not self._app.queue_repo:
            return
        for iid in sel:
            vals = dict(zip(_QUEUE_COLS, self._queue_table._tree.item(iid, "values")))
            pos = int(vals["Pos"])
            items = self._app.queue_repo.get_all(self._app.active_project.id)
            for item in items:
                if item.queue_position == pos:
                    item.status = QueueStatus.PENDING
                    self._app.queue_repo.update(item)
                    break
        self.load_queue_from_db()
        self._append_log("Queued item reset for retry.")

    def _clear_log(self) -> None:
        self._log_box.configure(state="normal")
        self._log_box.delete("1.0", "end")
        self._log_box.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"[{ts}] {text}\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    # -----------------------------------------------------------------------
    # Signal Handling
    # -----------------------------------------------------------------------

    def on_signal(self, signal: Signal) -> None:
        if signal.type == SignalType.WORKER_PROGRESS:
            curr = signal.payload.get("current", 0)
            tot = signal.payload.get("total", 1)
            frac = curr / max(tot, 1)
            self._progress_bar.set(frac)

            elapsed = time.time() - self._start_time
            if curr > 0:
                avg = elapsed / curr
                rem = (tot - curr) * avg
                m, s = divmod(int(rem), 60)
                self._eta_lbl.configure(text=f"ETA: {m}m {s}s")

        elif signal.type == SignalType.WORKER_LOG:
            msg = signal.payload.get("message", "")
            self._append_log(msg)

        elif signal.type in (SignalType.EMAIL_SENT, SignalType.EMAIL_FAILED, SignalType.EMAIL_QUEUE_COMPLETE, SignalType.WORKER_COMPLETED):
            self.load_queue_from_db()
            if signal.type in (SignalType.EMAIL_QUEUE_COMPLETE, SignalType.WORKER_COMPLETED):
                self._header.set_button_state("▶  Start Sending", "normal")
                self._header.set_button_state("⏸  Pause", "disabled")
                self._header.set_button_state("⏹  Stop", "disabled")
                self._prog_status_lbl.configure(text="Distribution completed successfully!")
                self._eta_lbl.configure(text="ETA: Completed")
