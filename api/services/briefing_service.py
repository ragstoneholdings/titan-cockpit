"""Deterministic morning briefing (anchors + kill zones + Combat slot #1 alignment)."""

from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any, Dict, List, Optional


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def briefing_active_hour_range() -> tuple[int, int]:
    """Inclusive start hour, exclusive end hour (local wall clock)."""
    start = _env_int("BRIEFING_ACTIVE_START_HOUR", 8)
    end = _env_int("BRIEFING_ACTIVE_END_HOUR", 11)
    if end <= start:
        end = min(23, start + 1)
    return start, end


def briefing_window_active(now: Optional[datetime] = None) -> bool:
    """True when local hour is in [BRIEFING_ACTIVE_START_HOUR, BRIEFING_ACTIVE_END_HOUR)."""
    now = now or datetime.now().astimezone()
    tz = now.tzinfo
    local = now.astimezone(tz) if tz else now
    start_h, end_h = briefing_active_hour_range()
    return start_h <= local.hour < end_h


def _fmt_clock_local(dt: datetime) -> str:
    loc = dt.astimezone()
    h12 = loc.hour % 12 or 12
    ap = "AM" if loc.hour < 12 else "PM"
    return f"{h12}:{loc.minute:02d} {ap}"


def _fmt_zone(z: Dict[str, Any]) -> str:
    s = str(z.get("start_iso") or "").strip()
    e = str(z.get("end_iso") or "").strip()
    if not s or not e:
        return "(time TBD)"
    try:
        ts = datetime.fromisoformat(s.replace("Z", "+00:00"))
        te = datetime.fromisoformat(e.replace("Z", "+00:00"))
        return f"{_fmt_clock_local(ts)}–{_fmt_clock_local(te)}"
    except ValueError:
        return f"{s[:16]}… → {e[:16]}…"


def build_morning_brief_payload(
    recon_day: date,
    runway: Dict[str, Any],
    kill_zones: List[Dict[str, Any]],
    trio_slot1_title: str,
    *,
    dismissed: bool,
    window_active: bool,
) -> Dict[str, Any]:
    """Structured morning brief; `visible` only for today + window + not dismissed."""
    today = date.today()
    visible = recon_day == today and window_active and not dismissed

    anchor_title = str(runway.get("anchor_title") or "").strip() or "No hard anchor on file."
    anchor_start = str(runway.get("anchor_start_iso") or "").strip()
    anchor_clock = ""
    if anchor_start:
        try:
            adt = datetime.fromisoformat(anchor_start.replace("Z", "+00:00"))
            anchor_clock = _fmt_clock_local(adt)
        except ValueError:
            anchor_clock = anchor_start[:16]

    anchors_summary = anchor_title
    if anchor_clock:
        anchors_summary = f"{anchor_title} — first commitment around **{anchor_clock}**."

    k3: List[Dict[str, str]] = []
    for z in (kill_zones or [])[:3]:
        if not isinstance(z, dict):
            continue
        k3.append(
            {
                "start_iso": str(z.get("start_iso") or ""),
                "end_iso": str(z.get("end_iso") or ""),
            }
        )

    slot1 = str(trio_slot1_title or "").strip()
    matched_idx: Optional[int] = None
    match_sentence = ""
    if slot1 and k3:
        matched_idx = 0
        rng = _fmt_zone(k3[0])
        match_sentence = (
            f"**Combat (#1)** *{slot1}* maps to your **first deep-work window** ({rng}). "
            "Start there when that gap opens."
        )

    lines: List[str] = []
    lines.append("### Hard anchor")
    lines.append(anchors_summary)
    lines.append("")
    lines.append("### Top kill zones (deep work)")
    if k3:
        for i, z in enumerate(k3, start=1):
            lines.append(f"{i}. {_fmt_zone(z)}")
    else:
        lines.append("No 60m+ gaps detected from calendars — protect ad-hoc focus where you can.")

    if match_sentence:
        lines.append("")
        lines.append("### Combat alignment")
        lines.append(match_sentence)

    brief_markdown = "\n".join(lines).strip()

    return {
        "visible": visible,
        "dismissed": dismissed,
        "briefing_window_active": window_active,
        "anchors_summary": anchors_summary,
        "kill_zones_top3": k3,
        "trio_slot1_title": slot1,
        "matched_zone_index": matched_idx,
        "brief_markdown": brief_markdown,
        "generated_at": datetime.now().astimezone().isoformat(),
    }
