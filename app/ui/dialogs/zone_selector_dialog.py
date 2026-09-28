"""
app.ui.dialogs.zone_selector_dialog
====================================
Interactive visual dialog for defining the Name Area (ROI Bounding Box)
on a sample certificate template for batch processing.
"""

from __future__ import annotations

import logging
from pathlib import Path
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageTk

try:
    import fitz  # PyMuPDF
    _PYMUPDF_AVAILABLE = True
except ImportError:
    _PYMUPDF_AVAILABLE = False

from app.services.ocr.name_detector import NameDetector
from app.ui.theme import ColorPalette, FontSystem

logger = logging.getLogger(__name__)


class ZoneSelectorDialog(ctk.CTkToplevel):
    """
    Modal dialog allowing the user to click & drag a rectangle over the participant
    name on a sample certificate. The normalized coordinates (0.0–1.0) are returned
    via the on_apply callback.
    """

    def __init__(
        self,
        parent,
        pdf_path: Path,
        initial_zone: tuple[float, float, float, float] | None,
        on_apply: Callable[[tuple[float, float, float, float]], None],
        palette: ColorPalette,
        fonts: FontSystem,
        participant_names: list[str] | set[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self._parent = parent
        self._pdf_path = pdf_path
        self._on_apply = on_apply
        self._palette = palette
        self._fonts = fonts
        self._participant_names = list(participant_names) if participant_names else []
        self._detector = NameDetector()

        # Default zone: centered horizontal strip if none provided
        self._zone: list[float] = list(initial_zone) if initial_zone else [0.15, 0.44, 0.85, 0.56]

        self._doc = None
        self._orig_img: Image.Image | None = None
        self._tk_img: ImageTk.PhotoImage | None = None
        self._img_x = 0
        self._img_y = 0
        self._img_w = 1
        self._img_h = 1

        self._start_x = 0
        self._start_y = 0
        self._is_dragging = False

        self._rect_id: int | None = None
        self._tag_rect_id: int | None = None
        self._tag_text_id: int | None = None

        self._init_window()
        self._load_pdf()
        self._build_ui()
        self._update_extraction_preview()

        # Focus & modal grab
        self.after(100, self._grab_focus)

    def _grab_focus(self) -> None:
        try:
            self.grab_set()
            self.focus_set()
        except Exception:
            pass

    def _init_window(self) -> None:
        self.title("🎯 Set Name Area for this Folder")
        self.geometry("1060x780")
        self.minsize(850, 650)
        self.configure(fg_color=self._palette.bg_primary)
        self.transient(self._parent)

    def _load_pdf(self) -> None:
        if not _PYMUPDF_AVAILABLE or not self._pdf_path.exists():
            return
        try:
            self._doc = fitz.open(str(self._pdf_path))
            page = self._doc[0]
            mat = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            self._orig_img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        except Exception as exc:
            logger.error("Failed to load PDF for zone selection: %s", exc)

    def _build_ui(self) -> None:
        p, f = self._palette, self._fonts

        # Header Frame
        header = ctk.CTkFrame(self, fg_color=p.bg_card, corner_radius=0, height=54)
        header.pack(fill="x", side="top")

        title_lbl = ctk.CTkLabel(
            header, text="🎯 Define Name Area for this Folder",
            font=(f.family, f.size_md, "bold"), text_color=p.text_primary
        )
        title_lbl.pack(side="left", padx=20, pady=(10, 2))

        sub_lbl = ctk.CTkLabel(
            header,
            text="Click & drag a box over the participant name. All certificates in this folder will use this exact area.",
            font=(f.family, f.size_xs), text_color=p.text_secondary
        )
        sub_lbl.pack(side="left", padx=8, pady=(12, 2))

        # Bottom Bar: Live extracted name & action buttons
        bottom_bar = ctk.CTkFrame(self, fg_color=p.bg_card, corner_radius=0)
        bottom_bar.pack(fill="x", side="bottom", padx=0, pady=0)

        # Extraction result card
        res_frame = ctk.CTkFrame(bottom_bar, fg_color=p.bg_input, corner_radius=8, border_width=1, border_color=p.border)
        res_frame.pack(fill="x", padx=20, pady=(12, 8))

        res_left = ctk.CTkFrame(res_frame, fg_color="transparent")
        res_left.pack(side="left", padx=14, pady=8)

        ctk.CTkLabel(
            res_left, text="Detected Name from Box:",
            font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary
        ).pack(anchor="w")

        self._extracted_label = ctk.CTkLabel(
            res_left, text="Checking...",
            font=(f.family, f.size_md, "bold"), text_color=p.accent
        )
        self._extracted_label.pack(anchor="w")

        self._confidence_label = ctk.CTkLabel(
            res_frame, text="",
            font=(f.family, f.size_xs), text_color=p.text_secondary
        )
        self._confidence_label.pack(side="right", padx=20)

        # Sliders & Presets Row
        ctrl_frame = ctk.CTkFrame(bottom_bar, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=20, pady=(0, 12))

        # Quick preset buttons
        preset_box = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        preset_box.pack(side="left")

        ctk.CTkLabel(preset_box, text="Presets:", font=(f.family, f.size_xs, "bold"), text_color=p.text_secondary).pack(side="left", padx=(0, 6))

        presets = [
            ("Standard Center", [0.15, 0.44, 0.85, 0.56]),
            ("Upper Center",    [0.15, 0.35, 0.85, 0.48]),
            ("Lower Center",    [0.15, 0.52, 0.85, 0.65]),
            ("Full Width",      [0.05, 0.42, 0.95, 0.58]),
        ]
        for name, coords in presets:
            btn = ctk.CTkButton(
                preset_box, text=name, width=95, height=28,
                fg_color=p.bg_secondary, hover_color=p.bg_hover,
                text_color=p.text_primary, font=(f.family, f.size_xs),
                command=lambda c=coords: self._apply_preset(c)
            )
            btn.pack(side="left", padx=3)

        # Buttons on right
        btn_box = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_box.pack(side="right")

        self._cancel_btn = ctk.CTkButton(
            btn_box, text="✕ Cancel", width=100, height=32,
            fg_color=p.bg_secondary, hover_color=p.bg_hover,
            text_color=p.text_primary, font=(f.family, f.size_sm),
            command=self._on_cancel
        )
        self._cancel_btn.pack(side="left", padx=(0, 8))

        self._apply_btn = ctk.CTkButton(
            btn_box, text="✓ Apply to this Folder", width=170, height=32,
            fg_color=p.accent, hover_color=p.accent_hover,
            text_color=p.accent_text, font=(f.family, f.size_sm, "bold"),
            command=self._on_apply_clicked
        )
        self._apply_btn.pack(side="left")

        # Canvas Area for interactive rectangle selection
        self._canvas_container = ctk.CTkFrame(self, fg_color=p.bg_tertiary, corner_radius=0)
        self._canvas_container.pack(fill="both", expand=True, padx=20, pady=12)

        self._canvas = tk.Canvas(
            self._canvas_container, bg=p.bg_tertiary, highlightthickness=0, cursor="crosshair"
        )
        self._canvas.pack(fill="both", expand=True)

        self._canvas.bind("<Configure>", self._on_canvas_resize)
        self._canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self._canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

    # -----------------------------------------------------------------------
    # Canvas Rendering & Geometry
    # -----------------------------------------------------------------------

    def _on_canvas_resize(self, event=None) -> None:
        if not self._orig_img:
            return

        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw < 50 or ch < 50:
            return

        # Fit image while preserving aspect ratio with padding
        iw, ih = self._orig_img.size
        scale = min((cw - 40) / iw, (ch - 40) / ih)
        nw, nh = max(50, int(iw * scale)), max(50, int(ih * scale))

        resized = self._orig_img.resize((nw, nh), Image.Resampling.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized)

        self._img_w = nw
        self._img_h = nh
        self._img_x = (cw - nw) // 2
        self._img_y = (ch - nh) // 2

        self._canvas.delete("all")
        self._canvas.create_image(self._img_x, self._img_y, anchor="nw", image=self._tk_img)

        # Draw current zone box
        self._draw_box()

    def _draw_box(self) -> None:
        x0, y0, x1, y1 = self._zone
        bx0 = self._img_x + int(x0 * self._img_w)
        by0 = self._img_y + int(y0 * self._img_h)
        bx1 = self._img_x + int(x1 * self._img_w)
        by1 = self._img_y + int(y1 * self._img_h)

        if self._rect_id:
            self._canvas.delete(self._rect_id)
        if self._tag_rect_id:
            self._canvas.delete(self._tag_rect_id)
        if self._tag_text_id:
            self._canvas.delete(self._tag_text_id)

        # Outer highlight box
        self._rect_id = self._canvas.create_rectangle(
            bx0, by0, bx1, by1,
            outline="#3B82F6", width=3, dash=(6, 4)
        )

        # Small top badge
        tag_w = 90
        tag_h = 20
        tag_y = max(self._img_y, by0 - tag_h)
        self._tag_rect_id = self._canvas.create_rectangle(
            bx0, tag_y, bx0 + tag_w, tag_y + tag_h,
            fill="#3B82F6", outline="#3B82F6"
        )
        self._tag_text_id = self._canvas.create_text(
            bx0 + (tag_w // 2), tag_y + (tag_h // 2),
            text="NAME AREA", fill="#FFFFFF",
            font=("Segoe UI", 9, "bold")
        )

    # -----------------------------------------------------------------------
    # Mouse Handlers (Click & Drag ROI)
    # -----------------------------------------------------------------------

    def _on_mouse_down(self, event) -> None:
        self._start_x = event.x
        self._start_y = event.y
        self._is_dragging = True

    def _on_mouse_drag(self, event) -> None:
        if not self._is_dragging:
            return

        cx0 = min(self._start_x, event.x)
        cy0 = min(self._start_y, event.y)
        cx1 = max(self._start_x, event.x)
        cy1 = max(self._start_y, event.y)

        # Convert to normalized zone coordinates
        nx0 = max(0.0, min(1.0, (cx0 - self._img_x) / self._img_w))
        ny0 = max(0.0, min(1.0, (cy0 - self._img_y) / self._img_h))
        nx1 = max(0.0, min(1.0, (cx1 - self._img_x) / self._img_w))
        ny1 = max(0.0, min(1.0, (cy1 - self._img_y) / self._img_h))

        if nx1 - nx0 > 0.02 and ny1 - ny0 > 0.01:
            self._zone = [round(nx0, 4), round(ny0, 4), round(nx1, 4), round(ny1, 4)]
            self._draw_box()

    def _on_mouse_up(self, event) -> None:
        self._is_dragging = False
        self._draw_box()
        self._update_extraction_preview()

    def _apply_preset(self, coords: list[float]) -> None:
        self._zone = list(coords)
        self._draw_box()
        self._update_extraction_preview()

    # -----------------------------------------------------------------------
    # Live Extraction Preview
    # -----------------------------------------------------------------------

    def _update_extraction_preview(self) -> None:
        if not self._doc:
            self._extracted_label.configure(text="No document loaded", text_color=self._palette.error)
            return

        page = self._doc[0]
        pw, ph = page.rect.width, page.rect.height
        x0, y0, x1, y1 = self._zone
        clip = fitz.Rect(max(0.0, x0 * pw), max(0.0, y0 * ph), min(pw, x1 * pw), min(ph, y1 * ph))

        # Vector text extraction inside the zone
        extracted = page.get_text("text", clip=clip).strip()

        if extracted:
            res = self._detector.detect_from_zone(extracted, self._participant_names)
            name = res.detected_name
            conf = res.confidence
            self._extracted_label.configure(
                text=f'"{name}"', text_color=self._palette.success
            )
            self._confidence_label.configure(
                text=f"Extraction Confidence: {conf:.0f}%  (Zone text: {len(name)} chars)",
                text_color=self._palette.success
            )
        else:
            self._extracted_label.configure(
                text="[ No selectable text in box ]", text_color=self._palette.warning
            )
            self._confidence_label.configure(
                text="If this certificate is a scanned image, OCR will be run on this cropped box.",
                text_color=self._palette.text_secondary
            )

    # -----------------------------------------------------------------------
    # Close / Apply
    # -----------------------------------------------------------------------

    def _on_apply_clicked(self) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None
        self._on_apply(tuple(self._zone))
        self.destroy()

    def _on_cancel(self) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None
        self.destroy()
