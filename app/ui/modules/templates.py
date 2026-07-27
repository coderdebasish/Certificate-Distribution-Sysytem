"""
app.ui.modules.templates
=========================
Email Template Editor module — full implementation wired to TemplateRepository and DB context.
"""

from __future__ import annotations

import customtkinter as ctk

from app.models.email_template import EmailTemplate as Template
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


class TemplatesView:
    """Full Email Template Editor view connected to TemplateRepository."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._current_template: Template | None = None

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)

        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Header
        header = ModuleHeader(
            self.frame, p, f,
            title="Email Templates",
            subtitle="Compose personalized email templates using dynamic placeholders.",
            actions=[
                ("💾  Save Template", self._save_template, "primary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        workspace = ctk.CTkFrame(self.frame, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=6)
        workspace.grid_columnconfigure(1, weight=5)

        # Editor Panel
        editor_panel = ctk.CTkFrame(workspace, fg_color=p.bg_secondary, corner_radius=12)
        editor_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(editor_panel, text="Subject Line", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        self._subject_var = ctk.StringVar(value="Certificate of Participation for {name} - {event_name}")
        self._subject_var.trace_add("write", self._on_content_change)
        
        self._subject_entry = ctk.CTkEntry(
            editor_panel, textvariable=self._subject_var, height=36,
            fg_color=p.bg_tertiary, text_color=p.text_primary, font=(f.family, f.size_sm)
        )
        self._subject_entry.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(editor_panel, text="Insert Placeholders", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary).pack(anchor="w", padx=16, pady=(4, 2))

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

        ctk.CTkLabel(editor_panel, text="Email Body (HTML supported)", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(anchor="w", padx=16, pady=(4, 4))

        default_body = (
            "Dear {name},\n\n"
            "Thank you for attending {event_name}! We are pleased to present your official Certificate of Participation.\n\n"
            "Your certificate ({certificate_filename}) is attached to this email.\n\n"
            "Best regards,\n"
            "Organizing Team\n"
            "{college}"
        )

        self._body_editor = ctk.CTkTextbox(editor_panel, fg_color=p.bg_tertiary, text_color=p.text_primary, font=(f.family, f.size_sm), wrap="word")
        self._body_editor.insert("1.0", default_body)
        self._body_editor.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self._body_editor.bind("<KeyRelease>", self._on_content_change)

        # Right: Live Preview
        preview_panel = ctk.CTkFrame(workspace, fg_color=p.bg_secondary, corner_radius=12)
        preview_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        prev_head = ctk.CTkFrame(preview_panel, fg_color="transparent")
        prev_head.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(prev_head, text="Live Preview", font=(f.family, f.size_md, "bold"), text_color=p.text_primary).pack(side="left")

        self._subject_preview = ctk.CTkLabel(preview_panel, text="", font=(f.family, f.size_sm, "bold"), text_color=p.accent, anchor="w", wraplength=340)
        self._subject_preview.pack(fill="x", padx=16, pady=(0, 8))

        self._attach_badge = ctk.CTkLabel(preview_panel, text="📎 Attachment: Certificate.pdf", font=(f.family, f.size_xs), fg_color=p.bg_tertiary, text_color=p.text_secondary, corner_radius=6, anchor="w")
        self._attach_badge.pack(anchor="w", padx=16, pady=(0, 12))

        self._body_preview = ctk.CTkTextbox(preview_panel, state="disabled", fg_color=p.bg_tertiary, text_color=p.text_primary, font=(f.family, f.size_sm), wrap="word")
        self._body_preview.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._update_preview()

    # -----------------------------------------------------------------------
    # DB Integration
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        if not self._app.template_repo or not project:
            return

        templates = self._app.template_repo.get_all(project.id)
        if templates:
            self._current_template = templates[0]
            self._subject_var.set(self._current_template.subject)
            self._body_editor.delete("1.0", "end")
            self._body_editor.insert("1.0", self._current_template.body_html)
            self._update_preview()

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _insert_placeholder(self, tag: str) -> None:
        self._body_editor.insert("insert", tag)
        self._update_preview()

    def _on_content_change(self, *args) -> None:
        self._update_preview()

    def _update_preview(self) -> None:
        subj_raw = self._subject_var.get()
        body_raw = self._body_editor.get("1.0", "end-1c")

        proj_name = self._app.active_project.name if self._app.active_project else "Sample Event"
        event_name = self._app.active_project.event_name if self._app.active_project else "Sample Event 2026"

        replacements = {
            "{name}": "Debasish Mohanty",
            "{email}": "debasish@example.com",
            "{certificate_filename}": "Debasish Mohanty.pdf",
            "{event_name}": event_name,
            "{project_name}": proj_name,
            "{college}": "IEM Kolkata",
            "{department}": "Computer Science",
            "{designation}": "Participant",
        }

        subj_rendered = subj_raw
        body_rendered = body_raw

        for key, val in replacements.items():
            subj_rendered = subj_rendered.replace(key, val)
            body_rendered = body_rendered.replace(key, val)

        self._subject_preview.configure(text=f"Subject: {subj_rendered}")
        self._body_preview.configure(state="normal")
        self._body_preview.delete("1.0", "end")
        self._body_preview.insert("1.0", body_rendered)
        self._body_preview.configure(state="disabled")

    def _save_template(self) -> None:
        if not self._app.active_project or not self._app.template_repo:
            self._app.statusbar.set_status("No project open to save template.")
            return

        subj = self._subject_var.get().strip()
        body = self._body_editor.get("1.0", "end-1c").strip()

        if self._current_template:
            self._current_template.subject = subj
            self._current_template.body_html = body
            self._current_template.body_text = body
            self._app.template_repo.update(self._current_template)
        else:
            tmpl = Template(
                project_id=self._app.active_project.id,
                name="Default Email Template",
                subject=subj,
                body_html=body,
                body_text=body,
                is_default=True,
            )
            self._current_template = self._app.template_repo.insert(tmpl)

        self._app.statusbar.set_status("Email template saved successfully.")

    def on_signal(self, signal: Signal) -> None:
        pass
