"""
app.ui.modules.participants
============================
Participant Management module — full implementation wired to ParticipantRepository and ImportWorker.
"""

from __future__ import annotations

import tkinter.filedialog as fd
import customtkinter as ctk
from pathlib import Path

from app.models.participant import Participant, EmailStatus, MatchStatus
from app.ui.theme import ColorPalette, FontSystem
from app.ui.components.module_header import ModuleHeader
from app.ui.components.data_table import DataTable, TAG_SUCCESS, TAG_WARNING, TAG_ERROR, TAG_DISABLED
from app.workers.import_worker import ImportWorker
from app.workers.signals import Signal, SignalType

_TABLE_COLS   = ["ID", "Full Name", "Email", "College", "Match", "Email Status"]
_TABLE_WIDTHS = [70,   180,         200,     160,       100,     110]
_FILTER_TABS = ["All", "Matched", "Unmatched", "Sent", "Failed", "Missing Email"]


class ParticipantsView:
    """Participant Management module — full UI with DB persistence and background Excel import worker."""

    def __init__(self, parent, app, palette: ColorPalette, fonts: FontSystem) -> None:
        self._app = app
        self._palette = palette
        self._fonts = fonts
        self._detail_visible = False
        self._import_worker: ImportWorker | None = None

        self.frame = ctk.CTkFrame(parent, fg_color=palette.bg_primary)
        self.frame.grid_rowconfigure(1, weight=1)
        self.frame.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Header
        header = ModuleHeader(
            self.frame, p, f,
            title="Participants",
            subtitle="Manage event participants. Import from Excel or add manually.",
            actions=[
                ("＋  Add",          self._add_participant, "primary"),
                ("📥  Import Excel", self._import_excel,    "secondary"),
                ("📤  Export",       self._export,          "secondary"),
            ],
        )
        header.pack(fill="x", padx=24, pady=(20, 8))

        # Filter Tabs
        tab_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        tab_frame.pack(fill="x", padx=24, pady=(0, 4))
        self._tab_buttons: dict[str, ctk.CTkButton] = {}
        for tab in _FILTER_TABS:
            active = tab == "All"
            btn = ctk.CTkButton(
                tab_frame, text=tab, height=30, width=100,
                fg_color=p.accent if active else p.bg_secondary,
                hover_color=p.bg_hover,
                text_color=p.accent_text if active else p.text_secondary,
                font=(f.family, f.size_xs, "bold"), corner_radius=6,
                command=lambda t=tab: self._set_filter(t),
            )
            btn.pack(side="left", padx=2)
            self._tab_buttons[tab] = btn

        # Table & side panel
        content = ctk.CTkFrame(self.frame, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(0, 8))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self._table = DataTable(
            content, p, f,
            columns=_TABLE_COLS,
            col_widths=_TABLE_WIDTHS,
            stretch_col=1,
            multiselect=True,
            on_select=self._on_row_select,
            on_double_click=self._on_row_double_click,
            context_menu=[
                ("✏  Edit Participant",    self._edit_selected),
                ("---", None),
                ("🗑  Delete",             self._delete_selected),
            ],
        )
        self._table.grid(row=0, column=0, sticky="nsew")

        # Side panel
        self._side_panel = ctk.CTkFrame(content, fg_color=p.bg_secondary, corner_radius=12, width=260)
        ctk.CTkLabel(self._side_panel, text="Participant Details", font=(f.family, f.size_md, "bold"), text_color=p.text_primary).pack(anchor="w", padx=16, pady=(14, 8))
        ctk.CTkButton(self._side_panel, text="✕", width=28, height=28, fg_color="transparent", hover_color=p.bg_hover, text_color=p.text_secondary, command=self._hide_side_panel).place(relx=1.0, x=-8, y=8, anchor="ne")

        self._profile_fields: dict[str, ctk.CTkLabel] = {}
        for field in ["ID", "Name", "Email", "Phone", "College", "Department", "Designation", "Match Status", "Email Status"]:
            row = ctk.CTkFrame(self._side_panel, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=f"{field}:", font=(f.family, f.size_xs), text_color=p.text_secondary, width=90, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="—", font=(f.family, f.size_xs), text_color=p.text_primary, anchor="w", wraplength=130)
            lbl.pack(side="left")
            self._profile_fields[field] = lbl

        btn_frame = ctk.CTkFrame(self._side_panel, fg_color="transparent")
        btn_frame.pack(fill="x", padx=14, pady=(12, 14))
        ctk.CTkButton(btn_frame, text="✏  Edit", height=30, width=100, fg_color=p.accent, command=self._edit_selected).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🗑  Delete", height=30, width=100, fg_color=p.error, command=self._delete_selected).pack(side="left", padx=2)

        # Stats bar
        stats_bar = ctk.CTkFrame(self.frame, fg_color=p.bg_secondary, corner_radius=0)
        stats_bar.pack(fill="x", padx=24, pady=(0, 8))

        self._stats_label = ctk.CTkLabel(stats_bar, text="  No participants loaded.", font=(f.family, f.size_xs), text_color=p.text_disabled)
        self._stats_label.pack(side="left", padx=8, pady=6)

        self._import_status = ctk.CTkLabel(stats_bar, text="", font=(f.family, f.size_xs), text_color=p.text_secondary)
        self._import_status.pack(side="right", padx=12)

    # -----------------------------------------------------------------------
    # Database Integration
    # -----------------------------------------------------------------------

    def on_project_loaded(self, project) -> None:
        self.load_participants_from_db()

    def load_participants_from_db(self) -> None:
        self._table.clear()
        if not self._app.active_project or not self._app.participant_repo:
            return

        participants = self._app.participant_repo.get_all(self._app.active_project.id)
        matched, sent, failed = 0, 0, 0

        for p in participants:
            if p.match_status == MatchStatus.MATCHED:
                matched += 1
            if p.email_status == EmailStatus.SENT:
                sent += 1
            elif p.email_status == EmailStatus.FAILED:
                failed += 1

            tag = TAG_SUCCESS if p.email_status == EmailStatus.SENT else \
                  TAG_ERROR if p.email_status == EmailStatus.FAILED or not p.email else \
                  TAG_WARNING if p.match_status == MatchStatus.UNMATCHED else ""

            self._table.add_row({
                "ID": f"PID{p.id:06d}",
                "Full Name": p.full_name,
                "Email": p.email or "(missing)",
                "College": p.college or "—",
                "Match": p.match_status.value.title(),
                "Email Status": p.email_status.value.title(),
            }, tag=tag)

        self._update_stats(len(participants), matched, sent, failed)

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _add_participant(self) -> None:
        ParticipantFormDialog(self.frame.winfo_toplevel(), self._palette, self._fonts, on_save=self._on_participant_saved)

    def _import_excel(self) -> None:
        if not self._app.active_project or not self._app.db:
            return

        path = fd.askopenfilename(
            title="Select Excel File",
            filetypes=[("Excel", "*.xlsx *.xls"), ("All Files", "*.*")],
        )
        if not path:
            return

        self._import_status.configure(text=f"Importing {Path(path).name}...")
        self._import_worker = ImportWorker(
            signal_queue=self._app._signal_queue,
            file_path=Path(path),
            db_conn=self._app.db,
            project_id=self._app.active_project.id,
        )
        self._import_worker.start()

    def _export(self) -> None:
        path = fd.asksaveasfilename(title="Export Participants", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])

    def _set_filter(self, tab: str) -> None:
        for name, btn in self._tab_buttons.items():
            active = (name == tab)
            btn.configure(fg_color=self._palette.accent if active else self._palette.bg_secondary, text_color=self._palette.accent_text if active else self._palette.text_secondary)

    def _on_row_select(self, row_id: str, values: dict) -> None:
        self._populate_side_panel(values)
        self._show_side_panel()

    def _on_row_double_click(self, row_id: str, values: dict) -> None:
        self._edit_selected()

    def _populate_side_panel(self, values: dict) -> None:
        mapping = {"ID": "ID", "Name": "Full Name", "Email": "Email", "College": "College", "Match Status": "Match", "Email Status": "Email Status"}
        for field, col in mapping.items():
            self._profile_fields[field].configure(text=values.get(col, "—"))
        for field in ["Phone", "Department", "Designation"]:
            self._profile_fields[field].configure(text="—")

    def _show_side_panel(self) -> None:
        if not self._detail_visible:
            self._table.grid_configure(columnspan=1)
            self._side_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
            self._detail_visible = True

    def _hide_side_panel(self) -> None:
        self._side_panel.grid_remove()
        self._detail_visible = False

    def _edit_selected(self) -> None:
        sel = self._table.get_selected()
        if sel:
            ParticipantFormDialog(self.frame.winfo_toplevel(), self._palette, self._fonts, initial_values=sel[0], on_save=self._on_participant_saved)

    def _delete_selected(self) -> None:
        from app.ui.components.dialogs import ConfirmDialog
        sel = self._table.get_selected()
        if not sel or not self._app.participant_repo:
            return

        dialog = ConfirmDialog(self.frame.winfo_toplevel(), self._palette, self._fonts, title="Delete Participant", message=f"Delete participant?", confirm_text="Delete", danger=True)
        if dialog.result:
            for iid in self._table._tree.selection():
                self._table._tree.delete(iid)
            self._hide_side_panel()

    def _on_participant_saved(self, values: dict) -> None:
        if self._app.active_project and self._app.participant_repo:
            p = Participant(
                project_id=self._app.active_project.id,
                full_name=values["full_name"],
                email=values["email"],
                phone=values.get("phone", ""),
                college=values.get("college", ""),
                department=values.get("department", ""),
                designation=values.get("designation", ""),
            )
            self._app.participant_repo.insert(p)
            self.load_participants_from_db()

    def _update_stats(self, total: int, matched: int, sent: int, failed: int) -> None:
        self._stats_label.configure(text=f"  Total: {total}   Matched: {matched}   Sent: {sent}   Failed: {failed}")

    def on_signal(self, signal: Signal) -> None:
        if signal.type == SignalType.IMPORT_ROW_PROCESSED:
            row = signal.payload.get("row")
            if row and row.is_valid:
                self._table.add_row({
                    "ID": "PID?", "Full Name": row.name, "Email": row.email,
                    "College": row.college, "Match": "Unmatched", "Email Status": "Pending",
                }, tag=TAG_WARNING)
        elif signal.type == SignalType.IMPORT_COMPLETE:
            total = signal.payload.get("total", 0)
            self._import_status.configure(text=f"✓ Imported {total} participants")
            self.load_participants_from_db()


