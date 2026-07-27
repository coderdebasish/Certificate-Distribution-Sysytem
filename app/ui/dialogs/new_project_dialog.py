"""
app.ui.dialogs.new_project_dialog
===================================
Modal dialog for creating a new Certificate Distribution Project.
"""

from __future__ import annotations

import tkinter.filedialog as fd
import customtkinter as ctk
from pathlib import Path
from app.ui.theme import ColorPalette, FontSystem


class NewProjectDialog(ctk.CTkToplevel):
    """
    Modal dialog to collect project setup details.
    """

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem, on_create=None) -> None:
        super().__init__(parent)
        self.title("Create New Project")
        self.resizable(False, False)
        self.grab_set()

        self._palette = palette
        self._fonts = fonts
        self._on_create = on_create

        self.configure(fg_color=palette.bg_secondary)
        self._build()
        self._center()

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        ctk.CTkLabel(self, text="Create New Project",
                     font=(f.family, f.size_lg, "bold"),
                     text_color=p.text_primary).pack(padx=24, pady=(20, 4))

        ctk.CTkLabel(self, text="Set up a workspace for your event certificate distribution.",
                     font=(f.family, f.size_sm),
                     text_color=p.text_secondary).pack(padx=24, pady=(0, 16))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=24)

        # Project Name
        r1 = ctk.CTkFrame(form, fg_color="transparent")
        r1.pack(fill="x", pady=4)
        ctk.CTkLabel(r1, text="Project Name *", font=(f.family, f.size_sm), text_color=p.text_primary, width=120, anchor="w").pack(side="left")
        self._name_var = ctk.StringVar()
        ctk.CTkEntry(r1, textvariable=self._name_var, width=280, height=32, fg_color=p.bg_tertiary, text_color=p.text_primary, placeholder_text="e.g. Innovation Symposium 2026").pack(side="left")

        # Event Name
        r2 = ctk.CTkFrame(form, fg_color="transparent")
        r2.pack(fill="x", pady=4)
        ctk.CTkLabel(r2, text="Event Title *", font=(f.family, f.size_sm), text_color=p.text_primary, width=120, anchor="w").pack(side="left")
        self._event_var = ctk.StringVar()
        ctk.CTkEntry(r2, textvariable=self._event_var, width=280, height=32, fg_color=p.bg_tertiary, text_color=p.text_primary, placeholder_text="e.g. National Tech Fest 2026").pack(side="left")

        # Project Directory
        r3 = ctk.CTkFrame(form, fg_color="transparent")
        r3.pack(fill="x", pady=4)
        ctk.CTkLabel(r3, text="Location *", font=(f.family, f.size_sm), text_color=p.text_primary, width=120, anchor="w").pack(side="left")
        self._dir_var = ctk.StringVar(value=str(Path.home() / "Documents" / "CDMS_Projects"))
        ctk.CTkEntry(r3, textvariable=self._dir_var, width=200, height=32, fg_color=p.bg_tertiary, text_color=p.text_primary).pack(side="left")
        ctk.CTkButton(r3, text="Browse...", width=72, height=32, fg_color="transparent", border_width=1, text_color=p.text_primary, command=self._browse_dir).pack(side="left", padx=(8, 0))

        self._err_lbl = ctk.CTkLabel(self, text="", font=(f.family, f.size_xs), text_color=p.error)
        self._err_lbl.pack(pady=(4, 0))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(padx=24, pady=(12, 20))

        ctk.CTkButton(btn_frame, text="Cancel", width=110, fg_color="transparent", border_width=1, text_color=p.text_primary, command=self.destroy).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="Create Project", width=130, fg_color=p.accent, command=self._create).pack(side="left", padx=4)

        self.geometry("480x360")

    def _browse_dir(self) -> None:
        d = fd.askdirectory(title="Select Parent Directory for Project Folder")
        if d:
            self._dir_var.set(d)

    def _create(self) -> None:
        name = self._name_var.get().strip()
        event = self._event_var.get().strip()
        location = self._dir_var.get().strip()

        if not name or not event or not location:
            self._err_lbl.configure(text="Please fill in all required fields.")
            return

        if self._on_create:
            self._on_create(name, event, location)
        self.destroy()

    def _center(self) -> None:
        self.update_idletasks()
        pw, ph = self.winfo_width(), self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"+{(sw - pw) // 2}+{(sh - ph) // 2}")
