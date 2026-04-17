"""User actions on rule-based golden path proposals (dismiss / approve / snooze)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from integrations.paths import data_root

STORE_PATH = data_root() / "golden_path_proposal_actions.json"


def _default_root() -> Dict[str, Any]:
    return {"version": 1, "by_day": {}}


def load_root() -> Dict[str, Any]:
    if not STORE_PATH.is_file():
        return _default_root()
    try:
        raw = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_root()
    if not isinstance(raw, dict):
        return _default_root()
    out = _default_root()
    if isinstance(raw.get("by_day"), dict):
        out["by_day"] = dict(raw["by_day"])
    return out


def save_root(data: Dict[str, Any]) -> None:
    root = _default_root()
    if isinstance(data.get("by_day"), dict):
        root["by_day"] = dict(data["by_day"])
    tmp = STORE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(root, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STORE_PATH)


def _day_bucket(day: date) -> Dict[str, Any]:
    root = load_root()
    by_day = root.setdefault("by_day", {})
    key = day.isoformat()
    if key not in by_day or not isinstance(by_day[key], dict):
        by_day[key] = {"dismissed": [], "approved": [], "snoozed_until": None}
    b = by_day[key]
    if not isinstance(b.get("dismissed"), list):
        b["dismissed"] = []
    if not isinstance(b.get("approved"), list):
        b["approved"] = []
    return b


def get_dismissed_ids(day: date) -> Set[str]:
    b = _day_bucket(day)
    return {str(x) for x in b["dismissed"] if isinstance(x, str)}


def get_approved_ids(day: date) -> Set[str]:
    b = _day_bucket(day)
    return {str(x) for x in b["approved"] if isinstance(x, str)}


def is_snoozed(day: date) -> bool:
    b = _day_bucket(day)
    raw = b.get("snoozed_until")
    if not raw or not isinstance(raw, str):
        return False
    try:
        until = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return now < until.astimezone(timezone.utc)


def set_action(day: date, proposal_id: str, action: str) -> Dict[str, Any]:
    if action not in ("approve", "dismiss", "snooze"):
        raise ValueError("action must be approve, dismiss, or snooze")
    root = load_root()
    by_day: Dict[str, Any] = dict(root.get("by_day") or {})
    key = day.isoformat()
    bucket = dict(by_day.get(key) or {})
    dismissed: List[str] = list(bucket.get("dismissed") or [])
    approved: List[str] = list(bucket.get("approved") or [])

    if action == "dismiss":
        if proposal_id not in dismissed:
            dismissed.append(proposal_id)
        approved = [x for x in approved if x != proposal_id]
    elif action == "approve":
        if proposal_id not in approved:
            approved.append(proposal_id)
        dismissed = [x for x in dismissed if x != proposal_id]
    else:  # snooze — suppress proposal card refresh noise for 24h
        snooze_end = datetime.now(timezone.utc) + timedelta(hours=24)
        bucket["snoozed_until"] = snooze_end.isoformat()

    bucket["dismissed"] = dismissed
    bucket["approved"] = approved
    by_day[key] = bucket
    root["by_day"] = by_day
    save_root(root)
    return bucket


def clear_snooze(day: date) -> None:
    root = load_root()
    by_day: Dict[str, Any] = dict(root.get("by_day") or {})
    key = day.isoformat()
    if key in by_day and isinstance(by_day[key], dict):
        by_day[key]["snoozed_until"] = None
        root["by_day"] = by_day
        save_root(root)
