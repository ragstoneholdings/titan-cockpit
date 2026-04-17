"""Life-purpose text persisted in identity.json (Purpose Pillar)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent
IDENTITY_JSON_PATH = ROOT / "identity.json"

DEFAULT_PURPOSE_TEXT = (
    "Integrity under pressure. Disciplined execution, plain speech, relationships worth defending. "
    "Build strength and outcomes that outlast you."
)


def _default_drain_profile() -> Dict[str, Any]:
    return {"high_drain_labels": [], "high_drain_title_substrings": []}


def _default_bundle() -> Dict[str, Any]:
    return {"version": 2, "purpose": DEFAULT_PURPOSE_TEXT, "drain_profile": _default_drain_profile()}


def _read_raw_bundle() -> Dict[str, Any]:
    if not IDENTITY_JSON_PATH.is_file():
        return {}
    try:
        raw = json.loads(IDENTITY_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def load_identity_purpose() -> str:
    if not IDENTITY_JSON_PATH.is_file():
        save_identity_purpose(DEFAULT_PURPOSE_TEXT)
        return DEFAULT_PURPOSE_TEXT
    raw = _read_raw_bundle()
    if not raw:
        save_identity_purpose(DEFAULT_PURPOSE_TEXT)
        return DEFAULT_PURPOSE_TEXT
    p = raw.get("purpose")
    if not isinstance(p, str) or not str(p).strip():
        save_identity_purpose(DEFAULT_PURPOSE_TEXT)
        return DEFAULT_PURPOSE_TEXT
    return str(p).strip()


def load_identity_drain_profile() -> Dict[str, Any]:
    """Optional energy/drain tagging for ranking; empty lists = no behavior change."""
    raw = _read_raw_bundle()
    if not raw:
        return dict(_default_drain_profile())
    dp = raw.get("drain_profile")
    if not isinstance(dp, dict):
        return dict(_default_drain_profile())
    out = dict(_default_drain_profile())
    labs = dp.get("high_drain_labels")
    if isinstance(labs, list):
        out["high_drain_labels"] = [str(x).strip() for x in labs if str(x).strip()]
    subs = dp.get("high_drain_title_substrings")
    if isinstance(subs, list):
        out["high_drain_title_substrings"] = [str(x).strip() for x in subs if str(x).strip()]
    return out


def save_identity_purpose(text: str) -> None:
    raw = _read_raw_bundle()
    purpose = str(text).strip() or DEFAULT_PURPOSE_TEXT
    drain = raw.get("drain_profile")
    if not isinstance(drain, dict):
        drain = _default_drain_profile()
    ver = max(2, int(raw.get("version") or 1))
    bundle = {"version": ver, "purpose": purpose, "drain_profile": drain}
    tmp = IDENTITY_JSON_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(bundle, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(IDENTITY_JSON_PATH)
