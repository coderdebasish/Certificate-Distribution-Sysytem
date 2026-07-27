"""
app.services.matching.matcher
==============================
Certificate-to-participant fuzzy name matching engine.

Uses rapidfuzz for high-performance fuzzy string matching.
Applies multiple normalization steps before comparing to handle
case differences, extra spaces, Unicode variants, etc.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz, process


class MatchConfidence(str, Enum):
    EXACT = "exact"       # 100
    HIGH = "high"         # 90–99
    MEDIUM = "medium"     # 75–89
    LOW = "low"           # < 75
    MANUAL = "manual"     # User-assigned
    NONE = "none"


@dataclass
class MatchResult:
    participant_id: int
    certificate_id: int
    certificate_filename: str
    score: float                         # 0–100
    confidence: MatchConfidence
    method: str = "fuzzy"                # "exact", "fuzzy", "manual"


class NameMatcher:
    """
    Matches participant names against certificate filenames.

    Usage::

        matcher = NameMatcher()
        results = matcher.match_all(participants, certificates)
    """

    HIGH_THRESHOLD: float = 90.0
    MEDIUM_THRESHOLD: float = 75.0

    def match_all(
        self,
        participant_names: dict[int, str],     # {participant_id: name}
        certificate_names: dict[int, str],     # {certificate_id: filename_stem}
    ) -> list[MatchResult]:
        """
        Auto-match every participant to the best certificate.

        One certificate can only be assigned to one participant.
        Assignments with score below MEDIUM_THRESHOLD are returned as LOW
        confidence and flagged for manual review.

        :param participant_names:  Mapping of participant IDs to their full names.
        :param certificate_names:  Mapping of certificate IDs to their filename stems
                                   (filename without .pdf extension).
        :returns: List of MatchResult, one per participant.
        """
        results: list[MatchResult] = []
        used_cert_ids: set[int] = set()

        # Normalised certificate lookup: normalised_stem → cert_id
        norm_certs: dict[str, int] = {
            self._normalize(stem): cert_id
            for cert_id, stem in certificate_names.items()
        }
        cert_id_to_stem: dict[int, str] = dict(certificate_names)

        for participant_id, participant_name in participant_names.items():
            norm_name = self._normalize(participant_name)

            # --- Exact match first ---
            if norm_name in norm_certs:
                cert_id = norm_certs[norm_name]
                if cert_id not in used_cert_ids:
                    used_cert_ids.add(cert_id)
                    results.append(MatchResult(
                        participant_id=participant_id,
                        certificate_id=cert_id,
                        certificate_filename=cert_id_to_stem[cert_id],
                        score=100.0,
                        confidence=MatchConfidence.EXACT,
                        method="exact",
                    ))
                    continue

            # --- Fuzzy match ---
            available = {
                cid: stem for cid, stem in certificate_names.items()
                if cid not in used_cert_ids
            }
            if not available:
                break

            norm_available = {self._normalize(stem): cid for cid, stem in available.items()}
            best = process.extractOne(
                norm_name,
                list(norm_available.keys()),
                scorer=fuzz.token_sort_ratio,
            )

            if best is None:
                results.append(MatchResult(
                    participant_id=participant_id,
                    certificate_id=0,
                    certificate_filename="",
                    score=0.0,
                    confidence=MatchConfidence.NONE,
                ))
                continue

            best_norm_stem, score, _ = best
            cert_id = norm_available[best_norm_stem]
            confidence = self._score_to_confidence(score)
            used_cert_ids.add(cert_id)
            results.append(MatchResult(
                participant_id=participant_id,
                certificate_id=cert_id,
                certificate_filename=cert_id_to_stem[cert_id],
                score=float(score),
                confidence=confidence,
                method="fuzzy",
            ))

        return results

    def match_one(self, participant_name: str, certificate_stems: list[str]) -> tuple[str, float]:
        """
        Find the best matching certificate stem for a single participant name.

        :returns: (best_stem, score) tuple. stem is "" if no candidates.
        """
        if not certificate_stems:
            return "", 0.0
        norm_name = self._normalize(participant_name)
        norm_stems = [self._normalize(s) for s in certificate_stems]
        result = process.extractOne(norm_name, norm_stems, scorer=fuzz.token_sort_ratio)
        if result is None:
            return "", 0.0
        best_norm, score, idx = result
        return certificate_stems[idx], float(score)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize a name for comparison:
        - Unicode NFC → NFD → ASCII transliteration
        - Lowercase
        - Collapse whitespace
        - Strip leading/trailing spaces
        """
        # Unicode normalization
        normalized = unicodedata.normalize("NFKD", text)
        # Remove combining characters (accents)
        ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
        return " ".join(ascii_text.lower().split())

    def _score_to_confidence(self, score: float) -> MatchConfidence:
        if score >= 100:
            return MatchConfidence.EXACT
        if score >= self.HIGH_THRESHOLD:
            return MatchConfidence.HIGH
        if score >= self.MEDIUM_THRESHOLD:
            return MatchConfidence.MEDIUM
        return MatchConfidence.LOW
