"""
app.ui.modules.templates
=========================
Email Template Editor Module — Rich Subject & HTML Body Editor with
individual candidate live email preview and embedded PDF attachment viewer.
"""

from __future__ import annotations

from pathlib import Path
import customtkinter as ctk

from app.models.email_template import EmailTemplate as Template
from app.models.participant import Participant
from app.services.placeholder.engine import PlaceholderEngine
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.pdf_viewer import PDFViewer
from app.workers.signals import Signal

_PLACEHOLDERS = [
    ("{name}", "Participant's full name"),
    ("{email}", "Participant's email address"),
    ("{certificate}", "Filename of attached PDF"),
    ("{event_name}", "Name of current event"),
    ("{project_name}", "Name of project"),
    ("{college}", "Participant's college"),
    ("{department}", "Participant's department"),
    ("{designation}", "Participant's role/designation"),
    ("{date}", "Current formatted date"),
]


class TemplatesView:
    """Full Email Template Editor view with candidate-by-candidate live preview engine."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._current_template: Template | None = None
        self._engine = PlaceholderEngine()
        self._participants: list[Participant] = []
        self._selected_participant: Participant | None = None

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
            subtitle="Compose personalized email templates and inspect live candidate-by-candidate email previews.",
            actions=[
                ("💾  Save Template", self._save_template, "primary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(16, 8))

        workspace = ctk.CTkFrame(self.frame, fg_color="transparent")
        workspace.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        workspace.grid_rowconfigure(0, weight=1)
        workspace.grid_columnconfigure(0, weight=5)
        workspace.grid_columnconfigure(1, weight=5)

        # Left: Editor Panel
        editor_panel = ctk.CTkFrame(workspace, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        editor_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(editor_panel, text="Subject Line", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(anchor="w", padx=16, pady=(12, 4))

        self._subject_var = ctk.StringVar(value="Certificate of Participation for {name} - {event_name}")
        self._subject_var.trace_add("write", lambda *_: self._update_preview())

        self._subject_entry = ctk.CTkEntry(
            editor_panel, textvariable=self._subject_var, height=34,
            fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary, font=(f.family, f.size_sm)
        )
        self._subject_entry.pack(fill="x", padx=16, pady=(0, 8))

        ctk.CTkLabel(editor_panel, text="Insert Placeholders", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary).pack(anchor="w", padx=16, pady=(2, 2))

        ph_bar = ctk.CTkScrollableFrame(editor_panel, orientation="horizontal", height=40, fg_color="transparent")
        ph_bar.pack(fill="x", padx=12, pady=(0, 8))

        for ph_tag, description in _PLACEHOLDERS:
            btn = ctk.CTkButton(
                ph_bar, text=ph_tag, height=26, width=90,
                fg_color=p.bg_secondary, hover_color=p.accent,
                text_color=p.text_primary, font=(f.family, f.size_xs),
                command=lambda tag=ph_tag: self._insert_placeholder(tag)
            )
            btn.pack(side="left", padx=3)

        ctk.CTkLabel(editor_panel, text="Email Body (HTML supported)", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(anchor="w", padx=16, pady=(4, 4))

        default_body = (
            "Dear {name},\n\n"
            "Thank you for participating in {event_name}! We are pleased to present your official Certificate of Participation.\n\n"
            "Your certificate ({certificate}) is attached to this email.\n\n"
            "Best regards,\n"
            "Organizing Team\n"
            "{college}"
        )

        self._body_editor = ctk.CTkTextbox(editor_panel, fg_color=p.bg_input, text_color=p.text_primary, font=(f.family, f.size_sm), wrap="word")
        self._body_editor.insert("1.0", default_body)
        self._body_editor.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self._body_editor.bind("<KeyRelease>", lambda *_: self._update_preview())

        # Right: Live Preview Panel
        preview_panel = ctk.CTkFrame(workspace, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        preview_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        prev_head = ctk.CTkFrame(preview_panel, fg_color="transparent")
        prev_head.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(prev_head, text="Candidate Email Preview", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left")

        # Candidate Dropdown Selector
        self._candidate_var = ctk.StringVar(value="Sample Candidate (Debasish Mohanty)")
        self._candidate_dropdown = ctk.CTkOptionMenu(
            prev_head, variable=self._candidate_var, values=["Sample Candidate (Debasish Mohanty)"],
            width=220, height=28, fg_color=p.bg_input, text_color=p.text_primary, dropdown_fg_color=p.bg_card,
            command=self._on_candidate_selected
        )
        self._candidate_dropdown.pack(side="right")

        self._subject_preview = ctk.CTkLabel(preview_panel, text="", font=(f.family, f.size_sm, "bold"), text_color=p.accent, anchor="w", wraplength=400)
        self._subject_preview.pack(fill="x", padx=16, pady=(4, 4))

        self._attach_badge = ctk.CTkLabel(preview_panel, text="📎 Attachment: Sample_Certificate.pdf", font=(f.family, f.size_xs), fg_color=p.bg_secondary, text_color=p.text_secondary, corner_radius=6, anchor="w")
        self._attach_badge.pack(anchor="w", padx=16, pady=(0, 8))

        # Split lower preview: Text preview on top, PDF Attachment preview on bottom
        prev_split = ctk.CTkFrame(preview_panel, fg_color="transparent")
        prev_split.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        prev_split.grid_rowconfigure(0, weight=1)
        prev_split.grid_rowconfigure(1, weight=1)
        prev_split.grid_columnconfigure(0, weight=1)

        self._body_preview = ctk.CTkTextbox(prev_split, state="disabled", fg_color=p.bg_input, text_color=p.text_primary, font=(f.family, f.size_sm), wrap="word")
        self._body_preview.grid(row=0, column=0, sticky="nsew", pady=(0, 4))

        pdf_frame = ctk.CTkFrame(prev_split, fg_color=p.bg_secondary, corner_radius=6)
        pdf_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self._pdf_viewer = PDFViewer(pdf_frame, palette=p, fonts=f)
        self._pdf_viewer.pack(fill="both", expand=True)

        self._update_preview()

    # -----------------------------------------------------------------------
    # DB & Candidate Integration
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        if self._app.template_repo and project:
            templates = self._app.template_repo.get_all(project.id)
            if templates:
                self._current_template = templates[0]
                self._subject_var.set(self._current_template.subject)
                self._body_editor.delete("1.0", "end")
                self._body_editor.insert("1.0", self._current_template.body_html)

        if self._app.participant_repo and project:
            self._participants = self._app.participant_repo.get_all(project.id)
            names = [f"{p.full_name} ({p.email})" for p in self._participants]
            if names:
                self._candidate_dropdown.configure(values=names)
                self._candidate_var.set(names[0])
                self._selected_participant = self._participants[0]

        self._update_preview()

    def _on_candidate_selected(self, choice: str) -> None:
        for p in self._participants:
            if f"{p.full_name} ({p.email})" == choice:
                self._selected_participant = p
                break
        self._update_preview()

    # -----------------------------------------------------------------------
    # Actions & Live Preview Updates
    # -----------------------------------------------------------------------

    def _insert_placeholder(self, tag: str) -> None:
        self._body_editor.insert("insert", tag)
        self._update_preview()

    def _update_preview(self) -> None:
        subj_raw = self._subject_var.get()
        body_raw = self._body_editor.get("1.0", "end-1c")

        if self._selected_participant:
            p = self._selected_participant
            name = p.full_name
            email = p.email
            college = p.college or "IEM Kolkata"
            dept = p.department or "Computer Science"
            desig = p.designation or "Participant"
            cert_filename = f"{name}.pdf"
        else:
            name = "Debasish Mohanty"
            email = "debasish@example.com"
            college = "IEM Kolkata"
            dept = "Computer Science"
            desig = "Participant"
            cert_filename = "Debasish Mohanty.pdf"

        proj_name = self._app.active_project.name if self._app.active_project else "Sample Event"
        event_name = self._app.active_project.event_name if self._app.active_project else "Annual Tech Fest 2026"

        context = self._engine.build_context(
            name=name, email=email, certificate_filename=cert_filename,
            event_name=event_name, project_name=proj_name,
            college=college, department=dept, designation=desig
        )

        res = self._engine.render(subj_raw, body_raw, context)

        self._subject_preview.configure(text=f"Subject: {res.subject}")
        self._attach_badge.configure(text=f"📎 Attachment: {cert_filename}")

        self._body_preview.configure(state="normal")
        self._body_preview.delete("1.0", "end")
        self._body_preview.insert("1.0", res.body_html)
        self._body_preview.configure(state="disabled")

        # Load attached PDF if exists on disk
        pdf_path = None
        if self._selected_participant and self._app.certificate_repo and self._selected_participant.certificate_id > 0:
            cert_obj = self._app.certificate_repo.get_by_id(self._selected_participant.certificate_id)
            if cert_obj and cert_obj.renamed_file_path and Path(cert_obj.renamed_file_path).exists():
                pdf_path = Path(cert_obj.renamed_file_path)

        if not pdf_path and self._app.active_project:
            proj_dir = Path(self._app.active_project.project_dir)
            possible_paths = [
                proj_dir / "Renamed_Certificates" / cert_filename,
                proj_dir / "Renamed Certificates" / cert_filename,
                proj_dir.parent / "Renamed_Certificates" / cert_filename,
                proj_dir.parent / "Renamed Certificates" / cert_filename,
            ]
            for candidate in possible_paths:
                if candidate.exists():
                    pdf_path = candidate
                    break

        if pdf_path and pdf_path.exists():
            self._pdf_viewer.load(pdf_path)
        else:
            self._pdf_viewer.clear()

    def _save_template(self) -> None:
        if not self._app.active_project or not self._app.template_repo:
            self._app.statusbar.set_status("No active project loaded to save template.")
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
