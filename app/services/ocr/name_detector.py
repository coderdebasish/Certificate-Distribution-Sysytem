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
# Phrases that typically precede the participant name on a certificate
NAME_KEYWORDS: list[str] = [
    "this certificate is proudly presented to",
    "this certificate is presented to",
    "is proudly presented to",
    "proudly presented to",
    "this is to certify that",
    "is hereby awarded to",
    "is awarded to",
    "presented to",
    "awarded to",
    "certify that",
    "is presented to",
    "congratulations to",
]

# Words that indicate a descriptive sentence or header, NOT a person's name
SENTENCE_WORDS: set[str] = {
    "towards", "building", "future", "through", "powered", "design", "recognition",
    "creativity", "innovation", "commitment", "participating", "participated",
    "participates", "organized", "jointly", "official", "results", "details",
    "awarded", "presented", "certify", "hereby", "department", "science",
    "humanities", "institute", "engineering", "management", "university",
    "council", "society", "centre", "center", "laboratory", "college",
    "school", "team", "appreciation", "effort", "enthusiasm", "initiative",
    "meaningful", "successful", "congratulations", "warm", "regards",
    "challenge", "certificate", "participation", "achievement", "completion",
    "excellence", "award", "symposium", "workshop", "seminar", "conference",
    "convenor", "president", "head", "july", "august", "september", "october",
    "november", "december", "january", "february", "march", "april", "may", "june",
    "is", "are", "was", "were", "been", "have", "has", "had", "with", "from",
    "for", "and", "the", "this", "that", "these", "those", "which"
}

# Common non-name phrases to ignore when finding max font size or candidate names
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
    "future x",
    "design challenge",
    "future x design",
    "challenge",
    "institute",
    "university",
    "management",
    "engineering",
    "technology",
    "department",
    "council",
    "society",
    "center",
    "laboratory",
    "science",
    "humanities",
    "iic",
    "iem",
    "uem",
    "iifr",
    "lab",
    "innovacion",
    "organized",
    "jointly",
    "convenor",
    "president",
    "head",
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
    method: str = ""           # "roster", "font_size", "keyword", "layout", "fallback", "failed"
    raw_text_used: str = ""


class NameDetector:
    """
    Determines the participant's name from certificate text or text spans.
    """

    def detect(
        self,
        raw_text: str,
        spans: list[dict[str, Any]] | None = None,
        event_name: str = "",
        participant_names: list[str] | set[str] | None = None,
    ) -> NameDetectionResult:
        """
        Try strategies in accurate priority order: Roster Match -> Keyword Proximity -> Font Size -> Layout -> Fallback.

        :param raw_text: Full text extracted from a certificate PDF.
        :param spans: Optional list of span dicts with 'text', 'size', 'font', 'bbox'.
        :param event_name: Optional event name to exclude.
        :param participant_names: Optional imported participant roster to match against.
        """
        if not raw_text or not raw_text.strip():
            if spans:
                raw_text = "\n".join(s.get("text", "") for s in spans)
            else:
                return NameDetectionResult(method="failed", confidence=0.0)

        # Strategy 0: Imported Participant Roster Match (100% Accuracy)
        if participant_names:
            text_lower = raw_text.lower()
            for p_name in participant_names:
                p_name_clean = p_name.strip()
                if p_name_clean and len(p_name_clean) >= 3 and p_name_clean.lower() in text_lower:
                    return NameDetectionResult(
                        detected_name=p_name_clean,
                        confidence=100.0,
                        method="roster",
                        raw_text_used=p_name_clean,
                    )

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        # Strategy 1: Keyword Proximity FIRST
        result = self._keyword_strategy(lines, event_name=event_name)
        if result:
            return result

        # Strategy 2: Font Size Strategy
        if spans:
            res = self._font_size_strategy(spans, event_name=event_name)
            if res:
                return res

        # Strategy 3: Layout
        result = self._layout_strategy(lines, event_name=event_name)
        if result:
            return result

        # Strategy 4: Fallback
        return self._fallback_strategy(lines, event_name=event_name)

    # -----------------------------------------------------------------------
    # Strategies
    # -----------------------------------------------------------------------

    def _font_size_strategy(self, spans: list[dict[str, Any]], event_name: str = "") -> NameDetectionResult | None:
        """Find the span with maximum font size that forms a valid name."""
        valid_spans = []
        for s in spans:
            text = s.get("text", "").strip()
            name = self._clean_name(text)
            if not self._is_valid_name(name, event_name=event_name):
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

    def _keyword_strategy(self, lines: list[str], event_name: str = "") -> NameDetectionResult | None:
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
                if name and self._is_valid_name(name, event_name=event_name):
                    confidence = self._score_name(name, method="keyword")
                    return NameDetectionResult(
                        detected_name=name,
                        confidence=confidence,
                        method="keyword",
                        raw_text_used=candidate_line,
                    )
        return None

    def _layout_strategy(self, lines: list[str], event_name: str = "") -> NameDetectionResult | None:
        candidates = [
            (line, len(line))
            for line in lines
            if self._is_valid_name(self._clean_name(line), event_name=event_name)
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

    def _fallback_strategy(self, lines: list[str], event_name: str = "") -> NameDetectionResult:
        for line in lines:
            name = self._clean_name(line)
            if name and self._is_valid_name(name, event_name=event_name):
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
    def _is_valid_name(name: str, event_name: str = "") -> bool:
        if not name or len(name) < 3 or len(name) > 80:
            return False
        lower = name.lower()
        if any(ex in lower for ex in EXCLUDE_HEADER_PHRASES):
            return False
        if event_name:
            for w in event_name.lower().split():
                if len(w) > 3 and w in lower:
                    return False
        for pattern in REJECT_PATTERNS:
            if re.fullmatch(pattern, lower):
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
