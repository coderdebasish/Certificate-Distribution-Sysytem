"""
app.services.ocr.tesseract_ocr
===============================
Tesseract OCR implementation of the OCREngine interface.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from app.services.ocr.base import OCREngine, OCRResult

logger = logging.getLogger(__name__)

# Common Tesseract binary locations on Windows
KNOWN_TESSERACT_PATHS = [
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    Path(os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")),
]


class TesseractOCREngine(OCREngine):
    """
    OCR engine backed by Tesseract OCR (via pytesseract).
    """

    def __init__(self, language: str = "eng") -> None:
        self._language = language
        self._configured = False
        self._tesseract_cmd = ""
        self._init_engine()

    @property
    def name(self) -> str:
        return "TesseractOCR"

    def is_available(self) -> bool:
        return self._configured

    def extract_text_from_image(self, image_path: Path) -> OCRResult:
        if not self._configured:
            return OCRResult(engine_name=self.name)

        import pytesseract
        from PIL import Image

        try:
            img = Image.open(image_path)
            raw_text = pytesseract.image_to_string(img, lang=self._language)
            
            # Calculate average confidence score
            conf = 0.0
            try:
                data = pytesseract.image_to_data(img, lang=self._language, output_type=pytesseract.Output.DICT)
                confs = [float(c) for c in data.get("conf", []) if isinstance(c, (int, float, str)) and str(c).replace(".", "", 1).isdigit() and float(c) > 0]
                if confs:
                    conf = sum(confs) / len(confs)
            except Exception as exc:
                logger.debug("Failed to calculate detailed Tesseract confidence: %s", exc)
                conf = 85.0 if raw_text.strip() else 0.0

            return OCRResult(
                text=raw_text.strip(),
                confidence=conf,
                engine_name=self.name,
            )
        except Exception as exc:
            logger.error("Tesseract OCR failed on image %s: %s", image_path, exc)
            return OCRResult(engine_name=self.name)

    def extract_text_from_pdf_page(self, pdf_path: Path, page_number: int = 0) -> OCRResult:
        """Rasterize page to high-res image and run Tesseract OCR."""
        if not self._configured:
            return OCRResult(engine_name=self.name, page_number=page_number)

        import fitz  # PyMuPDF

        try:
            doc = fitz.open(str(pdf_path))
            if page_number >= len(doc):
                logger.warning("Page %d does not exist in %s", page_number, pdf_path)
                doc.close()
                return OCRResult(engine_name=self.name, page_number=page_number)

            page = doc[page_number]
            mat = fitz.Matrix(2.5, 2.5)  # 2.5× zoom for maximum character resolution
            pix = page.get_pixmap(matrix=mat)
            doc.close()

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            pix.save(str(tmp_path))

            result = self.extract_text_from_image(tmp_path)
            result.page_number = page_number
            tmp_path.unlink(missing_ok=True)
            return result
        except Exception as exc:
            logger.error("Failed to rasterize PDF page for Tesseract OCR %s: %s", pdf_path, exc)
            return OCRResult(engine_name=self.name, page_number=page_number)

    # -----------------------------------------------------------------------
    # Internal Initialization & Auto-Detection
    # -----------------------------------------------------------------------

    def _init_engine(self) -> None:
        try:
            import pytesseract

            # 1. Check if tesseract is on PATH or already configured
            try:
                pytesseract.get_tesseract_version()
                self._configured = True
                return
            except Exception:
                pass

            # 2. Check known Windows paths
            for path in KNOWN_TESSERACT_PATHS:
                if path.exists():
                    pytesseract.pytesseract.tesseract_cmd = str(path)
                    try:
                        pytesseract.get_tesseract_version()
                        self._configured = True
                        self._tesseract_cmd = str(path)
                        logger.info("Auto-configured Tesseract OCR binary: %s", path)
                        return
                    except Exception:
                        continue
        except ImportError:
            pass

        self._configured = False
