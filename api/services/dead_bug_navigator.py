"""Nagging Navigator: Vanguard Priority projects stale > N hours."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from integrations.env_loader import env_str
from power_trio import split_substrings_csv


def _parse_iso(s: str) -> Any:
    if not s or not str(s).strip():
        return None
    try:
        t = str(s).strip().replace("Z", "+00:00")
        return datetime.fromisoformat(t)
    except ValueError:
        return None


def compute_dead_bug_alerts(
    by_id: Dict[str, Any],
    *,
    hours_stale: float = 48.0,
) -> List[Dict[str, Any]]:
    raw_csv = env_str("VANGUARD_PRIORITY_PROJECT_SUBSTRINGS", "Vanguard")
    substrings = [x.lower() for x in split_substrings_csv(raw_csv)]
    if not substrings:
        return []
    now = datetime.now(timezone.utc)
    stale_delta = timedelta(hours=hours_stale)
    by_project: Dict[str, List[Dict[str, Any]]] = {}
    for t in by_id.values():
        if not isinstance(t, dict):
            continue
        pname = str(t.get("project_name") or "").strip()
        pl = pname.lower()
        if not any(s in pl for s in substrings):
            continue
        pid = str(t.get("project_id") or "")
        u = _parse_iso(str(t.get("updated_at") or ""))
        if u is None:
            u = now - stale_delta * 2
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        else:
            u = u.astimezone(timezone.utc)
        key = pid or pname
        by_project.setdefault(key, []).append(
            {
                "project_name": pname or "(project)",
                "project_id": pid,
                "updated_at": u.isoformat(),
                "task_id": str(t.get("id") or ""),
                "title": str(t.get("content") or "")[:80],
            }
        )
    alerts: List[Dict[str, Any]] = []
    for key, rows in by_project.items():
        latest = max(rows, key=lambda r: r["updated_at"])
        u = _parse_iso(latest["updated_at"])
        if u is None:
            continue
        if now - u > stale_delta:
            hours = (now - u).total_seconds() / 3600.0
            alerts.append(
                {
                    "project_id": latest.get("project_id") or "",
                    "project_name": latest.get("project_name") or "",
                    "hours_since_activity": round(hours, 1),
                    "task_id": latest.get("task_id") or "",
                    "title_hint": latest.get("title") or "",
                }
            )
    alerts.sort(key=lambda x: -float(x.get("hours_since_activity") or 0))
    return alerts[:5]