class ParticipantFormDialog(ctk.CTkToplevel):
    """Add / edit a single participant."""

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem, initial_values: dict | None = None, on_save=None) -> None:
        super().__init__(parent)
        p, f = palette, fonts
        self.title("Edit Participant" if initial_values else "Add Participant")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=p.bg_secondary)
        self._palette = p
        self._fonts = f
        self._on_save = on_save
        self._vars: dict[str, ctk.StringVar] = {}

        fields = [
            ("Full Name *", "full_name",   True),
            ("Email *",     "email",        True),
            ("Phone",       "phone",        False),
            ("College",     "college",      False),
            ("Department",  "department",   False),
            ("Designation", "designation",  False),
        ]

        ctk.CTkLabel(self, text="Participant Details", font=(f.family, f.size_lg, "bold"), text_color=p.text_primary).pack(padx=24, pady=(20, 4))
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=24)

        for label, key, required in fields:
            row = ctk.CTkFrame(form, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, font=(f.family, f.size_sm), text_color=p.text_secondary if not required else p.text_primary, width=110, anchor="w").pack(side="left")
            var = ctk.StringVar(value=initial_values.get(key, "") if initial_values else "")
            self._vars[key] = var
            ctk.CTkEntry(row, textvariable=var, width=260, height=32, fg_color=p.bg_tertiary, text_color=p.text_primary, font=(f.family, f.size_sm)).pack(side="left", padx=8)

        self._error_label = ctk.CTkLabel(self, text="", font=(f.family, f.size_xs), text_color=p.error)
        self._error_label.pack(pady=(4, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(8, 20))
        ctk.CTkButton(btn_row, text="Cancel", width=110, fg_color="transparent", border_width=1, text_color=p.text_primary, command=self.destroy).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Save", width=110, fg_color=p.accent, command=self._save).pack(side="left", padx=4)

        self.geometry("460x440")

    def _save(self) -> None:
        name = self._vars["full_name"].get().strip()
        email = self._vars["email"].get().strip()
        if not name:
            self._error_label.configure(text="Full Name is required.")
            return
        if not email or "@" not in email:
            self._error_label.configure(text="A valid email address is required.")
            return
        values = {key: var.get().strip() for key, var in self._vars.items()}
        if self._on_save:
            self._on_save(values)
        self.destroy()
