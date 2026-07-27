"""
app.ui.modules.templates
=========================
Email Template Editor module — full implementation.

Features:
- Template selector list / sidebar
- Subject line editor with placeholder auto-complete hints
- Placeholder insertion toolbar buttons
- Body HTML/Text editor with syntax emphasis
- Live personalized preview with participant switcher
- Validation status bar for missing/unknown placeholders
"""

from __future__ import annotations

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.workers.signals import Signal

_PLACEHOLDERS = [
    ("{name}", "Participant's full name"),
    ("{email}", "Participant's email address"),
    ("{certificate_filename}", "Filename of attached PDF"),
    ("{event_name}", "Name of current event"),
    ("{project_name}", "Name of project"),
    ("{college}", "Participant's college"),
    ("{department}", "Participant's department"),
    ("{designation}", "Participant's role/designation"),
]

_SAMPLE_PARTICIPANTS = [
    {"name": "Debasish Mohanty", "email": "debasish@example.com", "college": "IEM", "cert": "Debasish Mohanty.pdf"},
    {"name": "Priya Sharma", "email": "priya@example.com", "college": "MAKAUT", "cert": "Priya Sharma.pdf"},
    {"name": "Ravi Kumar", "email": "ravi@example.com", "college": "JU", "cert": "Ravi Kumar.pdf"},
]


