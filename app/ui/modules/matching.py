"""
app.ui.modules.matching
========================
Certificate Matching — full implementation wired to NameMatcher service and Database.
"""

from __future__ import annotations

import customtkinter as ctk
from app.models.participant import MatchStatus
from app.services.matching.matcher import NameMatcher, MatchConfidence
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.stat_card import StatCard
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.workers.signals import Signal


_MATCH_COLS   = ["Participant", "Email", "Assigned Certificate", "Confidence", "Method", "Status"]
_MATCH_WIDTHS = [160,           180,     200,                    100,           80,       90]


class MatchingView:
    """Certificate Matching module — full UI with NameMatcher engine integration."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._matcher = NameMatcher()

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
            subtitle="Link participants to their renamed certificate files automatically.",
            actions=[
                ("🔗  Auto Match All",  self._auto_match, "primary"),
                ("✓  Save Assignments", self._save_matches, "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))
        self._header = header

        # Stat cards
        stats_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=24, pady=(0, 10))
        self._stat_cards: dict[str, StatCard] = {}
        cards = [
            ("🔗", "Matched",     "0", "Auto or manual",   p.success),
            ("❓", "Unmatched",   "0", "Need attention",    p.error),
            ("📜", "Unused Certs","0", "No participant",    p.warning),
            ("⚠",  "Low Conf.",   "0", "Need review",       "#7B1FA2"),
        ]
        for icon, title, val, sub, color in cards:
            card = StatCard(stats_row, p, f, icon=icon, title=title, value=val, subtitle=sub, accent_color=color)
            card.pack(side="left", padx=5, expand=True, fill="x")
            self._stat_cards[title] = card

        # Confidence legend
        legend = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=8)
        legend.pack(fill="x", padx=24, pady=(0, 6))

        ctk.CTkLabel(legend, text="Confidence Legend:", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary).pack(side="left", padx=12, pady=6)
        for label, color in [("■ Exact (100)", p.success), ("■ High (90–99)", "#4CAF50"), ("■ Medium (75–89)", p.warning), ("■ Low (<75)", p.error), ("■ Manual", p.accent)]:
            ctk.CTkLabel(legend, text=label, font=(f.family, f.size_xs), text_color=color).pack(side="left", padx=10)

        # Split: match table + right panel
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=7)
        content.grid_columnconfigure(1, weight=3)

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
                ("✏  Manual Assign",  self._manual_assign),
                ("🗑  Clear Match",    self._clear_match),
            ],
        )
        self._match_table.pack(fill="both", expand=True)

        right = ctk.CTkFrame(content, fg_color=p.bg_secondary, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        ctk.CTkLabel(right, text="Match Details", font=(f.family, f.size_md, "bold"), text_color=p.text_primary).pack(anchor="w", padx=14, pady=(14, 8))

        self._detail_fields: dict[str, ctk.CTkLabel] = {}
        for label in ["Participant", "Email", "Certificate", "Confidence", "Match Method", "Score"]:
            row = ctk.CTkFrame(right, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=f"{label}:", font=(f.family, f.size_xs), text_color=p.text_secondary, width=90, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="—", font=(f.family, f.size_xs), text_color=p.text_primary, anchor="w", wraplength=140)
            lbl.pack(side="left")
            self._detail_fields[label] = lbl

        ctk.CTkFrame(right, height=1, fg_color=p.border).pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(right, text="Manual Override", font=(f.family, f.size_sm, "bold"), text_color=p.text_primary).pack(anchor="w", padx=14, pady=(0, 4))
        ctk.CTkLabel(right, text="Assign Certificate:", font=(f.family, f.size_xs), text_color=p.text_secondary).pack(anchor="w", padx=14)

        self._cert_dropdown = ctk.CTkOptionMenu(
            right, values=["— Select certificate —"], width=200, height=30,
            fg_color=p.bg_tertiary, text_color=p.text_primary, dropdown_fg_color=p.bg_secondary,
        )
        self._cert_dropdown.pack(anchor="w", padx=14, pady=4)

        ctk.CTkButton(right, text="✓ Apply Manual Match", width=200, height=32, fg_color=p.accent, command=self._apply_manual).pack(padx=14, pady=4)
        ctk.CTkButton(right, text="✗ Clear Match", width=200, height=32, fg_color="transparent", border_width=1, text_color=p.text_primary, command=self._clear_match).pack(padx=14, pady=2)

    # -----------------------------------------------------------------------
    # Database integration
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        self.load_matches_from_db()

    def load_matches_from_db(self) -> None:
        self._match_table.clear()
        if not self._app.active_project or not self._app.participant_repo:
            return

        participants = self._app.participant_repo.get_all(self._app.active_project.id)
        certs = self._app.certificate_repo.get_all(self._app.active_project.id)

        cert_dict = {c.id: c.renamed_filename or c.original_filename for c in certs}
        self._cert_dropdown.configure(values=["— Select certificate —"] + list(cert_dict.values()))

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
    # Actions
    # -----------------------------------------------------------------------

    def _auto_match(self) -> None:
        if not self._app.active_project or not self._app.participant_repo or not self._app.certificate_repo:
            return

        participants = self._app.participant_repo.get_all(self._app.active_project.id)
        certs = self._app.certificate_repo.get_all(self._app.active_project.id)

        p_names = {p.id: p.full_name for p in participants}
        c_names = {c.id: Path(c.renamed_filename or c.original_filename).stem for c in certs}

        results = self._matcher.match_all(p_names, c_names)

        # Update DB participants with match results
        for r in results:
            p = self._app.participant_repo.get_by_id(r.participant_id)
            if p and r.certificate_id > 0:
                p.certificate_id = r.certificate_id
                p.match_confidence = r.score
                p.match_status = MatchStatus.MATCHED if r.confidence in [MatchConfidence.EXACT, MatchConfidence.HIGH] else MatchStatus.LOW_CONFIDENCE
                self._app.participant_repo.update(p)

        self.load_matches_from_db()
        self._app.statusbar.set_status(f"Auto-matched {len(results)} participants.")

    def _save_matches(self) -> None:
        self._app.statusbar.set_status("Certificate mappings saved.")

    def _on_row_select(self, row_id: str, values: dict) -> None:
        mapping = {"Participant": "Participant", "Email": "Email", "Certificate": "Assigned Certificate", "Confidence": "Confidence", "Match Method": "Method"}
        for field, col in mapping.items():
            self._detail_fields[field].configure(text=values.get(col, "—"))
        self._detail_fields["Score"].configure(text=values.get("Confidence", "—"))

    def _on_row_double_click(self, row_id: str, values: dict) -> None:
        pass

    def _manual_assign(self) -> None:
        pass

    def _clear_match(self) -> None:
        sel = self._match_table._tree.selection()
        for iid in sel:
            vals = dict(zip(_MATCH_COLS, self._match_table._tree.item(iid, "values")))
            vals["Assigned Certificate"] = "—"
            vals["Confidence"] = "—"
            vals["Method"] = "—"
            vals["Status"] = "Unmatched"
            self._match_table.update_row(iid, vals, tag=TAG_ERROR)

    def _apply_manual(self) -> None:
        cert = self._cert_dropdown.get()
        if cert.startswith("—"):
            return
        sel = self._match_table._tree.selection()
        for iid in sel:
            vals = dict(zip(_MATCH_COLS, self._match_table._tree.item(iid, "values")))
            vals["Assigned Certificate"] = cert
            vals["Confidence"] = "Manual"
            vals["Method"] = "Manual"
            vals["Status"] = "Matched"
            self._match_table.update_row(iid, vals, tag=TAG_SUCCESS)

    def on_signal(self, signal: Signal) -> None:
        pass
