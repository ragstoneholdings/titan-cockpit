"""Vanguard health, inbox gate, evening ops, favor strike — vanguard_health.json."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "vanguard_health.json"


def _default() -> Dict[str, Any]:
    return {
        "version": 1,
        "days": {},
        "targets": {
            "body_fat_percent_target": 13.0,
            "protein_g_per_lb_target": 1.2,
            "bench_press_lb_target": 205,
            "sleep_hours_target": 7.5,
            "macro_alignment_percent_target": 97.0,
        },
        "current": {
            "body_fat_percent": None,
            "protein_g_per_lb": None,
            "bench_press_lb": None,
            "macro_alignment_percent": None,
        },
        "executive_time_value_usd_per_hour": None,
    }


def load_bundle() -> Dict[str, Any]:
    if not PATH.is_file():
        return _default()
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default()
    if not isinstance(raw, dict):
        return _default()
    out = _default()
    out.update(raw)
    out.setdefault("version", 1)
    out.setdefault("days", {})
    out.setdefault("targets", _default()["targets"])
    out.setdefault("current", _default()["current"])
    if not isinstance(out["days"], dict):
        out["days"] = {}
    if not isinstance(out["targets"], dict):
        out["targets"] = dict(_default()["targets"])
    if not isinstance(out["current"], dict):
        out["current"] = dict(_default()["current"])
    return out


def save_bundle(bundle: Dict[str, Any]) -> None:
    data = _default()
    data.update(bundle)
    data["version"] = max(1, int(data.get("version") or 1))
    if not isinstance(data.get("days"), dict):
        data["days"] = {}
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PATH)


def get_day(d: date) -> Dict[str, Any]:
    b = load_bundle()
    days = b.get("days") if isinstance(b.get("days"), dict) else {}
    k = d.isoformat()
    row = days.get(k)
    if not isinstance(row, dict):
        return {}
    return dict(row)


def put_day_merge(d: date, patch: Dict[str, Any]) -> Dict[str, Any]:
    b = load_bundle()
    days = b.setdefault("days", {})
    if not isinstance(days, dict):
        days = {}
        b["days"] = days
    k = d.isoformat()
    cur = dict(days[k]) if isinstance(days.get(k), dict) else {}
    cur.update(patch)
    days[k] = cur
    save_bundle(b)
    return cur


def sleep_hours_for_prior_day(*, recon_day: date) -> Optional[float]:
    """Yesterday relative to recon_day for air-gap advisory."""
    y = recon_day - timedelta(days=1)
    row = get_day(y)
    v = row.get("sleep_hours")
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def favor_strike_streak_7d(*, ending: date) -> int:
    """Count trailing days (ending inclusive) with zero_utility_labor True."""
    b = load_bundle()
    days = b.get("days") if isinstance(b.get("days"), dict) else {}
    streak = 0
    for i in range(7):
        d = ending - timedelta(days=i)
        k = d.isoformat()
        row = days.get(k)
        if not isinstance(row, dict):
            break
        if bool(row.get("zero_utility_labor")):
            streak += 1
        else:
            break
    return streak


def rolling_utility_free_days_7d(*, ending: date) -> int:
    """How many of the last 7 calendar days had zero_utility_labor set."""
    b = load_bundle()
    days = b.get("days") if isinstance(b.get("days"), dict) else {}
    n = 0
    for i in range(7):
        d = ending - timedelta(days=i)
        row = days.get(d.isoformat())
        if isinstance(row, dict) and bool(row.get("zero_utility_labor")):
            n += 1
    return n
