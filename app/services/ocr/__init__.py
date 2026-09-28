"""app.services.ocr package"""

from app.services.ocr.base import OCREngine, OCRResult
from app.services.ocr.tesseract_ocr import TesseractOCREngine
from app.services.ocr.paddle_ocr import PaddleOCREngine


def get_best_ocr_engine() -> OCREngine:
    """Return the highest priority available OCR engine (Tesseract or PaddleOCR)."""
    tess = TesseractOCREngine()
    if tess.is_available():
        return tess

    paddle = PaddleOCREngine()
    if paddle.is_available():
        return paddle

    return tess
