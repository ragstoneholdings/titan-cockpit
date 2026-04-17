"""Lightweight Physical Integrity summary for the cockpit sidebar (editable JSON)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Dict

from integrations.paths import data_root

INTEGRITY_STATS_PATH = data_root() / "integrity_stats.json"


def default_bundle() -> Dict[str, Any]:
    return {
        "version": 1,
        "notes": "",
        "posture_sessions_7d": [False] * 7,
        "neck_last_dates": [],
        "last_neck_cm": None,
        "updated_at": "",
    }


def load_bundle() -> Dict[str, Any]:
    if not INTEGRITY_STATS_PATH.is_file():
        return default_bundle()
    try:
        raw = json.loads(INTEGRITY_STATS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_bundle()
    if not isinstance(raw, dict):
        return default_bundle()
    out = default_bundle()
    for k in out:
        if k in raw:
            out[k] = raw[k]
    return out


def save_bundle(data: Dict[str, Any]) -> None:
    payload = default_bundle()
    for k in payload:
        if k in data:
            payload[k] = data[k]
    payload["updated_at"] = date.today().isoformat()
    tmp = INTEGRITY_STATS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INTEGRITY_STATS_PATH)
