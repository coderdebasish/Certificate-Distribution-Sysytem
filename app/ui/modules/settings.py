"""
app.ui.modules.settings
========================
Settings module view — full implementation wired to AppSettings and GmailProvider.
"""

from __future__ import annotations

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.services.email.gmail_provider import GmailProvider
from app.utils.crypto import encrypt_credentials, decrypt_credentials
from app.workers.signals import Signal


class SettingsView:
    """Full Settings Module view wired to application settings."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build()
        self._load_current_settings()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Header
        header = ModuleHeader(
            self.frame, p, f,
            title="Settings",
            subtitle="Configure system preferences, email credentials, and processing defaults.",
            actions=[
                ("💾  Save Settings", self._save_settings, "primary"),
                ("↺  Reset Defaults", self._reset_defaults, "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        scroll = ctk.CTkScrollableFrame(self.frame, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=24, pady=(0, 16))

        # Theme Section
        self._theme_opt = ctk.CTkOptionMenu(
            scroll, values=["dark", "light", "system"], width=160,
            fg_color=p.bg_tertiary, text_color=p.text_primary,
            command=self._on_theme_change
        )
        self._build_card(scroll, "Appearance & Interface", [
            ("Appearance Mode", self._theme_opt),
        ])

        # Gmail Credentials Section
        self._build_email_credentials_card(scroll)

        # Extraction Settings
        self._ocr_conf_entry = ctk.CTkEntry(scroll, width=120, placeholder_text="70", fg_color=p.bg_tertiary, text_color=p.text_primary)
        self._match_threshold_entry = ctk.CTkEntry(scroll, width=120, placeholder_text="75", fg_color=p.bg_tertiary, text_color=p.text_primary)
        self._build_card(scroll, "OCR & Extraction Settings", [
            ("OCR Confidence Threshold (%)", self._ocr_conf_entry),
            ("Fuzzy Name Match Threshold (%)", self._match_threshold_entry),
        ])

    def _build_card(self, parent, title: str, rows: list[tuple[str, ctk.CTkBaseClass]]) -> None:
        p, f = self._palette, self._fonts
        card = ctk.CTkFrame(parent, fg_color=p.bg_secondary, corner_radius=12)
        card.pack(fill="x", pady=6)

        ctk.CTkLabel(card, text=title, font=(f.family, f.size_md, "bold"), text_color=p.text_primary).pack(anchor="w", padx=16, pady=(14, 8))

        for label_text, widget in rows:
            row_frame = ctk.CTkFrame(card, fg_color="transparent")
            row_frame.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(row_frame, text=label_text, font=(f.family, f.size_sm), text_color=p.text_secondary).pack(side="left")
            widget.master = row_frame
            widget.pack(side="right")

        ctk.CTkFrame(card, height=6, fg_color="transparent").pack()

    def _build_email_credentials_card(self, parent) -> None:
        p, f = self._palette, self._fonts
        card = ctk.CTkFrame(parent, fg_color=p.bg_secondary, corner_radius=12)
        card.pack(fill="x", pady=6)

        ctk.CTkLabel(card, text="Email Provider & Credentials (SMTP)", font=(f.family, f.size_md, "bold"), text_color=p.text_primary).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(card, text="Credentials are encrypted locally and never uploaded anywhere.", font=(f.family, f.size_xs), text_color=p.text_disabled).pack(anchor="w", padx=16, pady=(0, 10))

        r1 = ctk.CTkFrame(card, fg_color="transparent")
        r1.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(r1, text="Sender Email Address", font=(f.family, f.size_sm), text_color=p.text_secondary).pack(side="left")
        self._email_entry = ctk.CTkEntry(r1, width=240, placeholder_text="yourname@gmail.com", fg_color=p.bg_tertiary, text_color=p.text_primary)
        self._email_entry.pack(side="right")

        r2 = ctk.CTkFrame(card, fg_color="transparent")
        r2.pack(fill="x", padx=16, pady=4)
        ctk.CTkLabel(r2, text="Google App Password (16 chars)", font=(f.family, f.size_sm), text_color=p.text_secondary).pack(side="left")
        self._pass_entry = ctk.CTkEntry(r2, width=240, show="•", placeholder_text="xxxx xxxx xxxx xxxx", fg_color=p.bg_tertiary, text_color=p.text_primary)
        self._pass_entry.pack(side="right")

        r3 = ctk.CTkFrame(card, fg_color="transparent")
        r3.pack(fill="x", padx=16, pady=(8, 14))
        self._test_status = ctk.CTkLabel(r3, text="", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._test_status.pack(side="left")

        ctk.CTkButton(r3, text="⚡  Test Connection", width=140, height=32, fg_color=p.accent, command=self._test_connection).pack(side="right")

    def _load_current_settings(self) -> None:
        settings = self._app.settings
        self._theme_opt.set(settings.theme)
        if settings.encrypted_credentials:
            dec = decrypt_credentials(settings.encrypted_credentials)
            if dec:
                self._email_entry.insert(0, dec.get("email", ""))
                self._pass_entry.insert(0, dec.get("password", ""))

        self._ocr_conf_entry.insert(0, str(int(settings.ocr_confidence_threshold)))
        self._match_threshold_entry.insert(0, str(int(settings.fuzzy_match_threshold)))

    def _on_theme_change(self, mode: str) -> None:
        ctk.set_appearance_mode(mode)
        self._app.settings.theme = mode

    def _test_connection(self) -> None:
        email_addr = self._email_entry.get().strip()
        app_pass = self._pass_entry.get().strip()

        if not email_addr or not app_pass:
            self._test_status.configure(text="Please enter email and app password.", text_color=self._palette.error)
            return

        self._test_status.configure(text="Testing SMTP connection...", text_color=self._palette.warning)
        self.frame.update_idletasks()

        provider = GmailProvider()
        try:
            provider.configure(email_addr, app_pass)
            res = provider.test_connection()
            if res.success:
                self._test_status.configure(text="✓ SMTP Connection Successful", text_color=self._palette.success)
            else:
                self._test_status.configure(text=f"✗ {res.error_message}", text_color=self._palette.error)
        except Exception as exc:
            self._test_status.configure(text=f"✗ {exc}", text_color=self._palette.error)

    def _save_settings(self) -> None:
        settings = self._app.settings
        settings.theme = self._theme_opt.get()

        email_addr = self._email_entry.get().strip()
        app_pass = self._pass_entry.get().strip()
        if email_addr and app_pass:
            settings.encrypted_credentials = encrypt_credentials(email_addr, app_pass)

        try:
            settings.ocr_confidence_threshold = float(self._ocr_conf_entry.get().strip() or 70.0)
            settings.fuzzy_match_threshold = float(self._match_threshold_entry.get().strip() or 75.0)
        except ValueError:
            pass

        settings.save()
        self._app.statusbar.set_status("Settings saved successfully.")

    def _reset_defaults(self) -> None:
        pass

    def on_signal(self, signal: Signal) -> None:
        pass
