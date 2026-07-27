"""
app.services.ocr.paddle_ocr
============================
PaddleOCR implementation of the OCREngine interface.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.services.ocr.base import OCREngine, OCRResult

logger = logging.getLogger(__name__)


class PaddleOCREngine(OCREngine):
    """
    OCR engine backed by PaddleOCR.

    PaddleOCR is initialized lazily (on first use) to avoid slowing down
    application startup.
    """

    def __init__(self, language: str = "en", use_gpu: bool = False) -> None:
        self._language = language
        self._use_gpu = use_gpu
        self._ocr_instance = None   # Lazy init

    @property
    def name(self) -> str:
        return "PaddleOCR"

    def is_available(self) -> bool:
        try:
            import paddleocr  # noqa: F401
            import paddle      # noqa: F401
            return True
        except ImportError:
            return False

    def extract_text_from_image(self, image_path: Path) -> OCRResult:
        ocr = self._get_instance()
        try:
            results = ocr.ocr(str(image_path), cls=True)
            return self._parse_results(results)
        except Exception as exc:
            logger.error("PaddleOCR failed on image %s: %s", image_path, exc)
            return OCRResult(engine_name=self.name)

    def extract_text_from_pdf_page(self, pdf_path: Path, page_number: int = 0) -> OCRResult:
        """Rasterize the specified page to a PNG, then run OCR."""
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        if page_number >= len(doc):
            logger.warning("Page %d does not exist in %s", page_number, pdf_path)
            return OCRResult(engine_name=self.name, page_number=page_number)

        page = doc[page_number]
        mat = fitz.Matrix(2.0, 2.0)   # 2× zoom for higher OCR accuracy
        pix = page.get_pixmap(matrix=mat)
        doc.close()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        pix.save(str(tmp_path))

        result = self.extract_text_from_image(tmp_path)
        result.page_number = page_number
        tmp_path.unlink(missing_ok=True)
        return result

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _get_instance(self):
        if self._ocr_instance is None:
            from paddleocr import PaddleOCR
            self._ocr_instance = PaddleOCR(
                use_angle_cls=True,
                lang=self._language,
                use_gpu=self._use_gpu,
                show_log=False,
            )
        return self._ocr_instance

    def _parse_results(self, results) -> OCRResult:
        """Convert PaddleOCR raw output into an OCRResult."""
        lines: list[str] = []
        confidences: list[float] = []

        for page_result in (results or []):
            for line in (page_result or []):
                if line and len(line) >= 2:
                    text, conf = line[1]
                    lines.append(str(text).strip())
                    confidences.append(float(conf) * 100.0)

        full_text = "\n".join(lines)
        avg_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0
        return OCRResult(
            text=full_text,
            confidence=round(avg_confidence, 2),
            engine_name=self.name,
        )
