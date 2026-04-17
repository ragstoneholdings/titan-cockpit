"""Optional Zapier inbound idempotency (``X-Idempotency-Key`` / ``Idempotency-Key``)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Set

from integrations.paths import data_root

PATH = data_root() / "zapier_idempotency_keys.json"
MAX_KEYS = 4000
TTL_SEC = 86400 * 2  # 48h


def _read() -> Dict[str, Any]:
    if not PATH.is_file():
        return {"keys": {}}
    try:
        raw = json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"keys": {}}
    if isinstance(raw, dict) and isinstance(raw.get("keys"), dict):
        return raw
    return {"keys": {}}


def _write(obj: Dict[str, Any]) -> None:
    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PATH)


def _prune_keys(keys_map: Dict[str, Any]) -> Dict[str, float]:
    now = time.time()
    out: Dict[str, float] = {}
    for k, ts in keys_map.items():
        if not isinstance(k, str) or len(k) > 256:
            continue
        try:
            t = float(ts)
        except (TypeError, ValueError):
            continue
        if now - t < TTL_SEC:
            out[k[:256]] = t
    if len(out) > MAX_KEYS:
        # Drop oldest
        items = sorted(out.items(), key=lambda x: x[1])[-MAX_KEYS:]
        out = dict(items)
    return out


def remember_if_new(key: str) -> bool:
    """Return True if *new* (should process), False if duplicate."""

    k = (key or "").strip()
    if not k or len(k) > 256:
        return True
    data = _read()
    km = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    km = _prune_keys(km)  # type: ignore[arg-type]
    if k in km:
        return False
    km[k] = time.time()
    data["keys"] = km
    _write(data)
    return True


def seen_keys_for_tests() -> Set[str]:
    data = _read()
    km = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    return {str(x) for x in km.keys()}


def reset_for_tests() -> None:
    if PATH.is_file():
        PATH.unlink()

