"""Persisted dismissals for the Morning Brief card (per recon day)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict, List

from integrations.paths import data_root

_STORE_PATH = data_root() / "morning_brief_state.json"


def _default_bundle() -> Dict[str, Any]:
    return {"version": 1, "dismissed_days": []}


def _load() -> Dict[str, Any]:
    if not _STORE_PATH.is_file():
        return _default_bundle()
    try:
        raw = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_bundle()
    if not isinstance(raw, dict):
        return _default_bundle()
    raw.setdefault("version", 1)
    dd = raw.get("dismissed_days")
    if not isinstance(dd, list):
        raw["dismissed_days"] = []
    return raw


def _save(bundle: Dict[str, Any]) -> None:
    bundle = dict(bundle)
    bundle.setdefault("version", 1)
    dd = bundle.get("dismissed_days")
    if not isinstance(dd, list):
        bundle["dismissed_days"] = []
    else:
        bundle["dismissed_days"] = sorted({str(x).strip()[:10] for x in dd if str(x).strip()})
    tmp = _STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_STORE_PATH)


def is_morning_brief_dismissed(day: date) -> bool:
    key = day.isoformat()
    dd: List[Any] = _load().get("dismissed_days") or []
    return key in {str(x).strip()[:10] for x in dd if str(x).strip()}


def dismiss_morning_brief(day: date) -> None:
    bundle = _load()
    days: List[str] = [str(x).strip()[:10] for x in (bundle.get("dismissed_days") or []) if str(x).strip()]
    key = day.isoformat()
    if key not in days:
        days.append(key)
    bundle["dismissed_days"] = days
    _save(bundle)
