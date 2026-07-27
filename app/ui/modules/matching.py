"""
app.ui.modules.matching
========================
Certificate Matching Module — Matches participants with renamed certificate PDFs.

Supports both automatic fuzzy string matching and manual override assignments
with live side-by-side PDF preview canvas.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog as fd
import customtkinter as ctk

from app.models.participant import MatchStatus, Participant
from app.services.matching.matcher import NameMatcher, MatchConfidence
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.stat_card import StatCard
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.ui.components.pdf_viewer import PDFViewer
from app.workers.signals import Signal

_MATCH_COLS   = ["Participant", "Email", "Assigned Certificate", "Confidence", "Method", "Status"]
_MATCH_WIDTHS = [160,           180,     200,                    90,            80,       90]


class MatchingView:
    """Certificate Matching module — full UI with NameMatcher engine integration & live PDF preview."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._matcher = NameMatcher()
        self._cert_dir: Path | None = None
        self._cert_files: dict[str, Path] = {}  # stem/filename -> Path
        self._selected_row: dict | None = None

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Header
        header = ModuleHeader(
            self.frame, p, f,
            title="Certificate Matching",
            subtitle="Link participants to their renamed certificate files automatically or manually with live PDF preview.",
            actions=[
                ("📂  Select Certificate Folder", self._browse_cert_folder, "secondary"),
                ("🔗  Auto Match All",             self._auto_match,         "primary"),
                ("✓  Save Assignments",            self._save_matches,       "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(16, 8))
        self._header = header

        # Stat cards
        stats_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=24, pady=(0, 8))
        self._stat_cards: dict[str, StatCard] = {}
        cards = [
            ("🔗", "Matched",     "0", "Auto or manual",   p.success),
            ("❓", "Unmatched",   "0", "Need attention",    p.error),
            ("📜", "Available",   "0", "PDF certificates",  p.accent),
            ("⚠",  "Low Conf.",   "0", "Need review",       p.warning),
        ]
        for icon, title, val, sub, color in cards:
            card = StatCard(stats_row, p, f, icon=icon, title=title, value=val, subtitle=sub, accent_color=color)
            card.pack(side="left", padx=4, expand=True, fill="x")
            self._stat_cards[title] = card

        # Folder strip
        folder_strip = ctk.CTkFrame(self.frame, fg_color=p.bg_card, corner_radius=8, border_width=1, border_color=p.border)
        folder_strip.pack(fill="x", padx=24, pady=(0, 8))

        f_row = ctk.CTkFrame(folder_strip, fg_color="transparent")
        f_row.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(f_row, text="Certificate Folder:", font=(f.family, f.size_xs, "bold"), text_color=p.text_primary).pack(side="left", padx=(0, 8))
        self._folder_var = ctk.StringVar(value="No folder selected")
        self._folder_entry = ctk.CTkEntry(f_row, textvariable=self._folder_var, font=(f.family, f.size_xs), height=28, fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary)
        self._folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(f_row, text="Browse...", width=80, height=28, fg_color=p.bg_secondary, text_color=p.text_primary, command=self._browse_cert_folder).pack(side="left")

        # Split content: match table on left, PDF inspector on right
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=6)
        content.grid_columnconfigure(1, weight=4)

        # Left: Match Table
        left = ctk.CTkFrame(content, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        self._match_table = DataTable(
            left, p, f,
            columns=_MATCH_COLS,
            col_widths=_MATCH_WIDTHS,
            stretch_col=2,
            on_select=self._on_row_select,
            on_double_click=self._on_row_double_click,
            context_menu=[
                ("✏  Manual Assign",  self._apply_manual),
                ("🗑  Clear Match",    self._clear_match),
            ],
        )
        self._match_table.pack(fill="both", expand=True)

        # Right: PDF Inspector & Override Panel
        right = ctk.CTkFrame(content, fg_color=p.bg_card, corner_radius=10, border_width=1, border_color=p.border)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Panel Title
        insp_header = ctk.CTkFrame(right, fg_color="transparent", height=32)
        insp_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))
        ctk.CTkLabel(insp_header, text="Certificate Inspector & Preview", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(side="left")

        # PDF Canvas
        preview_frame = ctk.CTkFrame(right, fg_color=p.bg_secondary, corner_radius=6)
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        self._pdf_viewer = PDFViewer(preview_frame, palette=p, fonts=f)
        self._pdf_viewer.pack(fill="both", expand=True)

        # Override Controls Panel
        ctl_panel = ctk.CTkFrame(right, fg_color="transparent")
        ctl_panel.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 12))

        labels = [("Participant", "—"), ("Assigned Cert", "—"), ("Confidence", "—")]
        self._detail_fields: dict[str, ctk.CTkLabel] = {}
        for label, default in labels:
            r = ctk.CTkFrame(ctl_panel, fg_color="transparent", height=20)
            r.pack(fill="x", pady=1)
            ctk.CTkLabel(r, text=f"{label}:", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary, width=100, anchor="w").pack(side="left")
            val_lbl = ctk.CTkLabel(r, text=default, font=(f.family, f.size_xs), text_color=p.text_primary, anchor="w")
            val_lbl.pack(side="left", fill="x", expand=True)
            self._detail_fields[label] = val_lbl

        ctk.CTkLabel(ctl_panel, text="Manual Override Assignment:", font=(f.family, f.size_xs, "bold"), text_color=p.text_primary).pack(anchor="w", pady=(6, 2))

        self._cert_dropdown = ctk.CTkOptionMenu(
            ctl_panel, values=["— Select certificate —"], height=30,
            fg_color=p.bg_input, text_color=p.text_primary, dropdown_fg_color=p.bg_card,
            command=self._on_dropdown_select
        )
        self._cert_dropdown.pack(fill="x", pady=(0, 4))

        btn_row = ctk.CTkFrame(ctl_panel, fg_color="transparent")
        btn_row.pack(fill="x")
        ctk.CTkButton(btn_row, text="✓ Apply Match", height=28, fg_color=p.accent, text_color=p.accent_text, command=self._apply_manual).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ctk.CTkButton(btn_row, text="✗ Clear Match", height=28, fg_color="transparent", border_width=1, border_color=p.border, text_color=p.text_primary, command=self._clear_match).pack(side="right", fill="x", expand=True, padx=(2, 0))

    # -----------------------------------------------------------------------
    # Directory & DB Initialization
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        renamed_dir = Path(project.project_dir) / "Renamed Certificates"
        if renamed_dir.exists():
            self._load_cert_folder(renamed_dir)
        self.load_matches_from_db()

    def _browse_cert_folder(self) -> None:
        folder = fd.askdirectory(title="Select Folder Containing Renamed Certificates")
        if folder:
            self._load_cert_folder(Path(folder))
            self.load_matches_from_db()

    def _load_cert_folder(self, path: Path) -> None:
        self._cert_dir = path
        self._folder_var.set(str(path))
        self._cert_files.clear()

        if path.exists():
            for p in path.glob("*.pdf"):
                self._cert_files[p.name] = p
                self._cert_files[p.stem] = p

        cert_list = sorted(list({p.name for p in self._cert_files.values()}))
        self._cert_dropdown.configure(values=["— Select certificate —"] + cert_list)
        self._stat_cards["Available"].set_value(str(len(cert_list)))

    def load_matches_from_db(self) -> None:
        self._match_table.clear()
        if not self._app.active_project or not self._app.participant_repo:
            return

        participants = self._app.participant_repo.get_all(self._app.active_project.id)
        certs = self._app.certificate_repo.get_all(self._app.active_project.id) if self._app.certificate_repo else []
        cert_dict = {c.id: c.renamed_filename or c.original_filename for c in certs}

        matched, unmatched, low_conf = 0, 0, 0
        for p in participants:
            cert_name = cert_dict.get(p.certificate_id, "—")
            if p.match_status == MatchStatus.MATCHED:
                matched += 1
                status = "Matched"
                tag = TAG_SUCCESS
            elif p.match_status == MatchStatus.LOW_CONFIDENCE:
                low_conf += 1
                status = "Low Conf."
                tag = TAG_WARNING
            else:
                unmatched += 1
                status = "Unmatched"
                tag = TAG_ERROR

            self._match_table.add_row({
                "Participant": p.full_name,
                "Email": p.email or "—",
                "Assigned Certificate": cert_name,
                "Confidence": f"{p.match_confidence:.0f}%" if p.match_confidence > 0 else "—",
                "Method": "Fuzzy" if p.match_confidence > 0 else "—",
                "Status": status,
            }, tag=tag)

        self._stat_cards["Matched"].set_value(str(matched))
        self._stat_cards["Unmatched"].set_value(str(unmatched))
        self._stat_cards["Low Conf."].set_value(str(low_conf))

    # -----------------------------------------------------------------------
    # Actions & Preview Handlers
    # -----------------------------------------------------------------------

    def _auto_match(self) -> None:
        if not self._app.active_project or not self._app.participant_repo:
            return

        participants = self._app.participant_repo.get_all(self._app.active_project.id)
        if not participants:
            return

        # Prepare names map
        p_names = {p.id: p.full_name for p in participants}

        c_names = {}
        if self._cert_files:
            c_names = {idx: stem for idx, (stem, path) in enumerate(self._cert_files.items(), 1) if path.suffix == ".pdf"}
        elif self._app.certificate_repo:
            certs = self._app.certificate_repo.get_all(self._app.active_project.id)
            c_names = {c.id: Path(c.renamed_filename or c.original_filename).stem for c in certs}

        if not c_names:
            self._app.statusbar.set_status("No certificate PDFs available to match.")
            return

        results = self._matcher.match_all(p_names, c_names)

        # Update participants in DB
        for r in results:
            p = self._app.participant_repo.get_by_id(r.participant_id)
            if p and r.certificate_id > 0:
                p.certificate_id = r.certificate_id
                p.match_confidence = r.score
                p.match_status = MatchStatus.MATCHED if r.confidence in [MatchConfidence.EXACT, MatchConfidence.HIGH] else MatchStatus.LOW_CONFIDENCE
                self._app.participant_repo.update(p)

        self.load_matches_from_db()
        self._app.statusbar.set_status(f"Auto-matched {len(results)} participant(s).")

    def _save_matches(self) -> None:
        self._app.statusbar.set_status("Certificate assignments saved.")

    def _on_row_select(self, row_id: str, values: dict) -> None:
        self._selected_row = values
        self._detail_fields["Participant"].configure(text=values.get("Participant", "—"))
        self._detail_fields["Assigned Cert"].configure(text=values.get("Assigned Certificate", "—"))
        self._detail_fields["Confidence"].configure(text=values.get("Confidence", "—"))

        cert_filename = values.get("Assigned Certificate", "")
        if cert_filename and cert_filename != "—":
            if cert_filename in self._cert_files:
                self._pdf_viewer.load(self._cert_files[cert_filename])
            elif self._cert_dir:
                pdf_p = self._cert_dir / cert_filename
                if pdf_p.exists():
                    self._pdf_viewer.load(pdf_p)
        else:
            self._pdf_viewer.clear()

    def _on_dropdown_select(self, choice: str) -> None:
        if choice in self._cert_files:
            self._pdf_viewer.load(self._cert_files[choice])

    def _on_row_double_click(self, row_id: str, values: dict) -> None:
        pass

    def _apply_manual(self) -> None:
        cert_name = self._cert_dropdown.get()
        if cert_name.startswith("—") or not self._selected_row:
            return

        sel = self._match_table._tree.selection()
        for iid in sel:
            vals = dict(zip(_MATCH_COLS, self._match_table._tree.item(iid, "values")))
            vals["Assigned Certificate"] = cert_name
            vals["Confidence"] = "100%"
            vals["Method"] = "Manual"
            vals["Status"] = "Matched"
            self._match_table.update_row(iid, vals, tag=TAG_SUCCESS)

        if cert_name in self._cert_files:
            self._pdf_viewer.load(self._cert_files[cert_name])

    def _clear_match(self) -> None:
        sel = self._match_table._tree.selection()
        for iid in sel:
            vals = dict(zip(_MATCH_COLS, self._match_table._tree.item(iid, "values")))
            vals["Assigned Certificate"] = "—"
            vals["Confidence"] = "—"
            vals["Method"] = "—"
            vals["Status"] = "Unmatched"
            self._match_table.update_row(iid, vals, tag=TAG_ERROR)
        self._pdf_viewer.clear()

    def on_signal(self, signal: Signal) -> None:
        pass
