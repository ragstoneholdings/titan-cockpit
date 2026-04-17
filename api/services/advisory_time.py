"""Parse Gemini/local time strings into ISO timestamps for a calendar date (local TZ)."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set, Tuple


def local_iso_from_day_and_time_guess(day: date, raw: str) -> Optional[str]:
    """
    Interpret a human/OCR time string as local time on `day`, return UTC ISO string.
    Mirrors web/src/App.tsx hhmmGuessToLocalIso.
    """
    s = (raw or "").strip()
    if not s:
        return None
    tzinfo = datetime.now().astimezone().tzinfo
    base = datetime.combine(day, datetime.min.time()).replace(
        hour=12, minute=0, second=0, microsecond=0, tzinfo=tzinfo
    )

    ampm = re.match(r"^(\d{1,2}):(\d{2})\s*([AaPp][Mm])\b", s)
    if ampm:
        h = int(ampm.group(1))
        minute = int(ampm.group(2))
        mer = ampm.group(3).lower()
        if h < 1 or h > 12 or minute < 0 or minute > 59:
            return None
        if mer == "pm" and h != 12:
            h += 12
        if mer == "am" and h == 12:
            h = 0
        dt = datetime.combine(day, datetime.min.time()).replace(
            hour=h, minute=minute, second=0, microsecond=0, tzinfo=tzinfo
        )
        return dt.isoformat()

    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        h = int(m.group(1))
        minute = int(m.group(2))
        if 0 <= h <= 23 and 0 <= minute <= 59:
            dt = datetime.combine(day, datetime.min.time()).replace(
                hour=h, minute=minute, second=0, microsecond=0, tzinfo=tzinfo
            )
            return dt.isoformat()
    # Last resort: dateutil-free parse "day + string"
    try:
        # calendar month name etc.
        t = datetime.strptime(f"{day.isoformat()} {s}", "%Y-%m-%d %I:%M %p")
        dt = t.replace(tzinfo=tzinfo)
        return dt.isoformat()
    except ValueError:
        pass
    try:
        t = datetime.strptime(f"{day.isoformat()} {s}", "%Y-%m-%d %H:%M")
        dt = t.replace(tzinfo=tzinfo)
        return dt.isoformat()
    except ValueError:
        return None


def _event_anchor_day(recon_day: date, ev: Dict[str, Any]) -> date:
    """Prefer printed column date for week-view rows; else recon upload day."""
    col = str(ev.get("column_date_iso") or "").strip()
    if len(col) >= 10:
        col = col[:10]
        try:
            return date.fromisoformat(col)
        except ValueError:
            pass
    return recon_day


def landscape_rows_from_advisory_events(
    day: date, advisory_events: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Build cockpit landscape dicts (work screenshot) from raw model event dicts."""
    out: List[Dict[str, Any]] = []
    for ev in advisory_events:
        if not isinstance(ev, dict):
            continue
        title = str(ev.get("title") or "").strip() or "(screenshot)"
        guess = str(
            ev.get("start_local_guess") or ev.get("start") or ev.get("time") or ""
        ).strip()
        if not guess:
            continue
        anchor = _event_anchor_day(day, ev)
        iso = local_iso_from_day_and_time_guess(anchor, guess)
        if not iso:
            continue
        row: Dict[str, Any] = {
            "start_iso": iso,
            "title": title,
            "source": "google",
            "source_kind": "work_screenshot",
        }
        col = str(ev.get("column_date_iso") or "").strip()
        if col:
            row["column_date_iso"] = col
        cw = ev.get("column_weekday")
        if isinstance(cw, str) and cw.strip():
            row["column_weekday"] = cw.strip().title()
        out.append(row)
    # Dedupe identical rows, sort
    seen: Set[Tuple[str, str]] = set()
    uniq: List[Dict[str, Any]] = []
    for row in sorted(out, key=lambda r: r["start_iso"]):
        key = (row["start_iso"], row["title"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return uniq
