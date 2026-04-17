"""Append-only janitor graveyard (tasks closed by Titan Janitor)."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from integrations.paths import data_root

GRAVEYARD_PATH = data_root() / "todoist_graveyard.json"


def _load() -> Dict[str, Any]:
    if not GRAVEYARD_PATH.is_file():
        return {"version": 1, "entries": []}
    try:
        raw = json.loads(GRAVEYARD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "entries": []}
    if not isinstance(raw, dict):
        return {"version": 1, "entries": []}
    raw.setdefault("version", 1)
    raw.setdefault("entries", [])
    if not isinstance(raw["entries"], list):
        raw["entries"] = []
    return raw


def append_entries(items: List[Dict[str, Any]], *, source: str = "janitor") -> int:
    """Append closed-task records; returns number appended."""
    if not items:
        return 0
    bundle = _load()
    entries: List[Dict[str, Any]] = list(bundle.get("entries") or [])
    n = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        row = {
            "task_id": str(it.get("task_id") or ""),
            "title": str(it.get("title") or ""),
            "closed_at": str(it.get("closed_at") or ""),
            "source": source,
        }
        if row["task_id"]:
            entries.append(row)
            n += 1
    bundle["entries"] = entries
    tmp = GRAVEYARD_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(GRAVEYARD_PATH)
    return n


def list_entries(limit: int = 200) -> List[Dict[str, Any]]:
    bundle = _load()
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        return []
    out = [x for x in entries if isinstance(x, dict)]
    if limit > 0:
        out = out[-limit:]
    return list(reversed(out))
