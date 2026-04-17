"""Persisted Friday 'Titan Prep' / sartorial calendar audit (Gemini), keyed by target week Monday."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional

from integrations.paths import data_root

_PATH = data_root() / "titan_sartorial_prep.json"


def next_week_monday(today: date) -> date:
    """Monday that starts the calendar week after the current week (Mon–Sun)."""
    delta = (7 - today.weekday()) % 7
    if delta == 0:
        delta = 7
    return today + timedelta(days=delta)


def _load() -> Dict[str, Any]:
    if not _PATH.is_file():
        return {"version": 1, "weeks": {}}
    try:
        raw = json.loads(_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "weeks": {}}
    if not isinstance(raw, dict):
        return {"version": 1, "weeks": {}}
    wk = raw.get("weeks")
    if not isinstance(wk, dict):
        raw["weeks"] = {}
    return raw


def _save(bundle: Dict[str, Any]) -> None:
    tmp = _PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_PATH)


def get_week(week_monday: date) -> Optional[Dict[str, Any]]:
    k = week_monday.isoformat()
    w = _load().get("weeks") or {}
    if not isinstance(w, dict):
        return None
    row = w.get(k)
    return row if isinstance(row, dict) else None


def save_week(
    week_monday: date,
    text: str,
    *,
    model: str = "",
    grounding_event_count: Optional[int] = None,
) -> None:
    bundle = _load()
    weeks = bundle.setdefault("weeks", {})
    if not isinstance(weeks, dict):
        weeks = {}
        bundle["weeks"] = weeks
    row: Dict[str, Any] = {
        "text": str(text or "").strip(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
    }
    if grounding_event_count is not None:
        row["grounding_event_count"] = int(grounding_event_count)
    weeks[week_monday.isoformat()] = row
    _save(bundle)
