"""
app.workers.ocr_worker
=======================
Background worker that scans a folder of PDF certificates,
extracts text (or runs OCR), detects participant names, and emits
a Signal per certificate as results arrive.

The GUI thread never blocks — it just polls signal_queue.
"""

from __future__ import annotations

import logging
import queue
from pathlib import Path
from typing import Callable, Optional

import fitz  # PyMuPDF

from app.services.ocr.base import OCREngine, OCRResult
from app.services.ocr.paddle_ocr import PaddleOCREngine
from app.services.ocr.name_detector import NameDetector, NameDetectionResult
from app.workers.base_worker import BaseWorker
from app.workers.signals import Signal, SignalType

logger = logging.getLogger(__name__)


class OCRWorker(BaseWorker):
    """
    Scans certificate PDFs in *source_folder* (or *pdf_folder*) and emits one
    ``CERTIFICATE_ANALYZED`` signal per file with the detected name.

    Text extraction is attempted first (faster).
    PaddleOCR is only invoked if text extraction yields nothing useful.
    """

    def __init__(
        self,
        signal_queue: Optional[queue.Queue[Signal]] = None,
        pdf_folder: Path | str | None = None,
        source_folder: Path | str | None = None,
        ocr_engine: Optional[OCREngine] = None,
        pdf_paths: list[Path] | None = None,
        db_conn=None,
        project_id: int = 0,
        ocr_threshold: float = 70.0,
    ) -> None:
        super().__init__(signal_queue=signal_queue)
        folder_path = pdf_folder or source_folder or "."
        self._source_folder = Path(folder_path)
        self._db_conn = db_conn
        self._project_id = project_id
        self._ocr_threshold = ocr_threshold
        self._ocr_engine = ocr_engine or PaddleOCREngine()
        self._name_detector = NameDetector()
        self._pdf_paths = pdf_paths

    def _run(self) -> None:
        pdfs = self._pdf_paths or sorted(self._source_folder.glob("*.pdf"))
        total = len(pdfs)

        if total == 0:
            self._emit(Signal.error("No PDF files found in the selected folder."))
            return

        self._emit(Signal.log(f"Starting analysis of {total} certificate(s)..."))

        for idx, pdf_path in enumerate(pdfs, start=1):
            if self._should_stop():
                self._emit(Signal(type=SignalType.WORKER_STOPPED))
                return
            self._wait_if_paused()

            self._emit(Signal.progress(idx, total, f"Analyzing {pdf_path.name}"))
            self._emit(Signal.log(f"Reading {pdf_path.name}"))

            try:
                result = self._analyze_pdf(pdf_path)
                self._emit(Signal(
                    type=SignalType.CERTIFICATE_ANALYZED,
                    payload={
                        "file": str(pdf_path),
                        "filename": pdf_path.name,
                        "detected_name": result.detected_name,
                        "confidence": result.confidence,
                        "method": result.method,
                        "raw_text": result.raw_text_used,
                    },
                ))
                self._emit(Signal.log(
                    f"  → {result.method.upper()}: '{result.detected_name}' "
                    f"({result.confidence:.0f}%)"
                ))
            except Exception as exc:
                logger.error("Failed to analyze %s: %s", pdf_path, exc)
                self._emit(Signal(
                    type=SignalType.CERTIFICATE_FAILED,
                    payload={"filename": pdf_path.name, "error": str(exc)},
                ))

        self._emit(Signal.complete(f"Analysis complete — {total} certificate(s) processed."))

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _analyze_pdf(self, pdf_path: Path) -> NameDetectionResult:
        """Attempt text extraction first, fall back to OCR."""
        # Stage 1: Text extraction via PyMuPDF
        raw_text = self._extract_text_pymupdf(pdf_path)
        if raw_text.strip():
            self._emit(Signal.log(f"  Text extraction successful for {pdf_path.name}"))
            return self._name_detector.detect(raw_text)

        # Stage 2: OCR
        if self._ocr_engine.is_available():
            self._emit(Signal.log(f"  No text found — running OCR on {pdf_path.name}"))
            ocr_result = self._ocr_engine.extract_text_from_pdf_page(pdf_path, 0)
            return self._name_detector.detect(ocr_result.text)

        # Stage 3: Nothing worked
        return NameDetectionResult(method="failed", confidence=0.0)

    @staticmethod
    def _extract_text_pymupdf(pdf_path: Path) -> str:
        try:
            doc = fitz.open(str(pdf_path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text
        except Exception as exc:
            logger.warning("PyMuPDF failed on %s: %s", pdf_path, exc)
            return ""
