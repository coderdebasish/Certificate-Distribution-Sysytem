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
    "this certificate is proudly presented to",
    "this certificate is presented to",
    "this certificate is awarded to",
    "this certificate is hereby awarded to",
    "this certificate is proudly awarded to",
    "is proudly presented to",
    "proudly presented to",
    "is presented to",
    "presented to",
    "awarded to",
    "this is to certify that",
    "is hereby awarded to",
    "certify that",
    "congratulations to",
    "certificate of participation",
    "certificate of appreciation",
    "in recognition of",
    "participant",
    "recipient",
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
    "certificate of",
    "this certificate",
    "certificate awarded",
    "certificate presented",
]

# Words that should NOT be treated as names
REJECT_PATTERNS: list[str] = [
    r"^(mr|ms|mrs|dr|prof)\.?\s*$",
    r"^\d+$",
    r"^[-_/\\|]+$",
    r"^[a-z]+\s+(to|for|in|on|of|and|with|from)\s*$",
    r"^(certificate|participation|appreciation|completion|achievement|award|winner|runner|up|recognition|event|workshop|seminar|conference|symposium|hackathon|ideathon|training|volunteer|organizing|committee)\s*$",
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
        for index, line in enumerate(lines):
            lower_line = line.lower()
            for keyword in NAME_KEYWORDS:
                keyword_lower = keyword.lower()
                if keyword_lower not in lower_line:
                    continue

                this_line_match = re.search(rf"{re.escape(keyword_lower)}\s*[:\-]?\s*([A-Z][A-Za-z'.,\- ]{{2,80}})", line, re.IGNORECASE)
                if this_line_match:
                    name = self._clean_name(this_line_match.group(1))
                    if name and self._is_valid_name(name, event_name=event_name):
                        return NameDetectionResult(
                            detected_name=name,
                            confidence=self._score_name(name, method="keyword"),
                            method="keyword",
                            raw_text_used=line,
                        )

                candidates: list[tuple[str, float]] = []
                for offset in range(1, 8):
                    target_index = index + offset
                    if target_index >= len(lines):
                        break
                    candidate_line = lines[target_index]
                    name = self._clean_name(candidate_line)
                    if name and self._is_valid_name(name, event_name=event_name):
                        score = self._score_name(name, method="keyword") + max(0.0, 8.0 - offset * 0.8)
                        candidates.append((name, score))
                if candidates:
                    best_name, best_score = max(candidates, key=lambda item: item[1])
                    return NameDetectionResult(
                        detected_name=best_name,
                        confidence=min(best_score, 99.0),
                        method="keyword",
                        raw_text_used=best_name,
                    )
        return None

    def _layout_strategy(self, lines: list[str], event_name: str = "") -> NameDetectionResult | None:
        candidates = []
        for line in lines:
            name = self._clean_name(line)
            if not self._is_valid_name(name, event_name=event_name):
                continue
            word_count = len(name.split())
            if word_count == 1:
                continue
            candidates.append((name, len(name)))
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
        name = name.replace("•", " ")
        name = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", name).strip()
        name = re.sub(r"\s*[:\-–—]\s*", " ", name)
        name = re.sub(r"\s+", " ", name).strip()
        return name

    @staticmethod
    def _is_valid_name(name: str, event_name: str = "") -> bool:
        if not name or len(name) < 2 or len(name) > 80:
            return False
        lower = name.lower()
        if any(ex in lower for ex in EXCLUDE_HEADER_PHRASES):
            return False
        if event_name:
            for w in event_name.lower().split():
                if len(w) > 3 and w in lower:
                    return False
        if len(name.split()) > 6:
            return False
        for pattern in REJECT_PATTERNS:
            if re.fullmatch(pattern, lower):
                return False
        if lower.startswith(("certificate", "participation", "appreciation", "award", "recognition", "winner", "runner", "workshop", "seminar", "conference", "symposium", "hackathon", "ideathon")):
            return False
        if "certificate" in lower or "participation" in lower or "workshop" in lower or "seminar" in lower or "conference" in lower:
            return False
        return bool(re.search(r"[a-zA-Z]", name))

    @staticmethod
    def _score_name(name: str, method: str) -> float:
        base_score = 92.0 if method in ("font_size", "keyword") else 75.0
        words = name.split()
        if 2 <= len(words) <= 4:
            base_score += 5.0
        if len(words) == 1:
            base_score -= 5.0
        if name.isupper() or name == name.title():
            base_score += 4.0
        return min(max(base_score, 0.0), 99.0)
