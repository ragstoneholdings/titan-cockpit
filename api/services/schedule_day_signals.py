"""
Schedule pressure / conflict signals aligned with docs/SCHEDULE_INTAKE_RYAN.md.

Priorities: A1 overlaps, A5 deep-work starvation (60m contiguous), A2 fragmentation / density;
calendar blocked-time warning at 5h+ (weekends suppress the heavy-day flag only); work vs personal API overlap flags.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from chief_of_staff.planning import (
    _bounds_from_google_event,
    _bounds_from_personal_row,
    _parse_hhmm_env,
    _parse_iso_dt,
    compute_deep_work_kill_zones,
    local_tz,
    to_local,
)

from api.services.landscape_tradeoff_resolve import stable_overlap_id

# Intake: docs/SCHEDULE_INTAKE_RYAN.md
DEEP_WORK_MIN_MINUTES = 60
MEETING_LOAD_WARN_MINUTES_DEFAULT = 5 * 60
SMALL_GAP_MAX_MINUTES = 59
FRAGMENT_SMALL_GAP_THRESHOLD = 4
SOURCE_OVERLAP_MIN_MINUTES = 15

IMMOVABLE_TITLE_SUBSTRINGS = (
    "gxo manager biweekly",
    "hiring delivery team meeting",
    "1:1",
)

MEETING_EXCLUSION_SUBSTRINGS = (
    "commute",
    "rdw",
    "ryan doing work",
)


def _extra_meeting_exclude_substrings() -> Tuple[str, ...]:
    raw = (os.environ.get("SCHEDULE_MEETING_EXCLUDE_SUBSTRINGS") or "").strip()
    if not raw:
        return ()
    return tuple(x.strip().lower() for x in raw.split(",") if x.strip())


def _meeting_load_warn_minutes() -> int:
    raw = (os.environ.get("SCHEDULE_MEETING_LOAD_WARN_MINUTES") or "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    hrs = (os.environ.get("SCHEDULE_MEETING_LOAD_WARN_HOURS") or "").strip()
    if hrs:
        try:
            return max(1, int(float(hrs) * 60))
        except ValueError:
            pass
    return MEETING_LOAD_WARN_MINUTES_DEFAULT


def _title_excludes_meeting_load(title: str) -> bool:
    t = str(title or "").lower()
    if any(x in t for x in MEETING_EXCLUSION_SUBSTRINGS):
        return True
    return any(x in t for x in _extra_meeting_exclude_substrings())


def _immovable_title(title: str) -> bool:
    t = " ".join(str(title or "").strip().lower().split())
    return any(sub in t for sub in IMMOVABLE_TITLE_SUBSTRINGS)


def _clip_to_day(
    s: datetime, e: datetime, day_start: datetime, day_end: datetime
) -> Optional[Tuple[datetime, datetime]]:
    s2 = max(to_local(s), day_start)
    e2 = min(to_local(e), day_end)
    if e2 <= s2:
        return None
    return s2, e2


def build_work_screenshot_busy_spans(
    day: date, landscape: List[Dict[str, Any]]
) -> List[Tuple[datetime, datetime]]:
    """Busy intervals from work screenshot rows (for kill zones + schedule math)."""
    tz = local_tz()
    day_start = datetime.combine(day, time.min).replace(tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    out: List[Tuple[datetime, datetime]] = []
    for row in landscape or []:
        if str(row.get("source_kind") or "") != "work_screenshot":
            continue
        s = _parse_iso_dt(str(row.get("start_iso") or ""))
        if s is None:
            continue
        e_raw = row.get("end_iso")
        if e_raw:
            e = _parse_iso_dt(str(e_raw)) or (s + timedelta(hours=1))
        else:
            e = s + timedelta(hours=1)
        clipped = _clip_to_day(s, e, day_start, day_end)
        if clipped:
            out.append(clipped)
    return out


def _collect_labeled_intervals(
    day: date,
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
    landscape: List[Dict[str, Any]],
) -> List[Tuple[datetime, datetime, str, str]]:
    """
    (start, end, title, tag) with tag in google | personal | work_screenshot.
    Clipped to local calendar day.
    """
    tz = local_tz()
    day_start = datetime.combine(day, time.min).replace(tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    items: List[Tuple[datetime, datetime, str, str]] = []

    for ev in google_events or []:
        b = _bounds_from_google_event(ev)
        if not b:
            continue
        s, e = b
        title = str(ev.get("summary") or "(no title)").strip() or "(no title)"
        clipped = _clip_to_day(s, e, day_start, day_end)
        if clipped:
            items.append((clipped[0], clipped[1], title, "google"))

    for row in personal_rows or []:
        b = _bounds_from_personal_row(row)
        if not b:
            continue
        s, e = b
        title = str(row.get("title") or "(no title)").strip() or "(no title)"
        clipped = _clip_to_day(s, e, day_start, day_end)
        if clipped:
            items.append((clipped[0], clipped[1], title, "personal"))

    for ws, we in build_work_screenshot_busy_spans(day, landscape):
        title = "(work screenshot)"
        for row in landscape or []:
            if str(row.get("source_kind") or "") != "work_screenshot":
                continue
            rs = _parse_iso_dt(str(row.get("start_iso") or ""))
            if rs is None:
                continue
            if abs((to_local(rs) - to_local(ws)).total_seconds()) < 120:
                title = str(row.get("title") or "(work screenshot)").strip() or "(work screenshot)"
                break
        items.append((ws, we, title, "work_screenshot"))

    return items


def _merge_busy(spans: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    if not spans:
        return []
    spans = sorted(spans, key=lambda x: x[0])
    merged: List[Tuple[datetime, datetime]] = []
    for s, e in spans:
        s = to_local(s)
        e = to_local(e)
        if e <= s:
            continue
        if not merged:
            merged.append((s, e))
            continue
        ps, pe = merged[-1]
        if s <= pe:
            merged[-1] = (ps, max(pe, e))
        else:
            merged.append((s, e))
    return merged


def _awake_bounds(day: date) -> Tuple[datetime, datetime]:
    tz = local_tz()
    a0 = _parse_hhmm_env("COCKPIT_AWAKE_START", "05:00")
    a1 = _parse_hhmm_env("COCKPIT_AWAKE_END", "19:30")
    win0 = datetime.combine(day, a0).replace(tzinfo=tz)
    win1 = datetime.combine(day, a1).replace(tzinfo=tz)
    return win0, win1


def _intersection_minutes(
    a: Tuple[datetime, datetime], b: Tuple[datetime, datetime]
) -> float:
    s = max(a[0], b[0])
    e = min(a[1], b[1])
    if e <= s:
        return 0.0
    return (e - s).total_seconds() / 60.0


def _same_event_dedupe(
    t1: str, s1: datetime, t2: str, s2: datetime, tol_sec: int = 120
) -> bool:
    if _norm_title(t1) != _norm_title(t2):
        return False
    return abs((to_local(s1) - to_local(s2)).total_seconds()) <= tol_sec


def _norm_title(t: str) -> str:
    return " ".join(str(t or "").strip().lower().split())


def _overlap_pairs(
    items: List[Tuple[datetime, datetime, str, str]],
) -> List[Dict[str, Any]]:
    overlaps: List[Dict[str, Any]] = []
    n = len(items)
    for i in range(n):
        s1, e1, title1, tag1 = items[i]
        for j in range(i + 1, n):
            s2, e2, title2, tag2 = items[j]
            if _same_event_dedupe(title1, s1, title2, s2):
                continue
            ov = _intersection_minutes((s1, e1), (s2, e2))
            if ov < 1.0:
                continue
            overlaps.append(
                {
                    "start_iso": max(s1, s2).isoformat(),
                    "end_iso": min(e1, e2).isoformat(),
                    "title_a": title1,
                    "title_b": title2,
                    "source_a": tag1,
                    "source_b": tag2,
                    "start_a_iso": to_local(s1).isoformat(),
                    "end_a_iso": to_local(e1).isoformat(),
                    "start_b_iso": to_local(s2).isoformat(),
                    "end_b_iso": to_local(e2).isoformat(),
                }
            )
    return overlaps[:24]


def _work_personal_flags(
    items: List[Tuple[datetime, datetime, str, str]],
) -> List[Dict[str, Any]]:
    work = [(s, e, t) for s, e, t, tag in items if tag == "work_screenshot"]
    other = [(s, e, t, tag) for s, e, t, tag in items if tag != "work_screenshot"]
    flags: List[Dict[str, Any]] = []
    seen: set = set()
    for ws, we, wt in work:
        for os, oe, ot, otag in other:
            mins = _intersection_minutes((ws, we), (os, oe))
            if mins < SOURCE_OVERLAP_MIN_MINUTES:
                continue
            key = (ws.isoformat(), _norm_title(wt), _norm_title(ot), otag)
            if key in seen:
                continue
            seen.add(key)
            flags.append(
                {
                    "message": "Work screenshot overlaps a personal/API block — compare both.",
                    "start_iso": max(ws, os).isoformat(),
                    "work_title": wt,
                    "personal_title": ot,
                    "api_source": otag,
                }
            )
    return flags[:20]


def _meeting_load_merged_minutes(items: List[Tuple[datetime, datetime, str, str]]) -> int:
    """Union of meeting-ish intervals (excludes RDW/commute-style holds) so overlaps are not double-counted."""
    spans = [
        (s, e)
        for s, e, title, _tag in items
        if not _title_excludes_meeting_load(title)
    ]
    merged = _merge_busy(spans)
    return int(sum((to_local(e) - to_local(s)).total_seconds() / 60.0 for s, e in merged))


def _format_hm(minutes: int) -> str:
    h, m = divmod(max(0, minutes), 60)
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"


def _awake_gap_stats(merged_busy: List[Tuple[datetime, datetime]], day: date) -> Tuple[int, int]:
    """Max gap minutes inside awake window; count of small gaps (1..59m) between busy segments."""
    win0, win1 = _awake_bounds(day)
    if not merged_busy:
        return int((win1 - win0).total_seconds() // 60), 0

    busy = sorted((max(win0, to_local(s)), min(win1, to_local(e))) for s, e in merged_busy)
    busy = [(s, e) for s, e in busy if e > s]
    if not busy:
        return int((win1 - win0).total_seconds() // 60), 0

    max_gap = 0
    small = 0
    cursor = win0
    for s, e in busy:
        if s > cursor:
            gap_min = int((s - cursor).total_seconds() // 60)
            if gap_min > max_gap:
                max_gap = gap_min
            if 0 < gap_min < DEEP_WORK_MIN_MINUTES:
                small += 1
        cursor = max(cursor, e)
    if win1 > cursor:
        gap_min = int((win1 - cursor).total_seconds() // 60)
        if gap_min > max_gap:
            max_gap = gap_min
        if 0 < gap_min < DEEP_WORK_MIN_MINUTES:
            small += 1
    return max_gap, small


def _build_suggestions(
    overlap_count: int,
    meeting_warn: bool,
    meeting_minutes: int,
    deep_slot_60: bool,
    fragmented: bool,
    source_n: int,
    runway_conflict: bool,
) -> List[str]:
    """Intake order preference: questions first, then tradeoffs, concrete moves, nudges."""
    qs: List[str] = []

    if source_n:
        qs.append(
            "For a slot flagged work vs personal/API, which source reflects what you actually did "
            "or will do?"
        )

    if meeting_warn:
        qs.append(
            f"About {_format_hm(meeting_minutes)} is blocked on calendars today — if you shorten "
            "or decline one block, which moves the needle least for your priorities?"
        )

    if not deep_slot_60 and (meeting_minutes >= 120 or overlap_count):
        qs.append(
            "There is no 60+ minute contiguous free window in your awake hours — "
            "is any hold (except immovable 1:1s / GXO / Hiring Delivery) soft enough to slide?"
        )

    if fragmented and not overlap_count:
        qs.append(
            "The day is fragmented into short gaps — which two blocks could you batch or merge "
            "to open one real focus window?"
        )

    if runway_conflict:
        qs.append("Runway shows a morning tension — does your first hard commitment still match reality?")

    if meeting_warn and len(qs) < 5:
        qs.append(
            "Tradeoff: pick one lower-value meeting to shorten by 15–30m to buy a deep-work slot."
        )

    return qs[:8]


def _build_suggestion_items(
    overlap_count: int,
    meeting_warn: bool,
    meeting_minutes: int,
    deep_slot_60: bool,
    fragmented: bool,
    source_n: int,
    runway_conflict: bool,
) -> List[Dict[str, Any]]:
    """Structured MCQs mirroring _build_suggestions order (stable ids for persistence)."""
    items: List[Dict[str, Any]] = []

    if overlap_count:
        items.append(
            {
                "id": "overlap_resolution_hint",
                "prompt": (
                    "Overlapping calendar rows detected. Use **Daily landscape** → **Overlapping meetings** "
                    "to pick which block wins for in-app planning truth (calendars are not rewritten)."
                ),
                "options": [
                    {"value": "acknowledged", "label": "Acknowledged — I'll resolve there"},
                    {"value": "later", "label": "I'll decide later"},
                    {"value": "undecided", "label": "Not sure yet"},
                ],
            }
        )

    if source_n:
        items.append(
            {
                "id": "work_vs_personal_truth",
                "prompt": (
                    "For a slot flagged work screenshot vs personal/API, which reflects what you "
                    "actually did or will do?"
                ),
                "options": [
                    {"value": "work_screenshot", "label": "Work screenshot"},
                    {"value": "personal_api", "label": "Personal / API calendar"},
                    {"value": "both_partially", "label": "Both — split truth"},
                    {"value": "undecided", "label": "Not sure yet"},
                ],
            }
        )

    if meeting_warn:
        items.append(
            {
                "id": "meeting_tradeoff",
                "prompt": (
                    f"About {_format_hm(meeting_minutes)} is blocked on calendars today. "
                    "If you shorten or decline one block, what is your default stance?"
                ),
                "options": [
                    {"value": "maintain_all", "label": "Keep the grid as-is"},
                    {"value": "decline_low_value", "label": "Decline one low-value hold"},
                    {"value": "move_async", "label": "Move one block async / email"},
                    {"value": "undecided", "label": "Not sure yet"},
                ],
            }
        )

    if not deep_slot_60 and (meeting_minutes >= 120 or overlap_count):
        items.append(
            {
                "id": "no_60m_slide",
                "prompt": (
                    "There is no 60+ minute contiguous free window in your awake hours. "
                    "Is any hold (except immovable 1:1s / GXO / Hiring Delivery) soft enough to slide?"
                ),
                "options": [
                    {"value": "slide_soft_hold", "label": "Yes — I can slide a soft hold"},
                    {"value": "protect_prep", "label": "No — protect prep; I'll shrink elsewhere"},
                    {"value": "undecided", "label": "Not sure yet"},
                ],
            }
        )

    if fragmented and not overlap_count:
        items.append(
            {
                "id": "fragmented_batch",
                "prompt": (
                    "The day is fragmented into short gaps. What is your first move to open one "
                    "real focus window?"
                ),
                "options": [
                    {"value": "merge_blocks", "label": "Batch / merge two blocks"},
                    {"value": "keep_as_is", "label": "Keep as-is"},
                    {"value": "undecided", "label": "Not sure yet"},
                ],
            }
        )

    if runway_conflict:
        items.append(
            {
                "id": "runway_reality",
                "prompt": "Runway shows a morning tension. Does your first hard commitment still match reality?",
                "options": [
                    {"value": "anchor_accurate", "label": "Yes — anchor is right"},
                    {"value": "needs_update", "label": "No — calendar moved"},
                    {"value": "undecided", "label": "Not sure yet"},
                ],
            }
        )

    if meeting_warn and len(items) < 5:
        items.append(
            {
                "id": "shorten_meeting_tradeoff",
                "prompt": (
                    "Tradeoff: pick one lower-value meeting to shorten by 15–30m to buy a deep-work slot. "
                    "Will you take it?"
                ),
                "options": [
                    {"value": "will_shorten", "label": "Yes — I'll shorten one"},
                    {"value": "no_change", "label": "No — keep schedule"},
                    {"value": "undecided", "label": "Not sure yet"},
                ],
            }
        )

    return items[:8]


def compute_schedule_day_signals(
    day: date,
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
    landscape: List[Dict[str, Any]],
    *,
    runway_conflict: bool = False,
) -> Dict[str, Any]:
    items = _collect_labeled_intervals(day, google_events, personal_rows, landscape)
    overlaps = _overlap_pairs(items)
    for ov in overlaps:
        ov["id"] = stable_overlap_id(ov)
    source_flags = _work_personal_flags(items)
    meeting_minutes = _meeting_load_merged_minutes(items)
    warn_min = _meeting_load_warn_minutes()
    weekend = day.weekday() >= 5
    meeting_warn = (meeting_minutes >= warn_min) and (not weekend)

    busy_spans = [(s, e) for s, e, _t, _tag in items]
    merged = _merge_busy(busy_spans)
    max_gap_min, small_gap_count = _awake_gap_stats(merged, day)
    deep_slot_60 = max_gap_min >= DEEP_WORK_MIN_MINUTES

    zones_60 = compute_deep_work_kill_zones(
        google_events,
        personal_rows,
        day,
        min_gap=timedelta(minutes=DEEP_WORK_MIN_MINUTES),
        extra_busy_spans=build_work_screenshot_busy_spans(day, landscape),
    )
    deep_slot_60 = deep_slot_60 or bool(zones_60)

    fragmented = small_gap_count >= FRAGMENT_SMALL_GAP_THRESHOLD or (
        not deep_slot_60 and small_gap_count >= 2 and meeting_minutes >= 180
    )

    parts: List[str] = []
    if overlaps:
        parts.append(f"{len(overlaps)} overlap{'s' if len(overlaps) != 1 else ''}")
    if meeting_minutes > 0:
        cal_line = f"~{_format_hm(meeting_minutes)} on calendar"
        if meeting_warn:
            cal_line += f" (≥{_format_hm(warn_min)} blocked)"
        parts.append(cal_line)
    if not deep_slot_60:
        parts.append("No 60m open window")
    if fragmented:
        parts.append("Short gaps between blocks")
    if source_flags:
        parts.append("Work vs calendar — compare")
    summary = " · ".join(parts) if parts else "Light day — few conflicts."

    suggestions = _build_suggestions(
        len(overlaps),
        meeting_warn,
        meeting_minutes,
        deep_slot_60,
        fragmented,
        len(source_flags),
        runway_conflict,
    )
    suggestion_items = _build_suggestion_items(
        len(overlaps),
        meeting_warn,
        meeting_minutes,
        deep_slot_60,
        fragmented,
        len(source_flags),
        runway_conflict,
    )

    return {
        "overlap_count": len(overlaps),
        "overlaps": overlaps,
        "source_flags": source_flags,
        "meeting_load_minutes": meeting_minutes,
        "meeting_load_hours_display": _format_hm(meeting_minutes),
        "meeting_load_warning": meeting_warn,
        "meeting_load_warn_threshold_minutes": warn_min,
        "max_free_gap_minutes": max_gap_min,
        "deep_slot_60_available": deep_slot_60,
        "fragmented_day": fragmented,
        "small_gap_count": small_gap_count,
        "immovable_title_hits": sum(1 for _s, _e, t, _ in items if _immovable_title(t)),
        "suggestion_questions": suggestions,
        "suggestion_items": suggestion_items,
        "summary_line": summary,
    }
