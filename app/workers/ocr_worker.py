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
import time
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

        repo = None
        if self._db_conn and self._project_id:
            from app.database.repositories.certificate_repo import CertificateRepository
            repo = CertificateRepository(self._db_conn)

        start_time = time.time()
        for idx, pdf_path in enumerate(pdfs, start=1):
            if self._should_stop():
                self._emit(Signal(type=SignalType.WORKER_STOPPED))
                return
            self._wait_if_paused()

            elapsed = time.time() - start_time
            avg_per_item = elapsed / idx if idx > 0 else 0
            remaining_items = total - idx
            eta_sec = int(avg_per_item * remaining_items)

            self._emit(Signal.progress(
                idx, total,
                f"Analyzing {pdf_path.name} ({idx}/{total})",
                elapsed_sec=int(elapsed),
                eta_sec=eta_sec,
            ))
            self._emit(Signal.log(f"Reading {pdf_path.name}"))

            try:
                result, err_type = self._analyze_pdf(pdf_path)
                
                if repo and self._project_id:
                    from app.models.certificate import Certificate, CertificateStatus, ExtractionMethod
                    status = CertificateStatus.READY if (result.confidence >= 50.0 and result.detected_name) else CertificateStatus.NEEDS_REVIEW
                    if err_type == "encrypted":
                        status = CertificateStatus.ENCRYPTED_PDF
                    elif err_type == "corrupt":
                        status = CertificateStatus.CORRUPTED_FILE
                    elif result.method == "failed":
                        status = CertificateStatus.FAILED
                    
                    method_enum = ExtractionMethod.TEXT if result.method in ("text", "font_size", "keyword", "layout") else \
                                  ExtractionMethod.OCR if result.method == "ocr" else ExtractionMethod.FAILED
                    
                    existing = repo.get_by_filename(self._project_id, pdf_path.name)
                    if existing:
                        existing.detected_name = result.detected_name
                        existing.confidence = result.confidence
                        existing.extraction_method = method_enum
                        existing.raw_extracted_text = result.raw_text_used
                        existing.status = status
                        if err_type != "ok":
                            existing.failure_reason = err_type.upper()
                        repo.update(existing)
                    else:
                        cert = Certificate(
                            project_id=self._project_id,
                            original_filename=pdf_path.name,
                            original_file_path=str(pdf_path),
                            detected_name=result.detected_name,
                            confidence=result.confidence,
                            extraction_method=method_enum,
                            raw_extracted_text=result.raw_text_used,
                            status=status,
                            failure_reason=err_type.upper() if err_type != "ok" else "",
                        )
                        repo.insert(cert)

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

    def _analyze_pdf(self, pdf_path: Path) -> tuple[NameDetectionResult, str]:
        """Attempt text extraction first, fall back to OCR."""
        try:
            doc = fitz.open(str(pdf_path))
            if doc.is_encrypted:
                doc.close()
                return NameDetectionResult(method="encrypted", confidence=0.0), "encrypted"
            
            raw_text_lines = []
            spans = []
            for page in doc:
                raw_text_lines.append(page.get_text())
                pdict = page.get_text("dict")
                for block in pdict.get("blocks", []):
                    if "lines" in block:
                        for line in block["lines"]:
                            for s in line.get("spans", []):
                                text = s.get("text", "").strip()
                                if text:
                                    spans.append({
                                        "text": text,
                                        "size": s.get("size", 0.0),
                                        "font": s.get("font", ""),
                                        "bbox": s.get("bbox", (0, 0, 0, 0)),
                                    })
            doc.close()
            raw_text = "\n".join(raw_text_lines)

            if raw_text.strip():
                self._emit(Signal.log(f"  Text extraction successful for {pdf_path.name}"))
                res = self._name_detector.detect(raw_text, spans=spans)
                if not res.method:
                    res.method = "text"
                return res, "ok"
        except fitz.FileDataError:
            return NameDetectionResult(method="corrupt", confidence=0.0), "corrupt"
        except Exception as exc:
            logger.warning("PyMuPDF failed on %s: %s", pdf_path, exc)
            return NameDetectionResult(method="failed", confidence=0.0), "failed"

        # Stage 2: OCR
        if self._ocr_engine.is_available():
            self._emit(Signal.log(f"  No text found — running OCR on {pdf_path.name}"))
            ocr_result = self._ocr_engine.extract_text_from_pdf_page(pdf_path, 0)
            res = self._name_detector.detect(ocr_result.text)
            if not res.method:
                res.method = "ocr"
            return res, "ok"

        # Stage 3: Nothing worked
        return NameDetectionResult(method="failed", confidence=0.0), "failed"