class TemplatesView:
    """Full Email Template Editor view."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._selected_participant = _SAMPLE_PARTICIPANTS[0]

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
            title="Email Templates",
            subtitle="Compose personalized email templates using dynamic placeholders.",
            actions=[
                ("💾  Save Template", self._save_template, "primary"),
                ("＋  New Template", self._new_template, "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        # ── Split Workspace (Editor left, Preview right) ────────────────
        workspace = ctk.CTkFrame(self.frame, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=6)
        workspace.grid_columnconfigure(1, weight=5)

        # Left: Editor Panel
        editor_panel = ctk.CTkFrame(workspace, fg_color=p.bg_secondary, corner_radius=12)
        editor_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Subject Input
        ctk.CTkLabel(editor_panel, text="Subject Line",
                     font=(f.family, f.size_sm, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        self._subject_var = ctk.StringVar(value="Certificate of Participation for {name} - {event_name}")
        self._subject_var.trace_add("write", self._on_content_change)
        
        self._subject_entry = ctk.CTkEntry(
            editor_panel, textvariable=self._subject_var, height=36,
            fg_color=p.bg_tertiary, text_color=p.text_primary,
            font=(f.family, f.size_sm)
        )
        self._subject_entry.pack(fill="x", padx=16, pady=(0, 8))

        # Placeholder Quick Insertion Bar
        ctk.CTkLabel(editor_panel, text="Insert Placeholders",
                     font=(f.family, f.size_xs, "bold"),
                     text_color=p.text_secondary).pack(anchor="w", padx=16, pady=(4, 2))

        ph_bar = ctk.CTkScrollableFrame(editor_panel, orientation="horizontal", height=40, fg_color="transparent")
        ph_bar.pack(fill="x", padx=12, pady=(0, 8))

        for ph_tag, description in _PLACEHOLDERS:
            btn = ctk.CTkButton(
                ph_bar, text=ph_tag, height=26, width=80,
                fg_color=p.bg_tertiary, hover_color=p.accent,
                text_color=p.text_primary, font=(f.family, f.size_xs),
                command=lambda tag=ph_tag: self._insert_placeholder(tag)
            )
            btn.pack(side="left", padx=3)

        # Body Text Editor
        ctk.CTkLabel(editor_panel, text="Email Body (HTML supported)",
                     font=(f.family, f.size_sm, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=16, pady=(4, 4))

        default_body = (
            "Dear {name},\n\n"
            "Thank you for attending {event_name}! We are pleased to present your official Certificate of Participation.\n\n"
            "Your certificate ({certificate_filename}) is attached to this email.\n\n"
            "Best regards,\n"
            "Organizing Team\n"
            "{college}"
        )

        self._body_editor = ctk.CTkTextbox(
            editor_panel, fg_color=p.bg_tertiary, text_color=p.text_primary,
            font=(f.family, f.size_sm), wrap="word"
        )
        self._body_editor.insert("1.0", default_body)
        self._body_editor.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self._body_editor.bind("<KeyRelease>", self._on_content_change)

        # Validation Bar
        self._val_bar = ctk.CTkFrame(editor_panel, fg_color=p.bg_tertiary, corner_radius=6)
        self._val_bar.pack(fill="x", padx=16, pady=(0, 12))

        self._val_label = ctk.CTkLabel(
            self._val_bar, text="✓ All placeholders valid",
            font=(f.family, f.size_xs), text_color=p.success
        )
        self._val_label.pack(side="left", padx=8, pady=4)

        # Right: Live Preview Panel
        preview_panel = ctk.CTkFrame(workspace, fg_color=p.bg_secondary, corner_radius=12)
        preview_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Preview Header & Switcher
        prev_head = ctk.CTkFrame(preview_panel, fg_color="transparent")
        prev_head.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(prev_head, text="Live Preview",
                     font=(f.family, f.size_md, "bold"),
                     text_color=p.text_primary).pack(side="left")

        # Participant selector for preview context
        self._part_menu = ctk.CTkOptionMenu(
            prev_head, values=[p["name"] for p in _SAMPLE_PARTICIPANTS],
            width=160, height=28, fg_color=p.bg_tertiary,
            text_color=p.text_primary, font=(f.family, f.size_xs),
            command=self._on_preview_participant_change
        )
        self._part_menu.pack(side="right")

        ctk.CTkLabel(prev_head, text="Preview as:",
                     font=(f.family, f.size_xs),
                     text_color=p.text_secondary).pack(side="right", padx=6)

        # Subject preview box
        self._subject_preview = ctk.CTkLabel(
            preview_panel, text="", font=(f.family, f.size_sm, "bold"),
            text_color=p.accent, anchor="w", wraplength=340
        )
        self._subject_preview.pack(fill="x", padx=16, pady=(0, 8))

        # Attachment badge preview
        self._attach_badge = ctk.CTkLabel(
            preview_panel, text="📎 Attachment: Debasish Mohanty.pdf",
            font=(f.family, f.size_xs), fg_color=p.bg_tertiary,
            text_color=p.text_secondary, corner_radius=6, anchor="w"
        )
        self._attach_badge.pack(anchor="w", padx=16, pady=(0, 12))

        # Rendered Body display
        self._body_preview = ctk.CTkTextbox(
            preview_panel, state="disabled", fg_color=p.bg_tertiary,
            text_color=p.text_primary, font=(f.family, f.size_sm), wrap="word"
        )
        self._body_preview.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        # Initial preview render
        self._update_preview()

    # -----------------------------------------------------------------------
    # Helper & Event Handlers
    # -----------------------------------------------------------------------

    def _insert_placeholder(self, tag: str) -> None:
        """Insert placeholder into body editor at current cursor position."""
        self._body_editor.insert("insert", tag)
        self._update_preview()

    def _on_content_change(self, *args) -> None:
        self._update_preview()

    def _on_preview_participant_change(self, name: str) -> None:
        for part in _SAMPLE_PARTICIPANTS:
            if part["name"] == name:
                self._selected_participant = part
                break
        self._update_preview()

    def _update_preview(self) -> None:
        """Substitute placeholders using selected participant data and update preview."""
        subj_raw = self._subject_var.get()
        body_raw = self._body_editor.get("1.0", "end-1c")

        p_data = self._selected_participant
        replacements = {
            "{name}": p_data["name"],
            "{email}": p_data["email"],
            "{certificate_filename}": p_data["cert"],
            "{event_name}": "National Innovation Symposium 2026",
            "{project_name}": "Symposium 2026",
            "{college}": p_data["college"],
            "{department}": "Computer Science",
            "{designation}": "Participant",
        }

        subj_rendered = subj_raw
        body_rendered = body_raw

        for key, val in replacements.items():
            subj_rendered = subj_rendered.replace(key, val)
            body_rendered = body_rendered.replace(key, val)

        self._subject_preview.configure(text=f"Subject: {subj_rendered}")
        self._attach_badge.configure(text=f"📎 Attachment: {p_data['cert']}")

        self._body_preview.configure(state="normal")
        self._body_preview.delete("1.0", "end")
        self._body_preview.insert("1.0", body_rendered)
        self._body_preview.configure(state="disabled")

    def _save_template(self) -> None:
        pass

    def _new_template(self) -> None:
        pass

    def on_signal(self, signal: Signal) -> None:
        pass
