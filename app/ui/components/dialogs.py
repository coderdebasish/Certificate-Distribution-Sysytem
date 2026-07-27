"""
app.ui.components.dialogs
==========================
Reusable dialog boxes: confirmation, error, info, input.
"""

from __future__ import annotations
import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


class ConfirmDialog(ctk.CTkToplevel):
    """
    Modal confirmation dialog.

    Usage::

        dialog = ConfirmDialog(parent, palette, fonts,
                               title="Delete Participant",
                               message="Are you sure you want to delete Debasish Mohanty?",
                               detail="This action can be undone.")
        if dialog.result:
            ...
    """

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem,
                 title: str, message: str, detail: str = "",
                 confirm_text: str = "Confirm", danger: bool = False) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.result = False

        self._palette = palette
        self._fonts = fonts

        self.configure(fg_color=palette.bg_secondary)
        self._build(title, message, detail, confirm_text, danger)
        
        # Center dialog on parent
        self.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

        self.grab_set()
        self.wait_window()

    def _build(self, title: str, message: str, detail: str, confirm_text: str, danger: bool) -> None:
        ctk.CTkLabel(
            self, text=title,
            font=(self._fonts.family, self._fonts.size_lg, "bold"),
            text_color=self._palette.text_primary
        ).pack(padx=24, pady=(20, 4))

        ctk.CTkLabel(
            self, text=message,
            font=(self._fonts.family, self._fonts.size_md),
            text_color=self._palette.text_primary,
            wraplength=380
        ).pack(padx=24, pady=8)

        if detail:
            ctk.CTkLabel(
                self, text=detail,
                font=(self._fonts.family, self._fonts.size_sm),
                text_color=self._palette.text_secondary,
                wraplength=380
            ).pack(padx=24, pady=4)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=24, pady=(12, 20))

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            fg_color="transparent", border_width=1,
            text_color=self._palette.text_primary,
            command=self._cancel
        ).pack(side="left", padx=4)

        confirm_color = self._palette.error if danger else self._palette.accent
        ctk.CTkButton(
            btn_frame, text=confirm_text, width=100,
            fg_color=confirm_color,
            command=self._confirm
        ).pack(side="left", padx=4)

    def _confirm(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()


class ErrorDialog(ctk.CTkToplevel):
    """Display a user-friendly error message."""

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem,
                 title: str, message: str, details: str = "") -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=palette.bg_secondary)

        ctk.CTkLabel(
            self, text="⚠  " + title,
            font=(fonts.family, fonts.size_lg, "bold"),
            text_color=palette.error
        ).pack(padx=24, pady=(20, 4))

        ctk.CTkLabel(
            self, text=message,
            font=(fonts.family, fonts.size_md),
            text_color=palette.text_primary,
            wraplength=380
        ).pack(padx=24, pady=4)

        if details:
            ctk.CTkLabel(
                self, text=details,
                font=(fonts.family, fonts.size_sm),
                text_color=palette.text_secondary,
                wraplength=380
            ).pack(padx=24, pady=4)

        ctk.CTkButton(
            self, text="OK", width=100,
            fg_color=palette.accent,
            command=self.destroy
        ).pack(pady=(12, 20))

        # Center dialog on parent
        self.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

        self.grab_set()
        self.wait_window()


