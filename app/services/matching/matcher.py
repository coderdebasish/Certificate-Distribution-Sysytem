"""
app.services.matching.matcher
==============================
Certificate-to-participant fuzzy name matching engine.

Uses rapidfuzz for high-performance fuzzy string matching.
Applies multi-pass matching (Exact -> High -> Medium threshold) to prevent false-positive assignments
and domino-effect mismatches.
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
    method: str = "fuzzy"                # "exact", "fuzzy", "manual", "unmatched"


class NameMatcher:
    """
    Matches participant names against certificate filenames cleanly.
    Enforces strict multi-pass priority:
    Pass 1: 100% Exact matches
    Pass 2: High confidence (>= 90%)
    Pass 3: Medium confidence (>= 75%)
    Remaining: Left Unmatched (score < 75%)
    """

    HIGH_THRESHOLD: float = 90.0
    MEDIUM_THRESHOLD: float = 75.0

    def match_all(
        self,
        participant_names: dict[int, str],     # {participant_id: name}
        certificate_names: dict[int, str],     # {certificate_id: filename_stem}
    ) -> list[MatchResult]:
        results_map: dict[int, MatchResult] = {}
        used_cert_ids: set[int] = set()

        cert_id_to_stem = dict(certificate_names)

        # Build normalized cert lookup: norm_stem -> cert_id
        norm_certs: dict[str, int] = {}
        for cid, stem in certificate_names.items():
            norm_s = self._normalize(stem)
            if norm_s:
                norm_certs[norm_s] = cid

        # --- PASS 1: 100% Exact matches ---
        for pid, p_name in participant_names.items():
            norm_p = self._normalize(p_name)
            if norm_p in norm_certs:
                cid = norm_certs[norm_p]
                if cid not in used_cert_ids:
                    used_cert_ids.add(cid)
                    results_map[pid] = MatchResult(
                        participant_id=pid,
                        certificate_id=cid,
                        certificate_filename=cert_id_to_stem[cid],
                        score=100.0,
                        confidence=MatchConfidence.EXACT,
                        method="exact",
                    )

        # --- PASS 2: High confidence fuzzy matches (score >= 90.0) ---
        for pid, p_name in participant_names.items():
            if pid in results_map:
                continue
            norm_p = self._normalize(p_name)
            if not norm_p:
                continue

            available = {cid: self._normalize(stem) for cid, stem in certificate_names.items() if cid not in used_cert_ids}
            if not available:
                break

            best_cid = None
            best_score = 0.0
            for cid, norm_stem in available.items():
                score = float(fuzz.token_sort_ratio(norm_p, norm_stem))
                if score > best_score:
                    best_score = score
                    best_cid = cid

            if best_score >= self.HIGH_THRESHOLD and best_cid is not None:
                used_cert_ids.add(best_cid)
                results_map[pid] = MatchResult(
                    participant_id=pid,
                    certificate_id=best_cid,
                    certificate_filename=cert_id_to_stem[best_cid],
                    score=best_score,
                    confidence=MatchConfidence.HIGH,
                    method="fuzzy",
                )

        # --- PASS 3: Medium confidence fuzzy matches (75.0 <= score < 90.0) ---
        for pid, p_name in participant_names.items():
            if pid in results_map:
                continue
            norm_p = self._normalize(p_name)
            if not norm_p:
                continue

            available = {cid: self._normalize(stem) for cid, stem in certificate_names.items() if cid not in used_cert_ids}
            if not available:
                break

            best_cid = None
            best_score = 0.0
            for cid, norm_stem in available.items():
                score = float(fuzz.token_sort_ratio(norm_p, norm_stem))
                if score > best_score:
                    best_score = score
                    best_cid = cid

            if best_score >= self.MEDIUM_THRESHOLD and best_cid is not None:
                used_cert_ids.add(best_cid)
                results_map[pid] = MatchResult(
                    participant_id=pid,
                    certificate_id=best_cid,
                    certificate_filename=cert_id_to_stem[best_cid],
                    score=best_score,
                    confidence=MatchConfidence.MEDIUM,
                    method="fuzzy",
                )

        # --- PASS 4: Mark remaining participants as UNMATCHED ---
        for pid, p_name in participant_names.items():
            if pid not in results_map:
                results_map[pid] = MatchResult(
                    participant_id=pid,
                    certificate_id=0,
                    certificate_filename="",
                    score=0.0,
                    confidence=MatchConfidence.NONE,
                    method="unmatched",
                )

        return [results_map[pid] for pid in participant_names.keys()]

    def match_one(self, participant_name: str, certificate_stems: list[str]) -> tuple[str, float]:
        """Find best matching certificate stem for a single participant name."""
        if not certificate_stems:
            return "", 0.0
        norm_name = self._normalize(participant_name)
        norm_stems = [self._normalize(s) for s in certificate_stems]
        result = process.extractOne(norm_name, norm_stems, scorer=fuzz.token_sort_ratio)
        if result is None:
            return "", 0.0
        best_norm, score, idx = result
        if float(score) < self.MEDIUM_THRESHOLD:
            return "", 0.0
        return certificate_stems[idx], float(score)

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text)
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
