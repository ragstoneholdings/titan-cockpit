"""Apply per-overlap user decisions to merged daily_landscape (planning truth only)."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Set

from chief_of_staff.planning import _parse_iso_dt, to_local


def _norm_title(t: str) -> str:
    return " ".join(str(t or "").strip().lower().split())


def stable_overlap_id(ov: Dict[str, Any]) -> str:
    """Stable id for an overlap row (persisted user choice key)."""
    parts = [
        str(ov.get("start_iso") or ""),
        str(ov.get("end_iso") or ""),
        str(ov.get("start_a_iso") or ""),
        str(ov.get("end_a_iso") or ""),
        str(ov.get("start_b_iso") or ""),
        str(ov.get("end_b_iso") or ""),
        _norm_title(str(ov.get("title_a") or "")),
        _norm_title(str(ov.get("title_b") or "")),
        str(ov.get("source_a") or ""),
        str(ov.get("source_b") or ""),
    ]
    raw = "|".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:22]


def overlap_answer_key(overlap_id: str) -> str:
    return f"overlap:{overlap_id}"


def _tag_matches_row(tag: str, row: Dict[str, Any]) -> bool:
    sk = str(row.get("source_kind") or "")
    src = str(row.get("source") or "")
    if tag == "google":
        return src == "google"
    if tag == "personal":
        return src == "personal"
    if tag == "work_screenshot":
        return sk == "work_screenshot"
    return False


def _find_row_index(
    landscape: List[Dict[str, Any]],
    *,
    title: str,
    tag: str,
    start_iso_hint: str,
    tol_sec: int = 300,
) -> Optional[int]:
    hint = _parse_iso_dt(start_iso_hint)
    want_title = _norm_title(title)
    for i, row in enumerate(landscape):
        if not _tag_matches_row(tag, row):
            continue
        if _norm_title(str(row.get("title") or "")) != want_title:
            continue
        rs = _parse_iso_dt(str(row.get("start_iso") or ""))
        if hint is None or rs is None:
            continue
        if abs((to_local(rs) - to_local(hint)).total_seconds()) <= tol_sec:
            return i
    return None


def apply_overlap_decisions_to_landscape(
    landscape: List[Dict[str, Any]],
    overlaps: List[Dict[str, Any]],
    answers: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Remove the non-prioritized row for each overlap where user chose 'a' or 'b'.
    Keys in answers: overlap:<stable_id> -> a | b | undecided
    """
    if not overlaps:
        return list(landscape)

    to_remove: Set[int] = set()
    for ov in overlaps:
        if not isinstance(ov, dict):
            continue
        oid = str(ov.get("id") or stable_overlap_id(ov))
        key = overlap_answer_key(oid)
        dec = (answers.get(key) or answers.get(oid) or "").strip().lower()
        if dec not in ("a", "b"):
            continue
        idx_a = _find_row_index(
            landscape,
            title=str(ov.get("title_a") or ""),
            tag=str(ov.get("source_a") or ""),
            start_iso_hint=str(ov.get("start_a_iso") or ov.get("start_iso") or ""),
        )
        idx_b = _find_row_index(
            landscape,
            title=str(ov.get("title_b") or ""),
            tag=str(ov.get("source_b") or ""),
            start_iso_hint=str(ov.get("start_b_iso") or ov.get("start_iso") or ""),
        )
        if dec == "a" and idx_b is not None:
            to_remove.add(idx_b)
        elif dec == "b" and idx_a is not None:
            to_remove.add(idx_a)

    if not to_remove:
        return list(landscape)
    return [row for i, row in enumerate(landscape) if i not in to_remove]