class ColumnMapDialog(ctk.CTkToplevel):
    """Dialog for mapping spreadsheet headers to system participant fields."""

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem, headers: list[str]) -> None:
        super().__init__(parent)
        self.title("Map Excel/CSV Columns")
        self.resizable(False, False)
        self.configure(fg_color=palette.bg_secondary)
        self._palette = palette
        self._fonts = fonts
        self._headers = ["(Skip Column)"] + headers
        self.mapping: dict[str, str] | None = None

        self._combo_vars: dict[str, ctk.StringVar] = {}
        self._build(headers)

        self.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

        self.grab_set()
        self.wait_window()

    def _build(self, raw_headers: list[str]) -> None:
        p, f = self._palette, self._fonts

        ctk.CTkLabel(self, text="📥  Excel/CSV Column Mapping", font=(f.family, f.size_lg, "bold"), text_color=p.text_primary).pack(padx=24, pady=(16, 4))
        ctk.CTkLabel(self, text="Select which spreadsheet column matches each participant field.", font=(f.family, f.size_xs), text_color=p.text_secondary).pack(padx=24, pady=(0, 12))

        fields = [
            ("full_name", "Full Name *"),
            ("email", "Email Address *"),
            ("college", "College / Institution"),
            ("department", "Department / Branch"),
            ("designation", "Designation / Role"),
            ("phone", "Phone Number"),
        ]

        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(padx=24, pady=4, fill="x")

        for key, label_text in fields:
            row = ctk.CTkFrame(form_frame, fg_color="transparent", height=32)
            row.pack(fill="x", pady=3)

            ctk.CTkLabel(row, text=label_text, font=(f.family, f.size_xs, "bold"), text_color=p.text_primary, width=150, anchor="w").pack(side="left")

            # Smart auto-detection
            matched = "(Skip Column)"
            key_lower = key.lower()
            for h in raw_headers:
                h_lower = h.lower()
                if key == "full_name" and any(k in h_lower for k in ["name", "participant", "candidate", "student"]):
                    matched = h
                    break
                elif key == "email" and any(k in h_lower for k in ["email", "mail"]):
                    matched = h
                    break
                elif key == "college" and any(k in h_lower for k in ["college", "university", "institute", "school"]):
                    matched = h
                    break
                elif key == "department" and any(k in h_lower for k in ["dept", "department", "branch", "stream"]):
                    matched = h
                    break
                elif key == "designation" and any(k in h_lower for k in ["role", "designation", "position"]):
                    matched = h
                    break
                elif key == "phone" and any(k in h_lower for k in ["phone", "mobile", "contact"]):
                    matched = h
                    break

            var = ctk.StringVar(value=matched)
            self._combo_vars[key] = var

            combo = ctk.CTkComboBox(
                row, values=self._headers, variable=var,
                width=240, height=28, font=(f.family, f.size_xs),
                fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary,
                dropdown_fg_color=p.bg_card, dropdown_text_color=p.text_primary
            )
            combo.pack(side="left", fill="x", expand=True)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(padx=24, pady=(16, 20))

        ctk.CTkButton(
            btn_row, text="Cancel", width=100,
            fg_color="transparent", border_width=1, border_color=p.border,
            text_color=p.text_primary, command=self._cancel
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row, text="✓  Confirm & Import", width=160,
            fg_color=p.accent, text_color=p.accent_text, command=self._confirm
        ).pack(side="left", padx=4)

    def _confirm(self) -> None:
        self.mapping = {}
        for key, var in self._combo_vars.items():
            val = var.get()
            if val and val != "(Skip Column)":
                self.mapping[key] = val
        self.destroy()

    def _cancel(self) -> None:
        self.mapping = None
        self.destroy()


class ParticipantEditDialog(ctk.CTkToplevel):
    """Dialog for manually adding or editing a participant record."""

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem, title: str = "Add Participant", initial_data: dict | None = None) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color=palette.bg_secondary)
        self._palette = palette
        self._fonts = fonts
        self.result: dict | None = None

        self._data = initial_data or {}
        self._entries: dict[str, ctk.CTkEntry] = {}
        self._build(title)

        self.update_idletasks()
        try:
            px = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
            py = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
            self.geometry(f"+{max(0, px)}+{max(0, py)}")
        except Exception:
            pass

        self.grab_set()
        self.wait_window()

    def _build(self, title_text: str) -> None:
        p, f = self._palette, self._fonts

        ctk.CTkLabel(self, text=title_text, font=(f.family, f.size_lg, "bold"), text_color=p.text_primary).pack(padx=24, pady=(16, 12))

        form_frame = ctk.CTkFrame(self, fg_color="transparent")
        form_frame.pack(padx=24, pady=4, fill="x")

        fields = [
            ("full_name", "Full Name *", self._data.get("full_name", "")),
            ("email", "Email Address *", self._data.get("email", "")),
            ("college", "College / Institution", self._data.get("college", "")),
            ("department", "Department", self._data.get("department", "")),
            ("designation", "Designation", self._data.get("designation", "")),
        ]

        for key, label_text, default_val in fields:
            row = ctk.CTkFrame(form_frame, fg_color="transparent")
            row.pack(fill="x", pady=4)

            ctk.CTkLabel(row, text=label_text, font=(f.family, f.size_xs, "bold"), text_color=p.text_primary).pack(anchor="w", pady=(0, 2))
            entry = ctk.CTkEntry(
                row, height=32, font=(f.family, f.size_xs),
                fg_color=p.bg_input, border_color=p.border, text_color=p.text_primary
            )
            entry.insert(0, default_val)
            entry.pack(fill="x")
            self._entries[key] = entry

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(padx=24, pady=(16, 20))

        ctk.CTkButton(
            btn_row, text="Cancel", width=100,
            fg_color="transparent", border_width=1, border_color=p.border,
            text_color=p.text_primary, command=self._cancel
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row, text="✓  Save", width=120,
            fg_color=p.accent, text_color=p.accent_text, command=self._confirm
        ).pack(side="left", padx=4)

    def _confirm(self) -> None:
        name = self._entries["full_name"].get().strip()
        email = self._entries["email"].get().strip()
        if not name or not email:
            return

        self.result = {
            "full_name": name,
            "email": email,
            "college": self._entries["college"].get().strip(),
            "department": self._entries["department"].get().strip(),
            "designation": self._entries["designation"].get().strip(),
        }
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

