"""
app.ui.modules.sending
=======================
Email Sending module view.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.workers.signals import Signal, SignalType


class SendingView:
    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self._build()

    def _build(self) -> None:
        ctk.CTkLabel(self.frame, text="Send Certificates",
                     font=(self._fonts.family, self._fonts.size_xxl, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=24, pady=(24, 4))
        ctk.CTkLabel(self.frame,
                     text="Send personalized certificates to all participants via Gmail.",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_secondary).pack(anchor="w", padx=24, pady=(0, 16))

        # Control row
        ctrl = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=8)
        ctrl.pack(fill="x", padx=24, pady=8)

        self._send_btn = ctk.CTkButton(ctrl, text="▶ Start Sending", width=160, height=40,
                                       fg_color=self._palette.success,
                                       command=self._start_sending,
                                       state="disabled")
        self._send_btn.pack(side="left", padx=8, pady=8)

        self._pause_btn = ctk.CTkButton(ctrl, text="⏸ Pause", width=100, height=40,
                                        fg_color="transparent", border_width=1,
                                        text_color=self._palette.text_primary,
                                        command=self._pause,
                                        state="disabled")
        self._pause_btn.pack(side="left", padx=4, pady=8)

        self._stop_btn = ctk.CTkButton(ctrl, text="⏹ Stop", width=100, height=40,
                                       fg_color=self._palette.error,
                                       command=self._stop,
                                       state="disabled")
        self._stop_btn.pack(side="left", padx=4, pady=8)

        # Progress area
        progress_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        progress_frame.pack(fill="x", padx=24, pady=8)

        self._progress_label = ctk.CTkLabel(progress_frame, text="Ready to send.",
                                             font=(self._fonts.family, self._fonts.size_sm),
                                             text_color=self._palette.text_secondary)
        self._progress_label.pack(anchor="w", padx=16, pady=(12, 4))

        self._progress_bar = ctk.CTkProgressBar(progress_frame)
        self._progress_bar.set(0)
        self._progress_bar.pack(fill="x", padx=16, pady=(4, 12))

        # Live log
        log_frame = ctk.CTkFrame(self.frame, fg_color=self._palette.bg_secondary, corner_radius=12)
        log_frame.pack(fill="both", expand=True, padx=24, pady=8)
        ctk.CTkLabel(log_frame, text="Live Log",
                     font=(self._fonts.family, self._fonts.size_md, "bold"),
                     text_color=self._palette.text_primary).pack(anchor="w", padx=16, pady=(12, 4))
        self._log_box = ctk.CTkTextbox(log_frame, state="disabled",
                                        fg_color=self._palette.bg_tertiary,
                                        text_color=self._palette.text_primary)
        self._log_box.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _start_sending(self) -> None:
        pass  # TODO: build queue, start EmailWorker

    def _pause(self) -> None:
        pass  # TODO: worker.pause()

    def _stop(self) -> None:
        pass  # TODO: worker.stop()

    def _append_log(self, message: str) -> None:
        self._log_box.configure(state="normal")
        self._log_box.insert("end", message + "\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def on_signal(self, signal: Signal) -> None:
        if signal.type == SignalType.LOG_MESSAGE:
            self._append_log(signal.payload.get("message", ""))
        elif signal.type == SignalType.PROGRESS_UPDATE:
            current = signal.payload.get("current", 0)
            total = signal.payload.get("total", 1)
            self._progress_bar.set(current / total)
            self._progress_label.configure(
                text=f"Sending {current} / {total} — {signal.payload.get('message', '')}"
            )
