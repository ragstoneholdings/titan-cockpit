"""Append-only Zapier / integration trace for Firewall audit (zapier_inbound_log.json)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from integrations.paths import data_root

PATH = data_root() / "zapier_inbound_log.json"
MAX_ENTRIES = 100


def _read() -> List[Dict[str, Any]]:
    if not PATH.is_file():
        return []
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def append_event(payload: Dict[str, Any]) -> None:
    items = _read()
    entry = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "payload": dict(payload) if isinstance(payload, dict) else {"raw": payload},
    }
    items.append(entry)
    items = items[-MAX_ENTRIES:]
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PATH)


def list_recent(limit: int = 20) -> List[Dict[str, Any]]:
    items = _read()
    return items[-limit:]
