"""Commitments 2.0 partner obligations — commitments_store.json."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "commitments_store.json"


def _default() -> Dict[str, Any]:
    return {"version": 1, "partners": []}


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
    ps = out.get("partners")
    if not isinstance(ps, list):
        out["partners"] = []
    return out


def save_bundle(bundle: Dict[str, Any]) -> None:
    data = _default()
    data.update(bundle)
    data["version"] = max(1, int(data.get("version") or 1))
    if not isinstance(data.get("partners"), list):
        data["partners"] = []
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PATH)


def partners() -> List[Dict[str, Any]]:
    b = load_bundle()
    ps = b.get("partners")
    return [dict(x) for x in ps if isinstance(x, dict)] if isinstance(ps, list) else []


def has_overdue_partner() -> bool:
    """Partner obligation past due_date and not marked met."""
    today = date.today()
    for p in partners():
        due = str(p.get("due_date") or "").strip()[:10]
        if len(due) < 10:
            continue
        try:
            d = date.fromisoformat(due)
        except ValueError:
            continue
        if d < today and str(p.get("status") or "").lower() != "met":
            return True
    return False
