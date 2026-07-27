"""
app.services.ocr.name_detector
================================
Name Detection Engine.

Extracts the participant name from raw certificate text or PyMuPDF text spans
using multiple strategies in priority order:

  1. Font-size hierarchy — largest prominent text span on the page
  2. Keyword proximity  — scans for known phrases ("Presented To", etc.)
  3. Layout analysis    — longest / most prominent text block
  4. Fallback           — first non-empty valid line

Returns the detected name and a confidence score (0–100).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------------------
# Phrases that typically precede the participant name on a certificate
# ---------------------------------------------------------------------------
NAME_KEYWORDS: list[str] = [
    "presented to",
    "awarded to",
    "this is to certify that",
    "this certificate is proudly presented to",
    "this certificate is presented to",
    "certify that",
    "is hereby awarded to",
    "is awarded to",
    "participant",
    "recipient",
    "winner",
    "is presented to",
    "congratulations to",
]

# Common non-name phrases to ignore when finding max font size
EXCLUDE_HEADER_PHRASES: list[str] = [
    "certificate",
    "participation",
    "appreciation",
    "achievement",
    "completion",
    "excellence",
    "award",
    "presented to",
    "awarded to",
    "this is to certify",
    "congratulations",
    "symposium",
    "workshop",
    "seminar",
    "conference",
]

# Words that should NOT be treated as names
REJECT_PATTERNS: list[str] = [
    r"^(mr|ms|mrs|dr|prof)\.?\s*$",
    r"^\d+$",           # Pure numbers
    r"^[-_/\\|]+$",     # Symbols only
]


@dataclass
class NameDetectionResult:
    detected_name: str = ""
    confidence: float = 0.0    # 0–100
    method: str = ""           # "font_size", "keyword", "layout", "fallback", "failed"
    raw_text_used: str = ""


class NameDetector:
    """
    Determines the participant's name from certificate text or text spans.
    """

    def detect(self, raw_text: str, spans: list[dict[str, Any]] | None = None) -> NameDetectionResult:
        """
        Try all strategies in order and return the first successful result.

        :param raw_text: Full text extracted from a certificate PDF.
        :param spans: Optional list of span dicts with 'text', 'size', 'font', 'bbox'.
        """
        if spans:
            res = self._font_size_strategy(spans)
            if res and res.confidence >= 80.0:
                return res

        if not raw_text or not raw_text.strip():
            return NameDetectionResult(method="failed", confidence=0.0)

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        # Strategy 1: keyword proximity
        result = self._keyword_strategy(lines)
        if result:
            return result

        # Strategy 2: font size fallback if available
        if spans:
            res = self._font_size_strategy(spans)
            if res:
                return res

        # Strategy 3: layout (longest non-keyword line)
        result = self._layout_strategy(lines)
        if result:
            return result

        # Strategy 4: fallback
        return self._fallback_strategy(lines)

    # -----------------------------------------------------------------------
    # Strategies
    # -----------------------------------------------------------------------

    def _font_size_strategy(self, spans: list[dict[str, Any]]) -> NameDetectionResult | None:
        """Find the span with maximum font size that forms a valid name."""
        valid_spans = []
        for s in spans:
            text = s.get("text", "").strip()
            name = self._clean_name(text)
            if not self._is_valid_name(name):
                continue
            lower = name.lower()
            if any(ex in lower for ex in EXCLUDE_HEADER_PHRASES):
                continue
            size = float(s.get("size", 0.0))
            valid_spans.append((name, size, text))

        if not valid_spans:
            return None

        # Sort by font size descending
        valid_spans.sort(key=lambda x: x[1], reverse=True)
        top_name, top_size, raw_text = valid_spans[0]
        score = self._score_name(top_name, method="font_size")

        return NameDetectionResult(
            detected_name=top_name,
            confidence=score,
            method="font_size",
            raw_text_used=raw_text,
        )

    def _keyword_strategy(self, lines: list[str]) -> NameDetectionResult | None:
        text_lower = " ".join(lines).lower()
        for keyword in NAME_KEYWORDS:
            idx = text_lower.find(keyword)
            if idx == -1:
                continue
            char_count = 0
            keyword_line_idx = 0
            for i, line in enumerate(lines):
                char_count += len(line) + 1
                if char_count >= idx:
                    keyword_line_idx = i
                    break
            for candidate_line in lines[keyword_line_idx + 1: keyword_line_idx + 4]:
                name = self._clean_name(candidate_line)
                if name and self._is_valid_name(name):
                    confidence = self._score_name(name, method="keyword")
                    return NameDetectionResult(
                        detected_name=name,
                        confidence=confidence,
                        method="keyword",
                        raw_text_used=candidate_line,
                    )
        return None

    def _layout_strategy(self, lines: list[str]) -> NameDetectionResult | None:
        candidates = [
            (line, len(line))
            for line in lines
            if self._is_valid_name(self._clean_name(line))
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[1], reverse=True)
        name = self._clean_name(candidates[0][0])
        score = self._score_name(name, method="layout")
        return NameDetectionResult(
            detected_name=name,
            confidence=score,
            method="layout",
            raw_text_used=candidates[0][0],
        )

    def _fallback_strategy(self, lines: list[str]) -> NameDetectionResult:
        for line in lines:
            name = self._clean_name(line)
            if name and self._is_valid_name(name):
                return NameDetectionResult(
                    detected_name=name,
                    confidence=50.0,
                    method="fallback",
                    raw_text_used=line,
                )
        return NameDetectionResult(method="failed", confidence=0.0)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _clean_name(text: str) -> str:
        """Normalize whitespace and remove common title prefixes."""
        name = re.sub(r"\s+", " ", text).strip()
        # Strip leading/trailing non-alphanumeric punctuation
        name = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", name).strip()
        return name

    @staticmethod
    def _is_valid_name(name: str) -> bool:
        if not name or len(name) < 3 or len(name) > 80:
            return False
        for pattern in REJECT_PATTERNS:
            if re.fullmatch(pattern, name.lower()):
                return False
        # Must contain at least one letter
        return bool(re.search(r"[a-zA-Z]", name))

    @staticmethod
    def _score_name(name: str, method: str) -> float:
        base_score = 90.0 if method in ("font_size", "keyword") else 75.0
        words = name.split()
        if len(words) >= 2:
            base_score += 5.0
        if name.isupper() or name == name.title():
            base_score += 4.0
        return min(base_score, 99.0)
