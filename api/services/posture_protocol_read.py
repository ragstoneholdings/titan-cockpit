"""Read today's posture protocol confirmations from posture_protocol_state.json (Streamlit-compatible)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List, Optional

from integrations.paths import PROTOCOL_STATE_PATH

# Must match command_center_v2.PROTOCOL_ITEMS ids
PROTOCOL_ITEM_IDS: List[str] = ["chin_tucks", "wall_slides", "diaphragmatic_breathing"]


def _normalize_day(d: object) -> Dict[str, bool]:
    if not isinstance(d, dict):
        return {pid: False for pid in PROTOCOL_ITEM_IDS}
    return {pid: bool(d.get(pid, False)) for pid in PROTOCOL_ITEM_IDS}


def load_protocol_history_bundle() -> Dict[str, Dict[str, bool]]:
    if not PROTOCOL_STATE_PATH.is_file():
        return {}
    try:
        raw = json.loads(PROTOCOL_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(raw, dict):
        return {}
    hist = raw.get("history")
    if not isinstance(hist, dict):
        return {}
    out: Dict[str, Dict[str, bool]] = {}
    for dk, dv in hist.items():
        if isinstance(dk, str) and isinstance(dv, dict):
            out[dk[:10]] = _normalize_day(dv)
    return out


def protocol_confirmed_for_day(d: date) -> bool:
    """All three protocol checkboxes True for that calendar day."""
    hist = load_protocol_history_bundle()
    snap = hist.get(d.isoformat(), {})
    return all(bool(snap.get(pid, False)) for pid in PROTOCOL_ITEM_IDS)


def save_protocol_day_items(d: date, items: Dict[str, Any]) -> Dict[str, bool]:
    """Persist posture checkboxes for a calendar day (Streamlit-compatible history)."""
    normalized = {pid: bool(items.get(pid, False)) for pid in PROTOCOL_ITEM_IDS}
    raw: Dict[str, Any] = {}
    if PROTOCOL_STATE_PATH.is_file():
        try:
            raw = json.loads(PROTOCOL_STATE_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    if not isinstance(raw, dict):
        raw = {}
    hist = raw.get("history")
    if not isinstance(hist, dict):
        hist = {}
    hist[d.isoformat()] = normalized
    raw["history"] = hist
    PROTOCOL_STATE_PATH.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    return normalized


def merge_protocol_day_update(d: date, partial: Dict[str, Optional[bool]]) -> Dict[str, bool]:
    """Merge only keys present in partial into today's stored flags, then save."""
    hist = load_protocol_history_bundle()
    cur = {pid: bool(hist.get(d.isoformat(), {}).get(pid, False)) for pid in PROTOCOL_ITEM_IDS}
    for pid in PROTOCOL_ITEM_IDS:
        if pid in partial and partial[pid] is not None:
            cur[pid] = bool(partial[pid])
    return save_protocol_day_items(d, cur)
