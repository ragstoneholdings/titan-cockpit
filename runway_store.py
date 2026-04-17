"""Persisted manual Hard Anchor overrides by calendar date (local)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent
RUNWAY_OVERRIDES_PATH = ROOT / "runway_overrides.json"


@dataclass(frozen=True)
class RunwayDayOverride:
    start_iso: str
    title: str
    source: str  # "google" | "personal"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_runway_bundle() -> Dict[str, Any]:
    if not RUNWAY_OVERRIDES_PATH.is_file():
        return {"version": 1, "by_date": {}}
    try:
        raw = json.loads(RUNWAY_OVERRIDES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "by_date": {}}
    if not isinstance(raw, dict):
        return {"version": 1, "by_date": {}}
    by_date = raw.get("by_date")
    if not isinstance(by_date, dict):
        by_date = {}
    return {"version": int(raw.get("version") or 1), "by_date": by_date}


def load_runway_override_for_day(day: date) -> Optional[RunwayDayOverride]:
    bundle = load_runway_bundle()
    key = day.isoformat()
    entry = bundle["by_date"].get(key)
    if not isinstance(entry, dict):
        return None
    start_iso = str(entry.get("start_iso") or "").strip()
    title = str(entry.get("title") or "").strip()
    source = str(entry.get("source") or "").strip().lower()
    if not start_iso or not title or source not in ("google", "personal"):
        return None
    return RunwayDayOverride(start_iso=start_iso, title=title, source=source)


def save_runway_override_for_day(day: date, o: RunwayDayOverride) -> None:
    bundle = load_runway_bundle()
    by_date = dict(bundle["by_date"])
    by_date[day.isoformat()] = {
        "start_iso": o.start_iso,
        "title": o.title,
        "source": o.source,
    }
    _atomic_write_json(RUNWAY_OVERRIDES_PATH, {"version": 1, "by_date": by_date})


def clear_runway_override_for_day(day: date) -> None:
    bundle = load_runway_bundle()
    by_date = dict(bundle["by_date"])
    by_date.pop(day.isoformat(), None)
    _atomic_write_json(RUNWAY_OVERRIDES_PATH, {"version": 1, "by_date": by_date})
