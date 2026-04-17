"""Compact Mon–Sun calendar digest for Titan Prep (wardrobe) Gemini grounding."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from integrations.google_calendar import calendar_service_from_token, list_google_calendar_events_for_day
from integrations.personal_calendar import fetch_personal_calendar_events_from_env

_MAX_TITLE_LEN = 96
_MAX_LINES = 200


def _clip_title(s: str) -> str:
    t = " ".join(str(s or "").strip().split())
    if len(t) <= _MAX_TITLE_LEN:
        return t or "(no title)"
    return t[: _MAX_TITLE_LEN - 1] + "…"


def _local_hm(dt: datetime) -> str:
    loc = dt.astimezone() if dt.tzinfo else dt.replace(tzinfo=datetime.now().astimezone().tzinfo).astimezone()
    return loc.strftime("%H:%M")


def _google_event_line(day: date, ev: Dict[str, Any]) -> str | None:
    if ev.get("transparency") == "transparent":
        return None
    start_info = ev.get("start") or {}
    title = _clip_title(str(ev.get("summary") or "(no title)"))
    if "date" in start_info and "dateTime" not in start_info:
        ds = str(start_info.get("date") or day.isoformat())
        return f"{ds}  all-day  [google]  {title}"
    s_raw = start_info.get("dateTime")
    if not s_raw:
        return None
    try:
        s_dt = datetime.fromisoformat(str(s_raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    end_info = ev.get("end") or {}
    e_raw = end_info.get("dateTime")
    if e_raw:
        try:
            e_dt = datetime.fromisoformat(str(e_raw).replace("Z", "+00:00"))
            tr = f"{_local_hm(s_dt)}–{_local_hm(e_dt)}"
        except ValueError:
            tr = _local_hm(s_dt)
    else:
        tr = _local_hm(s_dt)
    return f"{day.isoformat()}  {tr}  [google]  {title}"


def _personal_row_line(day: date, row: Dict[str, Any]) -> str | None:
    title = _clip_title(str(row.get("title") or "(no title)"))
    if row.get("all_day"):
        return f"{day.isoformat()}  all-day  [personal]  {title}"
    s_raw = row.get("start_iso")
    e_raw = row.get("end_iso")
    if not s_raw:
        return None
    try:
        s_dt = datetime.fromisoformat(str(s_raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if e_raw:
        try:
            e_dt = datetime.fromisoformat(str(e_raw).replace("Z", "+00:00"))
            tr = f"{_local_hm(s_dt)}–{_local_hm(e_dt)}"
        except ValueError:
            tr = _local_hm(s_dt)
    else:
        tr = _local_hm(s_dt)
    return f"{day.isoformat()}  {tr}  [personal]  {title}"


def build_week_digest_for_titan_prep(week_monday: date, calendar_id: str) -> Tuple[str, int]:
    """
    Returns (multiline digest for the model, total event rows included).
    Mon–Sun inclusive starting week_monday. Empty digest if no service and no personal rows.
    """
    lines: List[str] = []
    svc = calendar_service_from_token()
    for i in range(7):
        d = week_monday + timedelta(days=i)
        if svc:
            for ev in list_google_calendar_events_for_day(svc, d, calendar_id):
                ln = _google_event_line(d, ev)
                if ln:
                    lines.append(ln)
        pers, _, _err = fetch_personal_calendar_events_from_env(d)
        for row in pers:
            ln = _personal_row_line(d, row)
            if ln:
                lines.append(ln)
    total_raw = len(lines)
    if total_raw > _MAX_LINES:
        kept = lines[:_MAX_LINES]
        kept.append(f"(… {_MAX_LINES} of {total_raw} lines shown; list truncated.)")
        lines = kept
    return ("\n".join(lines), total_raw)
