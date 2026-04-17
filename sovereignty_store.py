"""Manual and derived sovereignty inputs for Vanguard Cockpit KPIs (sovereignty_inputs.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "sovereignty_inputs.json"


def _default() -> Dict[str, Any]:
    return {
        "version": 1,
        "firefighting_incidents_week": None,
        "delegations_not_pushed_week": None,
        "zapier_failure_events_week": None,
        "operational_authority_note": "",
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
    return out


def save_bundle(bundle: Dict[str, Any]) -> None:
    data = dict(_default())
    data.update(bundle)
    data["version"] = max(1, int(data.get("version") or 1))
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PATH)
