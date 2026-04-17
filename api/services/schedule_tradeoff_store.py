"""Persisted MCQ answers for schedule tradeoff prompts (per calendar day)."""

from __future__ import annotations

import json
from datetime import date
import re
from typing import Any, Dict, List, Set

from integrations.paths import data_root

STORE_PATH = data_root() / "schedule_tradeoff_answers.json"

OVERLAP_KEY_PREFIX = "overlap:"
_OVERLAP_KEY_RE = re.compile(r"^overlap:[a-f0-9]{16,64}$")
OVERLAP_DECISION_VALUES: Set[str] = {"a", "b", "undecided"}

# MCQ ids from schedule_day_signals._build_suggestion_items (per-overlap uses overlap:<id> keys, not listed here)
KNOWN_IDS: Set[str] = {
    "overlap_resolution_hint",
    "work_vs_personal_truth",
    "meeting_tradeoff",
    "no_60m_slide",
    "fragmented_batch",
    "runway_reality",
    "shorten_meeting_tradeoff",
}

ALLOWED_VALUES: Dict[str, Set[str]] = {
    "overlap_resolution_hint": {"acknowledged", "later", "undecided"},
    "work_vs_personal_truth": {"work_screenshot", "personal_api", "both_partially", "undecided"},
    "meeting_tradeoff": {"maintain_all", "decline_low_value", "move_async", "undecided"},
    "no_60m_slide": {"slide_soft_hold", "protect_prep", "undecided"},
    "fragmented_batch": {"merge_blocks", "keep_as_is", "undecided"},
    "runway_reality": {"anchor_accurate", "needs_update", "undecided"},
    "shorten_meeting_tradeoff": {"will_shorten", "no_change", "undecided"},
}


def _default_root() -> Dict[str, Any]:
    return {"version": 1, "by_day": {}}


def load_root() -> Dict[str, Any]:
    if not STORE_PATH.is_file():
        return _default_root()
    try:
        raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_root()
    if not isinstance(raw, dict):
        return _default_root()
    out = _default_root()
    if isinstance(raw.get("by_day"), dict):
        out["by_day"] = dict(raw["by_day"])
    return out


def save_root(data: Dict[str, Any]) -> None:
    root = _default_root()
    if isinstance(data.get("by_day"), dict):
        root["by_day"] = dict(data["by_day"])
    tmp = STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(root, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE_PATH)


def _is_overlap_key(k: str) -> bool:
    return bool(k.startswith(OVERLAP_KEY_PREFIX) and _OVERLAP_KEY_RE.match(k))


def get_answers_for_day(day: date) -> Dict[str, str]:
    root = load_root()
    by_day = root.get("by_day") or {}
    raw = by_day.get(day.isoformat())
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(v, str):
            continue
        if k in KNOWN_IDS and v in ALLOWED_VALUES.get(k, set()):
            out[k] = v
        elif _is_overlap_key(k) and v in OVERLAP_DECISION_VALUES:
            out[k] = v
    return out


def validate_patch(patch: Dict[str, Any]) -> tuple[Dict[str, str], List[str]]:
    """Return (clean_answers, errors)."""
    errors: List[str] = []
    clean: Dict[str, str] = {}
    if not isinstance(patch, dict):
        return {}, ["body must be a JSON object"]
    for k, v in patch.items():
        if k == "version":
            continue
        if not isinstance(v, str):
            errors.append(f"{k}: value must be string")
            continue
        if _is_overlap_key(k):
            if v not in OVERLAP_DECISION_VALUES:
                errors.append(f"{k}: overlap decision must be a, b, or undecided")
            else:
                clean[k] = v
            continue
        if k not in KNOWN_IDS:
            errors.append(f"unknown key: {k}")
            continue
        allowed = ALLOWED_VALUES.get(k, set())
        if v not in allowed:
            errors.append(f"{k}: invalid value {v!r}")
            continue
        clean[k] = v
    return clean, errors


def put_answers_for_day(day: date, patch: Dict[str, Any]) -> Dict[str, str]:
    clean, errors = validate_patch(patch)
    if errors:
        raise ValueError("; ".join(errors))
    root = load_root()
    by_day: Dict[str, Any] = dict(root.get("by_day") or {})
    cur = by_day.get(day.isoformat())
    merged: Dict[str, str] = {}
    if isinstance(cur, dict):
        for kk, vv in cur.items():
            if not isinstance(vv, str):
                continue
            if kk in KNOWN_IDS and vv in ALLOWED_VALUES.get(kk, set()):
                merged[kk] = vv
            elif _is_overlap_key(kk) and vv in OVERLAP_DECISION_VALUES:
                merged[kk] = vv
    merged.update(clean)
    by_day[day.isoformat()] = merged
    root["by_day"] = by_day
    save_root(root)
    return merged
