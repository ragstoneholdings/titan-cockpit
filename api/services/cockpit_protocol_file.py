"""Optional JSON overrides for CHIEF_* protocol env (used by cockpit when present)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from chief_of_staff.models import IdentityProtocols
from integrations.env_loader import env_str
from integrations.paths import data_root

PROTOCOL_PATH = data_root() / "cockpit_protocol_settings.json"


def _default_bundle() -> Dict[str, Any]:
    return {
        "version": 1,
        "chief_hard_markers": None,
        "chief_posture_minutes": None,
        "chief_neck_minutes": None,
        "chief_ops_minutes": None,
    }


def load_protocol_bundle() -> Dict[str, Any]:
    if not PROTOCOL_PATH.is_file():
        return _default_bundle()
    try:
        raw = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_bundle()
    if not isinstance(raw, dict):
        return _default_bundle()
    out = _default_bundle()
    for k in list(out.keys()):
        if k in raw:
            out[k] = raw[k]
    return out


def save_protocol_bundle(data: Dict[str, Any]) -> None:
    payload = _default_bundle()
    for k in payload:
        if k in data:
            payload[k] = data[k]
    tmp = PROTOCOL_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PROTOCOL_PATH)


def merged_chief_hard_markers_csv() -> str:
    b = load_protocol_bundle()
    v = b.get("chief_hard_markers")
    if isinstance(v, str):
        return v.strip()
    if v is None:
        return env_str("CHIEF_HARD_MARKERS", "")
    return str(v).strip()


def _mint(key: str, default: int) -> int:
    try:
        return max(0, int(env_str(key, str(default)) or str(default)))
    except ValueError:
        return default


def merged_identity_protocols() -> IdentityProtocols:
    b = load_protocol_bundle()

    def pick(file_key: str, env_key: str, default: int) -> int:
        raw = b.get(file_key)
        if raw is not None and str(raw).strip() != "":
            try:
                return max(0, int(raw))
            except (TypeError, ValueError):
                pass
        return _mint(env_key, default)

    return IdentityProtocols(
        posture=timedelta(minutes=pick("chief_posture_minutes", "CHIEF_POSTURE_MINUTES", 30)),
        neck=timedelta(minutes=pick("chief_neck_minutes", "CHIEF_NECK_MINUTES", 60)),
        morning_ops=timedelta(minutes=pick("chief_ops_minutes", "CHIEF_OPS_MINUTES", 30)),
    )


def protocol_settings_response() -> Dict[str, Any]:
    b = load_protocol_bundle()
    return {
        "chief_hard_markers": b.get("chief_hard_markers"),
        "chief_posture_minutes": b.get("chief_posture_minutes"),
        "chief_neck_minutes": b.get("chief_neck_minutes"),
        "chief_ops_minutes": b.get("chief_ops_minutes"),
        "resolved_chief_hard_markers": merged_chief_hard_markers_csv(),
        "resolved_posture_minutes": int(merged_identity_protocols().posture.total_seconds() // 60),
        "resolved_neck_minutes": int(merged_identity_protocols().neck.total_seconds() // 60),
        "resolved_ops_minutes": int(merged_identity_protocols().morning_ops.total_seconds() // 60),
    }
