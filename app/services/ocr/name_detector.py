"""
app.services.ocr.name_detector
================================
Name Detection Engine.

Extracts the participant name from raw certificate text using multiple
strategies in priority order:

  1. Keyword proximity  — scans for known phrases ("Presented To", etc.)
  2. Layout analysis    — largest / most prominent text block
  3. Fallback           — first non-empty line

Returns the detected name and a confidence score (0–100).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


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

# Words that should NOT be treated as names even if found near a keyword
REJECT_PATTERNS: list[str] = [
    r"^(mr|ms|mrs|dr|prof)\.?\s*$",
    r"^\d+$",           # Pure numbers
    r"^[-_/\\|]+$",     # Symbols only
]


@dataclass
class NameDetectionResult:
    detected_name: str = ""
    confidence: float = 0.0    # 0–100
    method: str = ""           # "keyword", "layout", "fallback", "failed"
    raw_text_used: str = ""


class NameDetector:
    """
    Determines the participant's name from certificate text.

    Usage::

        detector = NameDetector()
        result = detector.detect(raw_text="Certificate of Participation\n\nDebasish Mohanty\n\nFor...")
    """

    def detect(self, raw_text: str) -> NameDetectionResult:
        """
        Try all strategies in order and return the first successful result.

        :param raw_text: Full text extracted from a certificate PDF.
        """
        if not raw_text or not raw_text.strip():
            return NameDetectionResult(method="failed", confidence=0.0)

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        # Strategy 1: keyword proximity
        result = self._keyword_strategy(lines)
        if result:
            return result

        # Strategy 2: layout (longest non-keyword line)
        result = self._layout_strategy(lines)
        if result:
            return result

        # Strategy 3: fallback
        return self._fallback_strategy(lines)

    # -----------------------------------------------------------------------
    # Strategies
    # -----------------------------------------------------------------------

    def _keyword_strategy(self, lines: list[str]) -> NameDetectionResult | None:
        text_lower = " ".join(lines).lower()
        for keyword in NAME_KEYWORDS:
            idx = text_lower.find(keyword)
            if idx == -1:
                continue
            # Find the line that contains the keyword
            char_count = 0
            keyword_line_idx = 0
            for i, line in enumerate(lines):
                char_count += len(line) + 1
                if char_count >= idx:
                    keyword_line_idx = i
                    break
            # The name is usually on the next non-empty line after the keyword
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
        # Heuristic: the name is often the longest line that looks like a name
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
            if name:
                return NameDetectionResult(
                    detected_name=name,
                    confidence=30.0,
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
        # Strip leading/trailing punctuation
        name = re.sub(r"^[^a-zA-Z]+|[^a-zA-Z]+$", "", name).strip()
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
        """
        Assign a confidence score based on name characteristics.
        Scores are deliberately conservative.
        """
        score = 85.0 if method == "keyword" else 60.0
        words = name.split()
        # Full names (2+ words) are more reliable
        if len(words) >= 2:
            score += 5.0
        # Title-case names look more like real names
        if name == name.title():
            score += 5.0
        return min(score, 99.0)
