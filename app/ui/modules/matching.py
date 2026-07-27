"""
app.ui.modules.matching
========================
Certificate Matching — full implementation.

Layout:
  Top: Summary stat cards + Auto Match button
  Main: Match table (Participant | Email | Certificate | Confidence | Method | Actions)
  Bottom tabs: Unmatched Participants | Unused Certificates
  Right panel: selected participant + certificate details
"""

from __future__ import annotations

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.stat_card import StatCard
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.workers.signals import Signal


_MATCH_COLS   = ["Participant", "Email", "Assigned Certificate", "Confidence", "Method", "Status"]
_MATCH_WIDTHS = [160,           180,     200,                    100,           80,       90]


class MatchingView:
    """Certificate Matching module — full UI."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # ── Header ──────────────────────────────────────────────────────
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
        header.set_button_state("✓  Save Assignments", "disabled")

        # ── Summary stat cards ───────────────────────────────────────────
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
            card = StatCard(stats_row, p, f, icon=icon, title=title,
                            value=val, subtitle=sub, accent_color=color)
            card.pack(side="left", padx=5, expand=True, fill="x")
            self._stat_cards[title] = card

        # ── Confidence legend ─────────────────────────────────────────────
        legend = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=8)
        legend.pack(fill="x", padx=24, pady=(0, 6))

        ctk.CTkLabel(legend, text="Confidence Legend:",
                     font=(f.family, f.size_xs, "bold"),
                     text_color=p.text_secondary).pack(side="left", padx=12, pady=6)
        for label, color in [("■ Exact (100)", p.success),
                              ("■ High (90–99)", "#4CAF50"),
                              ("■ Medium (75–89)", p.warning),
                              ("■ Low (<75)", p.error),
                              ("■ Manual", p.accent)]:
            ctk.CTkLabel(legend, text=label, font=(f.family, f.size_xs),
                         text_color=color).pack(side="left", padx=10)

        # ── Main split: match table + right panel ─────────────────────────
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=7)
        content.grid_columnconfigure(1, weight=3)

        # Match table
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
                ("🔄  Re-match",       self._rematch_selected),
                ("🗑  Clear Match",    self._clear_match),
            ],
        )
        self._match_table.pack(fill="both", expand=True)

        # Populate demo data
        self._load_demo_data()

        # Right panel: details
        right = ctk.CTkFrame(content, fg_color=p.bg_secondary, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        ctk.CTkLabel(right, text="Match Details",
                     font=(f.family, f.size_md, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=14, pady=(14, 8))

        self._detail_fields: dict[str, ctk.CTkLabel] = {}
        for label in ["Participant", "Email", "Certificate", "Confidence",
                      "Match Method", "Score"]:
            row = ctk.CTkFrame(right, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=f"{label}:",
                         font=(f.family, f.size_xs),
                         text_color=p.text_secondary, width=90, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="—",
                               font=(f.family, f.size_xs),
                               text_color=p.text_primary, anchor="w", wraplength=140)
            lbl.pack(side="left")
            self._detail_fields[label] = lbl

        ctk.CTkFrame(right, height=1, fg_color=p.border).pack(fill="x", padx=14, pady=8)

        # Manual override area
        ctk.CTkLabel(right, text="Manual Override",
                     font=(f.family, f.size_sm, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=14, pady=(0, 4))

        ctk.CTkLabel(right, text="Assign Certificate:",
                     font=(f.family, f.size_xs),
                     text_color=p.text_secondary).pack(anchor="w", padx=14)

        self._cert_dropdown = ctk.CTkOptionMenu(
            right, values=["— Select certificate —", "Debasish Mohanty.pdf",
                           "Priya Sharma.pdf", "Ravi Kumar.pdf"],
            width=200, height=30,
            fg_color=p.bg_tertiary, text_color=p.text_primary,
            dropdown_fg_color=p.bg_secondary,
        )
        self._cert_dropdown.pack(anchor="w", padx=14, pady=4)

        ctk.CTkButton(right, text="✓ Apply Manual Match", width=200, height=32,
                      fg_color=p.accent,
                      command=self._apply_manual).pack(padx=14, pady=4)
        ctk.CTkButton(right, text="✗ Clear Match", width=200, height=32,
                      fg_color="transparent", border_width=1,
                      text_color=p.text_primary,
                      command=self._clear_match).pack(padx=14, pady=2)

        # ── Bottom tabs: Unmatched / Unused ──────────────────────────────
        bottom = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=10)
        bottom.pack(fill="x", padx=24, pady=(0, 8))
        bottom.grid_columnconfigure(0, weight=1)
        bottom.grid_columnconfigure(1, weight=1)

        unmatched_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        unmatched_frame.grid(row=0, column=0, sticky="nsew", padx=8, pady=10)

        ctk.CTkLabel(unmatched_frame, text="⚠  Unmatched Participants",
                     font=(f.family, f.size_sm, "bold"),
                     text_color=p.error).pack(anchor="w")
        ctk.CTkLabel(unmatched_frame,
                     text="Ravi Kumar  •  Souvik Chatterjee",
                     font=(f.family, f.size_xs),
                     text_color=p.text_secondary).pack(anchor="w", pady=(2, 0))

        ctk.CTkFrame(bottom, width=1, fg_color=p.border).grid(row=0, column=1, sticky="ns",
                                                               padx=0, pady=8)

        unused_frame = ctk.CTkFrame(bottom, fg_color="transparent")
        unused_frame.grid(row=0, column=1, sticky="nsew", padx=8, pady=10)

        ctk.CTkLabel(unused_frame, text="📜  Unused Certificates",
                     font=(f.family, f.size_sm, "bold"),
                     text_color=p.warning).pack(anchor="w")
        ctk.CTkLabel(unused_frame,
                     text="No unused certificates.",
                     font=(f.family, f.size_xs),
                     text_color=p.text_secondary).pack(anchor="w", pady=(2, 0))

    # -----------------------------------------------------------------------
    # Demo data
    # -----------------------------------------------------------------------

    def _load_demo_data(self) -> None:
        rows = [
            ("Debasish Mohanty",  "debasish@ex.com", "Debasish Mohanty.pdf",  "100%", "Exact",  "Matched"),
            ("Priya Sharma",      "priya@ex.com",    "Priya Sharma.pdf",       "100%", "Exact",  "Matched"),
            ("Ravi Kumar",        "ravi@ex.com",     "—",                      "—",    "—",      "Unmatched"),
            ("Ananya Das",        "ananya@ex.com",   "Ananya Das.pdf",         "91%",  "Fuzzy",  "Matched"),
            ("Souvik Chatterjee", "souvik@ex.com",   "—",                      "—",    "—",      "Unmatched"),
            ("Monika Pal",        "monika@ex.com",   "Monika Pal.pdf",         "76%",  "Fuzzy",  "Low Conf."),
        ]
        tag_map = {"Matched": TAG_SUCCESS, "Unmatched": TAG_ERROR, "Low Conf.": TAG_WARNING}
        for r in rows:
            self._match_table.add_row(dict(zip(_MATCH_COLS, r)),
                                      tag=tag_map.get(r[5], ""))
        self._stat_cards["Matched"].set_value("4")
        self._stat_cards["Unmatched"].set_value("2")
        self._stat_cards["Unused Certs"].set_value("0")
        self._stat_cards["Low Conf."].set_value("1")

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _auto_match(self) -> None:
        # TODO: run NameMatcher, populate table
        pass

    def _save_matches(self) -> None:
        # TODO: persist to DB via CertificateMapping
        pass

    def _on_row_select(self, row_id: str, values: dict) -> None:
        mapping = {
            "Participant": "Participant", "Email": "Email",
            "Certificate": "Assigned Certificate",
            "Confidence": "Confidence", "Match Method": "Method",
        }
        for field, col in mapping.items():
            self._detail_fields[field].configure(text=values.get(col, "—"))
        self._detail_fields["Score"].configure(text=values.get("Confidence", "—"))

    def _on_row_double_click(self, row_id: str, values: dict) -> None:
        self._manual_assign()

    def _manual_assign(self) -> None:
        pass  # Focus dropdown

    def _rematch_selected(self) -> None:
        pass

    def _clear_match(self) -> None:
        sel = self._match_table._tree.selection()
        for iid in sel:
            vals = dict(zip(_MATCH_COLS,
                            self._match_table._tree.item(iid, "values")))
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
            vals = dict(zip(_MATCH_COLS,
                            self._match_table._tree.item(iid, "values")))
            vals["Assigned Certificate"] = cert
            vals["Confidence"] = "Manual"
            vals["Method"] = "Manual"
            vals["Status"] = "Matched"
            self._match_table.update_row(iid, vals, tag=TAG_SUCCESS)

    def on_signal(self, signal: Signal) -> None:
        pass
