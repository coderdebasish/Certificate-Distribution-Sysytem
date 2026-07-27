"""
app.ui.modules.dashboard
=========================
Dashboard — the first screen shown on launch and after project open.

Layout (top → bottom):
  1. Welcome / project summary card
  2. Four stat cards (Participants, Certificates, Matched, Sent)
  3. Workflow progress timeline
  4. Row: Quick Actions  |  Project Health Warnings
  5. Recent Projects scrollable list
"""

from __future__ import annotations

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.stat_card import StatCard
from app.ui.components.module_header import ModuleHeader
from app.workers.signals import Signal


_STAGE_LABELS = [
    "Create Project",
    "Import Certificates",
    "Rename & Verify",
    "Import Participants",
    "Match Certificates",
    "Prepare Template",
    "Send Emails",
    "Complete ✓",
]

_STAGE_ICONS = ["📁", "📥", "✏️", "👥", "🔗", "📄", "📧", "🎉"]


class DashboardView:
    """Full dashboard module view."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts

        self.frame = ctk.CTkScrollableFrame(parent, fg_color=palette.bg_primary, corner_radius=0)
        self._stat_cards: dict[str, StatCard] = {}
        self._build()

    # -----------------------------------------------------------------------
    # Build
    # -----------------------------------------------------------------------

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # ── Header ────────────────────────────────────────────────────────
        header = ModuleHeader(
            self.frame, p, f,
            title="Dashboard",
            subtitle="Your certificate distribution command center.",
            actions=[
                ("＋  New Project", self._new_project, "primary"),
                ("📂  Open Project", self._open_project, "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 12))

        # ── Welcome Card ──────────────────────────────────────────────────
        welcome = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=12)
        welcome.pack(fill="x", padx=24, pady=(0, 12))

        wl = ctk.CTkFrame(welcome, fg_color="transparent")
        wl.pack(fill="x", padx=20, pady=16)

        self._project_title = ctk.CTkLabel(
            wl, text="No project open",
            font=(f.family, f.size_xl, "bold"),
            text_color=p.text_primary, anchor="w",
        )
        self._project_title.pack(anchor="w")

        self._project_subtitle = ctk.CTkLabel(
            wl,
            text="Create a new project or open an existing one to get started.",
            font=(f.family, f.size_sm),
            text_color=p.text_secondary, anchor="w",
        )
        self._project_subtitle.pack(anchor="w", pady=(2, 0))

        # Status badge (right side)
        self._status_badge = ctk.CTkLabel(
            welcome, text="  No Project  ",
            font=(f.family, f.size_xs, "bold"),
            fg_color=p.bg_tertiary, corner_radius=8,
            text_color=p.text_disabled,
        )
        self._status_badge.place(relx=1.0, rely=0.5, anchor="e", x=-20)

        # ── Stats Row ─────────────────────────────────────────────────────
        stats_row = ctk.CTkFrame(self.frame, fg_color="transparent")
        stats_row.pack(fill="x", padx=24, pady=(0, 12))

        stats_config = [
            ("👥", "Participants", "—", "Imported",         p.accent),
            ("📜", "Certificates", "—", "PDF files",        "#7B1FA2"),
            ("🔗", "Matched",      "—", "Assigned",         p.success),
            ("📧", "Emails Sent",  "—", "Delivered",        "#E65100"),
        ]
        for icon, title, value, subtitle, color in stats_config:
            card = StatCard(stats_row, p, f,
                            icon=icon, title=title,
                            value=value, subtitle=subtitle,
                            accent_color=color)
            card.pack(side="left", padx=6, expand=True, fill="x")
            self._stat_cards[title] = card

        # ── Progress Timeline ─────────────────────────────────────────────
        timeline_frame = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=12)
        timeline_frame.pack(fill="x", padx=24, pady=(0, 12))

        ctk.CTkLabel(timeline_frame, text="Workflow Progress",
                     font=(f.family, f.size_md, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=16, pady=(12, 8))

        tl_content = ctk.CTkFrame(timeline_frame, fg_color="transparent")
        tl_content.pack(fill="x", padx=16, pady=(0, 16))
        self._stage_labels: list[ctk.CTkLabel] = []

        for i, (icon, label) in enumerate(zip(_STAGE_ICONS, _STAGE_LABELS)):
            col = ctk.CTkFrame(tl_content, fg_color="transparent")
            col.pack(side="left", expand=True)

            # Circle + icon
            circle_color = p.text_disabled
            circle = ctk.CTkLabel(col, text=icon, width=36, height=36,
                                   fg_color=p.bg_tertiary, corner_radius=18,
                                   font=(f.family, f.size_md),
                                   text_color=circle_color)
            circle.pack()

            # Connector line (not after last)
            if i < len(_STAGE_LABELS) - 1:
                ctk.CTkFrame(tl_content, width=16, height=2,
                              fg_color=p.border).pack(side="left", pady=(18, 0))

            lbl = ctk.CTkLabel(col, text=label,
                               font=(f.family, f.size_xs),
                               text_color=p.text_disabled,
                               wraplength=80, justify="center")
            lbl.pack(pady=(4, 0))
            self._stage_labels.append(lbl)

        # ── Middle row: Quick Actions + Health ─────────────────────────────
        mid = ctk.CTkFrame(self.frame, fg_color="transparent")
        mid.pack(fill="x", padx=24, pady=(0, 12))
        mid.grid_columnconfigure(0, weight=1)
        mid.grid_columnconfigure(1, weight=1)

        # Quick Actions
        qa_frame = ctk.CTkFrame(mid, fg_color=p.bg_secondary, corner_radius=12)
        qa_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(qa_frame, text="Quick Actions",
                     font=(f.family, f.size_md, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=16, pady=(12, 8))

        quick_actions = [
            ("✏️  Rename Certificates",  lambda: self._app._navigate("rename")),
            ("👥  Manage Participants",   lambda: self._app._navigate("participants")),
            ("🔗  Match Certificates",    lambda: self._app._navigate("matching")),
            ("📄  Edit Email Template",   lambda: self._app._navigate("templates")),
            ("📧  Send Certificates",     lambda: self._app._navigate("sending")),
            ("📊  Generate Reports",      lambda: self._app._navigate("reports")),
        ]
        for text, cmd in quick_actions:
            btn = ctk.CTkButton(qa_frame, text=text, anchor="w",
                                height=36, width=260,
                                fg_color="transparent",
                                hover_color=p.bg_hover,
                                text_color=p.text_primary,
                                font=(f.family, f.size_sm),
                                command=cmd)
            btn.pack(anchor="w", padx=12, pady=2)
        ctk.CTkFrame(qa_frame, height=12, fg_color="transparent").pack()

        # Project Health
        health_frame = ctk.CTkFrame(mid, fg_color=p.bg_secondary, corner_radius=12)
        health_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        ctk.CTkLabel(health_frame, text="Project Health",
                     font=(f.family, f.size_md, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=16, pady=(12, 8))

        self._health_frame_content = ctk.CTkFrame(health_frame, fg_color="transparent")
        self._health_frame_content.pack(fill="both", expand=True, padx=12)

        self._no_project_health = ctk.CTkLabel(
            self._health_frame_content,
            text="Open a project to see health status.",
            font=(f.family, f.size_sm),
            text_color=p.text_disabled,
            justify="center",
        )
        self._no_project_health.pack(expand=True, pady=24)

        # ── Recent Projects ─────────────────────────────────────────────────
        recent_frame = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=12)
        recent_frame.pack(fill="x", padx=24, pady=(0, 24))

        ctk.CTkLabel(recent_frame, text="Recent Projects",
                     font=(f.family, f.size_md, "bold"),
                     text_color=p.text_primary).pack(anchor="w", padx=16, pady=(12, 8))

        self._recent_list = ctk.CTkFrame(recent_frame, fg_color="transparent")
        self._recent_list.pack(fill="x", padx=12, pady=(0, 12))

        self._no_recent_label = ctk.CTkLabel(
            self._recent_list,
            text="No recent projects found.\nCreate a new project to get started.",
            font=(f.family, f.size_sm),
            text_color=p.text_disabled,
            justify="center",
        )
        self._no_recent_label.pack(pady=24)

    # -----------------------------------------------------------------------
    # Public update methods
    # -----------------------------------------------------------------------

    def set_project(self, name: str, event: str, stage_idx: int, status: str) -> None:
        """Update dashboard with the currently open project info."""
        self._project_title.configure(text=name)
        self._project_subtitle.configure(text=f"Event: {event}")
        status_colors = {
            "draft": (self._palette.text_disabled, self._palette.bg_tertiary),
            "ready": (self._palette.success, "#1B3A2A"),
            "sending": (self._palette.warning, "#3A2800"),
            "completed": (self._palette.success, "#1B3A2A"),
            "error": (self._palette.error, "#3A1010"),
        }
        fg, bg = status_colors.get(status, (self._palette.text_disabled, self._palette.bg_tertiary))
        self._status_badge.configure(text=f"  {status.upper()}  ",
                                      text_color=fg, fg_color=bg)
        self._highlight_stage(stage_idx)

    def set_stats(self, participants: int, certificates: int,
                  matched: int, sent: int) -> None:
        self._stat_cards["Participants"].set_value(str(participants))
        self._stat_cards["Certificates"].set_value(str(certificates))
        self._stat_cards["Matched"].set_value(str(matched))
        self._stat_cards["Emails Sent"].set_value(str(sent))

    def add_health_item(self, message: str, severity: str = "info") -> None:
        """Add a health warning/info item. severity: 'info'|'warning'|'error'"""
        self._no_project_health.pack_forget()
        color_map = {
            "info":    (self._palette.accent,   "ℹ"),
            "warning": (self._palette.warning,  "⚠"),
            "error":   (self._palette.error,    "✗"),
            "ok":      (self._palette.success,  "✓"),
        }
        color, icon = color_map.get(severity, (self._palette.text_secondary, "•"))
        row = ctk.CTkFrame(self._health_frame_content, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=icon, text_color=color,
                     font=(self._fonts.family, self._fonts.size_sm),
                     width=20).pack(side="left")
        ctk.CTkLabel(row, text=f" {message}",
                     font=(self._fonts.family, self._fonts.size_sm),
                     text_color=self._palette.text_primary,
                     anchor="w").pack(side="left", fill="x", expand=True)

    def add_recent_project(self, name: str, event: str,
                            status: str, path: str) -> None:
        """Add a project card to the recent projects list."""
        self._no_recent_label.pack_forget()
        p, f = self._palette, self._fonts

        card = ctk.CTkFrame(self._recent_list, fg_color=p.bg_tertiary, corner_radius=8)
        card.pack(fill="x", pady=3)
        card.bind("<Enter>", lambda e, c=card: c.configure(fg_color=p.bg_hover))
        card.bind("<Leave>", lambda e, c=card: c.configure(fg_color=p.bg_tertiary))
        card.bind("<Button-1>", lambda e, pa=path: self._open_path(pa))

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        ctk.CTkLabel(left, text=name,
                     font=(f.family, f.size_md, "bold"),
                     text_color=p.text_primary, anchor="w").pack(anchor="w")
        ctk.CTkLabel(left, text=f"Event: {event}  •  {path}",
                     font=(f.family, f.size_xs),
                     text_color=p.text_disabled, anchor="w").pack(anchor="w")

        status_colors = {
            "completed": p.success, "sending": p.warning,
            "draft": p.text_disabled, "error": p.error,
        }
        ctk.CTkLabel(card, text=f"  {status.upper()}  ",
                     font=(f.family, f.size_xs, "bold"),
                     fg_color=status_colors.get(status, p.text_disabled),
                     corner_radius=6, text_color="white").pack(side="right", padx=12)

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _highlight_stage(self, active_idx: int) -> None:
        """Color the workflow timeline up to the active stage."""
        for i, lbl in enumerate(self._stage_labels):
            if i < active_idx:
                lbl.configure(text_color=self._palette.success)
            elif i == active_idx:
                lbl.configure(text_color=self._palette.accent)
            else:
                lbl.configure(text_color=self._palette.text_disabled)

    def _new_project(self) -> None:
        from app.ui.dialogs.new_project_dialog import NewProjectDialog
        dialog = NewProjectDialog(self.frame.winfo_toplevel(),
                                  self._palette, self._fonts)

    def _open_project(self) -> None:
        import tkinter.filedialog as fd
        path = fd.askopenfilename(
            title="Open CDMS Project",
            filetypes=[("CDMS Project", "*.cds"), ("All Files", "*.*")],
        )
        if path:
            # TODO: load project from .cds file
            pass

    def _open_path(self, path: str) -> None:
        # TODO: load project by path
        pass

    def on_signal(self, signal: Signal) -> None:
        pass
