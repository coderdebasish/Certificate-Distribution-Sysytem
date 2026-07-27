"""
app.services.ocr.base
=====================
Abstract base class for OCR engines.  All concrete OCR implementations must
subclass ``OCREngine`` so they can be swapped without touching calling code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OCRResult:
    """Result returned by an OCR engine for a single PDF page."""
    text: str = ""
    confidence: float = 0.0        # 0.0 – 100.0
    page_number: int = 1
    engine_name: str = ""


class OCREngine(ABC):
    """
    Abstract OCR engine interface.

    Concrete implementations (e.g. PaddleOCR) must override the methods below.
    The rest of the application only depends on this interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name, e.g. 'PaddleOCR'."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the engine dependencies are installed and ready."""

    @abstractmethod
    def extract_text_from_image(self, image_path: Path) -> OCRResult:
        """
        Run OCR on a single image file.

        :param image_path: Path to the image file (PNG/JPEG rasterized from PDF).
        :returns: OCRResult with extracted text and confidence.
        """

    @abstractmethod
    def extract_text_from_pdf_page(self, pdf_path: Path, page_number: int = 0) -> OCRResult:
        """
        Rasterize one PDF page and run OCR on it.

        :param pdf_path: Path to the PDF file.
        :param page_number: Zero-based page index.
        :returns: OCRResult with extracted text and confidence.
        """

    def extract_all_pages(self, pdf_path: Path) -> list[OCRResult]:
        """
        Run OCR on every page of a PDF.  Default: iterates ``extract_text_from_pdf_page``.
        Subclasses may override for performance.
        """
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        results: list[OCRResult] = []
        for page_num in range(len(doc)):
            result = self.extract_text_from_pdf_page(pdf_path, page_num)
            results.append(result)
        doc.close()
        return results
