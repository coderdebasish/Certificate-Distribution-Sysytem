"""
app.ui.components.pdf_viewer
==============================
Inline PDF preview panel using PyMuPDF (fitz).

Renders a PDF page to a PIL CTkImage, displays it in a CTkLabel,
and supports zoom in/out, fit-to-width, fit-to-page, and mouse-wheel zoom.
"""

from __future__ import annotations

import logging
from pathlib import Path

import customtkinter as ctk
from app.ui.theme import ColorPalette, FontSystem

logger = logging.getLogger(__name__)

try:
    import fitz           # PyMuPDF
    from PIL import Image
    _PYMUPDF_AVAILABLE = True
except ImportError:
    _PYMUPDF_AVAILABLE = False


class PDFViewer(ctk.CTkFrame):
    """
    Embedded PDF page viewer.

    Usage::

        viewer = PDFViewer(parent, palette, fonts)
        viewer.pack(fill="both", expand=True)
        viewer.load(Path("path/to/cert.pdf"))
        viewer.clear()
    """

    MIN_ZOOM = 0.3
    MAX_ZOOM = 3.0
    ZOOM_STEP = 0.15

    def __init__(self, parent, palette: ColorPalette, fonts: FontSystem) -> None:
        super().__init__(parent, fg_color=palette.bg_tertiary, corner_radius=8)
        self._palette = palette
        self._fonts = fonts
        self._pdf_path: Path | None = None
        self._doc = None
        self._page_number = 0
        self._total_pages = 0
        self._zoom = 1.0
        self._ctk_img: ctk.CTkImage | None = None

        self._build()

    # -----------------------------------------------------------------------
    # Build
    # -----------------------------------------------------------------------

    def _build(self) -> None:
        p, f = self._palette, self._fonts

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=p.bg_secondary, corner_radius=0)
        toolbar.pack(fill="x")

        btn_kw = dict(width=32, height=28, fg_color="transparent",
                      hover_color=p.bg_hover, text_color=p.text_secondary,
                      font=(f.family, f.size_sm))

        ctk.CTkButton(toolbar, text="−", command=self._zoom_out, **btn_kw).pack(side="left", padx=2, pady=4)
        self._zoom_label = ctk.CTkLabel(toolbar, text="100%",
                                         font=(f.family, f.size_xs),
                                         text_color=p.text_disabled, width=44)
        self._zoom_label.pack(side="left")
        ctk.CTkButton(toolbar, text="＋", command=self._zoom_in, **btn_kw).pack(side="left", padx=2, pady=4)
        ctk.CTkButton(toolbar, text="⊞", command=self._fit_page, **btn_kw).pack(side="left", padx=4)
        ctk.CTkButton(toolbar, text="↔", command=self._fit_width, **btn_kw).pack(side="left", padx=4)

        # Page nav (right side)
        ctk.CTkButton(toolbar, text="◀", command=self._prev_page, **btn_kw).pack(side="right", padx=2, pady=4)
        self._page_label = ctk.CTkLabel(toolbar, text="—",
                                         font=(f.family, f.size_xs),
                                         text_color=p.text_disabled, width=60)
        self._page_label.pack(side="right")
        ctk.CTkButton(toolbar, text="▶", command=self._next_page, **btn_kw).pack(side="right", padx=2, pady=4)

        # Canvas for rendering
        self._canvas_frame = ctk.CTkScrollableFrame(
            self, fg_color=p.bg_tertiary, corner_radius=0
        )
        self._canvas_frame.pack(fill="both", expand=True)

        # Placeholder
        self._placeholder = ctk.CTkLabel(
            self._canvas_frame,
            text="No certificate selected.\nSelect a row to preview the PDF.",
            font=(f.family, f.size_sm),
            text_color=p.text_disabled,
            justify="center",
        )
        self._placeholder.pack(expand=True, pady=40)

        self._img_label: ctk.CTkLabel | None = None

        # Mouse wheel zoom
        self.bind("<MouseWheel>", self._on_mousewheel)

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def load(self, pdf_path: Path, page: int = 0) -> None:
        """Load a PDF and display the specified page."""
        if not _PYMUPDF_AVAILABLE:
            self._show_error("PyMuPDF not installed.\npip install PyMuPDF")
            return
        if not pdf_path.exists():
            self._show_error(f"File not found:\n{pdf_path.name}")
            return

        try:
            if self._doc:
                self._doc.close()
            self._doc = fitz.open(str(pdf_path))
            self._pdf_path = pdf_path
            self._total_pages = len(self._doc)
            self._page_number = max(0, min(page, self._total_pages - 1))
            self._fit_page()
        except Exception as exc:
            logger.error("PDF load failed: %s", exc)
            self._show_error(f"Cannot open PDF:\n{exc}")

    def clear(self) -> None:
        """Remove the displayed PDF."""
        if self._doc:
            self._doc.close()
            self._doc = None
        self._pdf_path = None
        if self._img_label:
            self._img_label.destroy()
            self._img_label = None
        self._placeholder.pack(expand=True, pady=40)
        self._page_label.configure(text="—")
        self._zoom_label.configure(text="100%")

    # -----------------------------------------------------------------------
    # Navigation & Zoom
    # -----------------------------------------------------------------------

    def _zoom_in(self) -> None:
        self._zoom = min(self.MAX_ZOOM, self._zoom + self.ZOOM_STEP)
        self._render()

    def _zoom_out(self) -> None:
        self._zoom = max(self.MIN_ZOOM, self._zoom - self.ZOOM_STEP)
        self._render()

    def _fit_page(self) -> None:
        if not self._doc:
            return
        page = self._doc[self._page_number]
        rect = page.rect
        self.update_idletasks()
        cw = self._canvas_frame.winfo_width()
        ch = self._canvas_frame.winfo_height()
        w = cw if cw > 100 else 420
        h = ch if ch > 100 else 280
        scale_w = (w - 30) / rect.width
        scale_h = (h - 30) / rect.height
        self._zoom = max(0.2, min(scale_w, scale_h))
        self._render()

    def _fit_width(self) -> None:
        if not self._doc:
            return
        page = self._doc[self._page_number]
        self.update_idletasks()
        cw = self._canvas_frame.winfo_width()
        w = cw if cw > 100 else 420
        self._zoom = max(0.2, (w - 30) / page.rect.width)
        self._render()

    def _prev_page(self) -> None:
        if self._doc and self._page_number > 0:
            self._page_number -= 1
            self._render()

    def _next_page(self) -> None:
        if self._doc and self._page_number < self._total_pages - 1:
            self._page_number += 1
            self._render()

    def _on_mousewheel(self, event) -> None:
        if event.delta > 0:
            self._zoom_in()
        else:
            self._zoom_out()

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def _render(self) -> None:
        if not self._doc or not _PYMUPDF_AVAILABLE:
            return
        page = self._doc[self._page_number]
        mat = fitz.Matrix(2.0, 2.0)  # Render crisp high-DPI image
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

        disp_w = max(50, int(page.rect.width * self._zoom))
        disp_h = max(50, int(page.rect.height * self._zoom))

        self._ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(disp_w, disp_h))

        # Hide placeholder
        self._placeholder.pack_forget()

        if self._img_label:
            self._img_label.configure(image=self._ctk_img)
        else:
            self._img_label = ctk.CTkLabel(
                self._canvas_frame, image=self._ctk_img, text=""
            )
            self._img_label.pack(expand=True, pady=8)

        self._page_label.configure(
            text=f"{self._page_number + 1} / {self._total_pages}"
        )
        self._zoom_label.configure(text=f"{int(self._zoom * 100)}%")

    def _show_error(self, message: str) -> None:
        self._placeholder.configure(text=message,
                                     text_color=self._palette.error)
        self._placeholder.pack(expand=True, pady=40)
