"""
app.ui.components.data_table
==============================
Full-featured dark-themed sortable data table.

Built on ttk.Treeview with custom dark styling applied via ttk.Style.
Supports: column sorting, row color tagging, multi-select,
right-click context menu, integrated search bar.

CustomTkinter doesn't provide a native table widget, so we use the
standard ttk.Treeview embedded inside a CTkFrame, with the style
customised to match the CDMS dark theme.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.ttk as ttk
from typing import Any, Callable

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem


# ---------------------------------------------------------------------------
# Row tag constants
# ---------------------------------------------------------------------------
TAG_SUCCESS = "tag_success"
TAG_WARNING = "tag_warning"
TAG_ERROR   = "tag_error"
TAG_DISABLED = "tag_disabled"
TAG_SELECTED = "tag_selected"
TAG_ODD     = "tag_odd"
TAG_EVEN    = "tag_even"


class DataTable(ctk.CTkFrame):
    """
    Reusable dark-themed data table.

    Usage::

        table = DataTable(
            parent, palette, fonts,
            columns=["#", "Name", "Email", "Status"],
            col_widths=[40, 200, 240, 100],
            on_select=my_callback,       # called with (row_id, values_dict)
            context_menu=[
                ("Edit",   edit_cmd),
                ("Delete", delete_cmd),
            ],
        )
        table.pack(fill="both", expand=True)
        table.add_row({"#": "1", "Name": "Debasish Mohanty",
                       "Email": "d@example.com", "Status": "Matched"},
                      tag=TAG_SUCCESS)
        table.clear()
    """

    def __init__(
        self,
        parent,
        palette: ColorPalette,
        fonts: FontSystem,
        columns: list[str],
        col_widths: list[int] | None = None,
        stretch_col: int = 1,          # column index that stretches
        show_search: bool = True,
        show_row_count: bool = True,
        on_select: Callable[[str, dict], None] | None = None,
        on_double_click: Callable[[str, dict], None] | None = None,
        context_menu: list[tuple[str, Callable]] | None = None,
        multiselect: bool = False,
    ) -> None:
        super().__init__(parent, fg_color=palette.bg_secondary, corner_radius=12)
        self._palette = palette
        self._fonts = fonts
        self._columns = columns
        self._col_widths = col_widths or [120] * len(columns)
        self._stretch_col = stretch_col
        self._on_select = on_select
        self._on_double_click = on_double_click
        self._context_menu_items = context_menu or []
        self._multiselect = multiselect
        self._all_rows: list[dict] = []    # master data list (for filtering)
        self._sort_col: str = ""
        self._sort_reverse: bool = False

        self._apply_theme()
        self._build(show_search, show_row_count)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def add_row(self, values: dict[str, str], tag: str = "", row_id: str = "") -> str:
        """
        Append one row to the table.

        :param values:  Dict mapping column name → cell value.
        :param tag:     Optional row tag for coloring (TAG_SUCCESS, etc.).
        :param row_id:  Optional explicit iid; auto-generated if empty.
        :returns:       The iid of the inserted row.
        """
        cells = [str(values.get(col, "")) for col in self._columns]
        iid = row_id or str(len(self._all_rows))
        parity = TAG_ODD if len(self._all_rows) % 2 else TAG_EVEN
        tags = (tag, parity) if tag else (parity,)
        self._tree.insert("", "end", iid=iid, values=cells, tags=tags)
        self._all_rows.append({"_iid": iid, **values})
        self._update_count()
        return iid

    def update_row(self, row_id: str, values: dict[str, str], tag: str = "") -> None:
        """Update an existing row's values and tag."""
        if not self._tree.exists(row_id):
            return
        cells = [str(values.get(col, "")) for col in self._columns]
        parity = TAG_ODD if self._tree.index(row_id) % 2 else TAG_EVEN
        tags = (tag, parity) if tag else (parity,)
        self._tree.item(row_id, values=cells, tags=tags)
        # Update master list
        for row in self._all_rows:
            if row.get("_iid") == row_id:
                row.update(values)
                break

    def clear(self) -> None:
        """Remove all rows."""
        self._tree.delete(*self._tree.get_children())
        self._all_rows.clear()
        self._update_count()

    def get_selected(self) -> list[dict]:
        """Return list of selected rows' value dicts."""
        result = []
        for iid in self._tree.selection():
            values = self._tree.item(iid, "values")
            result.append(dict(zip(self._columns, values)))
        return result

    def get_all_rows(self) -> list[dict]:
        """Return all row dicts."""
        return list(self._all_rows)

    def select_row(self, row_id: str) -> None:
        """Programmatically select a row."""
        if self._tree.exists(row_id):
            self._tree.selection_set(row_id)
            self._tree.see(row_id)

    def set_row_count_label(self, text: str) -> None:
        """Override the row count label text."""
        if hasattr(self, "_count_label"):
            self._count_label.configure(text=text)

    # -----------------------------------------------------------------------
    # Build
    # -----------------------------------------------------------------------

    def _build(self, show_search: bool, show_row_count: bool) -> None:
        # ---- Toolbar ----
        if show_search or show_row_count:
            toolbar = ctk.CTkFrame(self, fg_color="transparent")
            toolbar.pack(fill="x", padx=12, pady=(10, 6))

            if show_row_count:
                self._count_label = ctk.CTkLabel(
                    toolbar, text="0 rows",
                    font=(self._fonts.family, self._fonts.size_xs),
                    text_color=self._palette.text_disabled,
                )
                self._count_label.pack(side="left", padx=4)

            if show_search:
                self._search_var = tk.StringVar()
                self._search_var.trace_add("write", self._on_search_change)
                ctk.CTkEntry(
                    toolbar,
                    placeholder_text="Search...",
                    textvariable=self._search_var,
                    width=220, height=30,
                    fg_color=self._palette.bg_tertiary,
                    text_color=self._palette.text_primary,
                    font=(self._fonts.family, self._fonts.size_sm),
                ).pack(side="right", padx=4)

        # ---- Scrollable container ----
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Scrollbars
        vsb = ttk.Scrollbar(container, orient="vertical", style="Vertical.TScrollbar")
        hsb = ttk.Scrollbar(container, orient="horizontal", style="Horizontal.TScrollbar")

        selectmode = "extended" if self._multiselect else "browse"
        self._tree = ttk.Treeview(
            container,
            columns=self._columns,
            show="headings",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set,
            selectmode=selectmode,
            style="CDMS.Treeview",
        )
        vsb.configure(command=self._tree.yview)
        hsb.configure(command=self._tree.xview)

        # Layout
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # ---- Column setup ----
        for i, col in enumerate(self._columns):
            width = self._col_widths[i] if i < len(self._col_widths) else 120
            stretch = (i == self._stretch_col)
            self._tree.column(col, width=width, minwidth=50, stretch=stretch)
            self._tree.heading(col, text=col,
                               command=lambda c=col: self._sort_by(c))

        # ---- Row tags ----
        p = self._palette
        self._tree.tag_configure(TAG_ODD,      background=p.table_row_odd)
        self._tree.tag_configure(TAG_EVEN,     background=p.table_row_even)
        self._tree.tag_configure(TAG_SUCCESS,  background="#1B3A2A", foreground="#81C784")
        self._tree.tag_configure(TAG_WARNING,  background="#3A2800", foreground="#FFB74D")
        self._tree.tag_configure(TAG_ERROR,    background="#3A1010", foreground="#EF9A9A")
        self._tree.tag_configure(TAG_DISABLED, background=p.bg_tertiary, foreground=p.text_disabled)

        # ---- Events ----
        self._tree.bind("<<TreeviewSelect>>", self._on_select_event)
        self._tree.bind("<Double-1>", self._on_double_click_event)
        if self._context_menu_items:
            self._tree.bind("<Button-3>", self._show_context_menu)
            self._ctx_menu = tk.Menu(self._tree, tearoff=0,
                                     bg=p.bg_secondary, fg=p.text_primary,
                                     activebackground=p.accent,
                                     activeforeground=p.accent_text,
                                     relief="flat", borderwidth=1)
            for label, cmd in self._context_menu_items:
                if label == "---":
                    self._ctx_menu.add_separator()
                else:
                    self._ctx_menu.add_command(label=label, command=cmd)

    # -----------------------------------------------------------------------
    # Theme
    # -----------------------------------------------------------------------

    def _apply_theme(self) -> None:
        p = self._palette
        f = self._fonts
        style = ttk.Style()
        style.theme_use("default")

        style.configure("CDMS.Treeview",
            background=p.table_row_even,
            foreground=p.text_primary,
            fieldbackground=p.table_row_even,
            rowheight=34,
            borderwidth=0,
            relief="flat",
            font=(f.family, f.size_sm),
        )
        style.configure("CDMS.Treeview.Heading",
            background=p.table_header,
            foreground=p.text_secondary,
            borderwidth=0,
            relief="flat",
            font=(f.family, f.size_sm, "bold"),
            padding=(8, 6),
        )
        style.map("CDMS.Treeview",
            background=[("selected", p.table_selected)],
            foreground=[("selected", p.accent_text)],
        )
        style.map("CDMS.Treeview.Heading",
            background=[("active", p.bg_hover)],
        )
        # Scrollbar
        style.configure("Vertical.TScrollbar",
            background=p.bg_tertiary, troughcolor=p.bg_secondary,
            borderwidth=0, relief="flat", width=8)
        style.configure("Horizontal.TScrollbar",
            background=p.bg_tertiary, troughcolor=p.bg_secondary,
            borderwidth=0, relief="flat", width=8)

    # -----------------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------------

    def _on_select_event(self, _event) -> None:
        if self._on_select is None:
            return
        sel = self._tree.selection()
        if sel:
            iid = sel[0]
            values = dict(zip(self._columns, self._tree.item(iid, "values")))
            self._on_select(iid, values)

    def _on_double_click_event(self, _event) -> None:
        if self._on_double_click is None:
            return
        sel = self._tree.selection()
        if sel:
            iid = sel[0]
            values = dict(zip(self._columns, self._tree.item(iid, "values")))
            self._on_double_click(iid, values)

    def _show_context_menu(self, event) -> None:
        iid = self._tree.identify_row(event.y)
        if iid:
            self._tree.selection_set(iid)
            self._ctx_menu.post(event.x_root, event.y_root)

    # -----------------------------------------------------------------------
    # Sort
    # -----------------------------------------------------------------------

    def _sort_by(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        col_idx = self._columns.index(col)
        rows = [(self._tree.set(iid, col), iid) for iid in self._tree.get_children("")]
        rows.sort(key=lambda x: x[0].lower(), reverse=self._sort_reverse)

        for idx, (_, iid) in enumerate(rows):
            self._tree.move(iid, "", idx)
            parity = TAG_ODD if idx % 2 else TAG_EVEN
            existing = list(self._tree.item(iid, "tags"))
            tags = [t for t in existing if t not in (TAG_ODD, TAG_EVEN)] + [parity]
            self._tree.item(iid, tags=tags)

        arrow = " ↑" if not self._sort_reverse else " ↓"
        for c in self._columns:
            suffix = arrow if c == col else ""
            self._tree.heading(c, text=c + suffix)

    # -----------------------------------------------------------------------
    # Search / filter
    # -----------------------------------------------------------------------

    def _on_search_change(self, *_) -> None:
        query = self._search_var.get().lower().strip()
        self._tree.delete(*self._tree.get_children())
        displayed = 0
        for idx, row in enumerate(self._all_rows):
            cells = [str(row.get(col, "")).lower() for col in self._columns]
            if not query or any(query in cell for cell in cells):
                values = [str(row.get(col, "")) for col in self._columns]
                parity = TAG_ODD if displayed % 2 else TAG_EVEN
                self._tree.insert("", "end", iid=row["_iid"], values=values, tags=(parity,))
                displayed += 1
        self._update_count(displayed)

    def _update_count(self, count: int | None = None) -> None:
        if hasattr(self, "_count_label"):
            n = count if count is not None else len(self._tree.get_children())
            total = len(self._all_rows)
            text = f"{n} row{'s' if n != 1 else ''}" if n == total else f"{n} / {total} rows"
            self._count_label.configure(text=text)
