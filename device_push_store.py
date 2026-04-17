"""Minimal APNs device token list for Phase 5 (server-initiated push later)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from integrations.paths import data_root

PATH = data_root() / "device_push_tokens.json"
MAX_TOKENS = 50


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


def _write(items: List[Dict[str, Any]]) -> None:
    PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def register_token(*, device_token_hex: str, platform: str = "ios", label: str = "") -> Dict[str, Any]:
    """Upsert by token; returns the stored row."""
    tok = (device_token_hex or "").strip()
    if not tok:
        return {"ok": False, "error": "missing_token"}
    items = _read()
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "device_token_hex": tok[:512],
        "platform": (platform or "ios").strip()[:32],
        "label": (label or "").strip()[:120],
        "registered_at": now,
        "updated_at": now,
    }
    out: List[Dict[str, Any]] = []
    found = False
    for it in items:
        if str(it.get("device_token_hex") or "") == tok:
            it = {**it, **row, "registered_at": it.get("registered_at") or now}
            found = True
        out.append(it)
    if not found:
        out.append(row)
    out = out[-MAX_TOKENS:]
    _write(out)
    return {"ok": True, "stored": row}


def list_tokens(limit: int = 20) -> List[Dict[str, Any]]:
    return _read()[-limit:]
