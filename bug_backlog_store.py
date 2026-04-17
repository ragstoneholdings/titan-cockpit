"""Windshield Bug backlog (capped) — bug_backlog.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
PATH = ROOT / "bug_backlog.json"

MAX_ITEMS = 50


def _default() -> Dict[str, Any]:
    return {"version": 1, "items": []}


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
    if not isinstance(out.get("items"), list):
        out["items"] = []
    return out


def save_bundle(bundle: Dict[str, Any]) -> None:
    data = _default()
    data.update(bundle)
    data["version"] = max(1, int(data.get("version") or 1))
    items = data.get("items")
    if not isinstance(items, list):
        data["items"] = []
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PATH)


def append_bug(text: str, one_line_reason: str) -> List[Dict[str, Any]]:
    text = str(text or "").strip()
    if not text:
        return items_list()
    b = load_bundle()
    items: List[Dict[str, Any]] = []
    raw = b.get("items")
    if isinstance(raw, list):
        for x in raw:
            if isinstance(x, dict):
                items.append(dict(x))
    items.append({"text": text[:2000], "reason": str(one_line_reason or "")[:500]})
    items = items[-MAX_ITEMS:]
    b["items"] = items
    save_bundle(b)
    return items


def items_list() -> List[Dict[str, Any]]:
    b = load_bundle()
    raw = b.get("items")
    if not isinstance(raw, list):
        return []
    return [dict(x) for x in raw if isinstance(x, dict)]


def clear_items() -> None:
    b = load_bundle()
    b["items"] = []
    save_bundle(b)
