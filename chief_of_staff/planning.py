from __future__ import annotations

import os
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from chief_of_staff.models import ChiefOfStaffConfig, DayReadiness, HardAnchor, IdentityProtocols

DEFAULT_MORNING_OPS_ANCHOR_TITLE = "Morning Ops (default anchor)"

# Heuristic keywords (substring, case-insensitive) before default named titles.
HEURISTIC_KEYWORDS = ("sync", "review", "ragstone", "google")

# Exact title match (normalized whitespace, case-insensitive) after heuristics.
DEFAULT_NAMED_ANCHOR_TITLES = (
    "Morning Ops and Alignment",
    "Vanguard Bridge",
)


def local_tz():
    return datetime.now().astimezone().tzinfo


def to_local(dt: datetime) -> datetime:
    tz = local_tz()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)


def _normalize_title_key(title: str) -> str:
    return " ".join(str(title or "").strip().lower().split())


def _marker_match(title: str, markers: List[str]) -> bool:
    t = title.lower()
    return any(m.strip().lower() in t for m in markers if m.strip())


def _parse_iso_dt(s: str) -> Optional[datetime]:
    raw = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _anchor_matches_runway_override(
    anchor: HardAnchor,
    start_iso: str,
    title: str,
    source: str,
    tol_sec: int = 120,
) -> bool:
    if anchor.source != source:
        return False
    if _normalize_title_key(anchor.title) != _normalize_title_key(title):
        return False
    o_dt = _parse_iso_dt(start_iso)
    if o_dt is None:
        return False
    a = anchor.start
    if a.tzinfo is None:
        a = a.replace(tzinfo=local_tz())
    if o_dt.tzinfo is None:
        o_dt = o_dt.replace(tzinfo=local_tz())
    return abs((a - o_dt).total_seconds()) <= tol_sec


def tactical_compression_protocols(p: IdentityProtocols) -> IdentityProtocols:
    """Trim morning_ops to zero; halve neck and posture."""

    def half(td: timedelta) -> timedelta:
        return timedelta(seconds=td.total_seconds() / 2.0)

    return IdentityProtocols(
        posture=half(p.posture),
        neck=half(p.neck),
        morning_ops=timedelta(0),
    )


def _google_events_to_sorted_anchors(events: List[Dict[str, Any]]) -> List[HardAnchor]:
    timed: List[HardAnchor] = []
    for ev in events:
        if ev.get("transparency") == "transparent":
            continue
        start_info = ev.get("start") or {}
        if "date" in start_info:
            continue
        s = start_info.get("dateTime")
        if not s:
            continue
        try:
            s_dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        except ValueError:
            continue
        title = str(ev.get("summary") or "(no title)").strip() or "(no title)"
        eid = ev.get("id")
        cid = str(eid).strip() if eid else None
        timed.append(HardAnchor(start=s_dt, title=title, source="google", calendar_event_id=cid or None))
    timed.sort(key=lambda x: x.start)
    return timed


def _personal_rows_to_sorted_anchors(rows: List[Dict[str, Any]]) -> List[HardAnchor]:
    candidates: List[HardAnchor] = []
    for row in rows:
        if row.get("all_day"):
            continue
        start_iso = row.get("start_iso")
        if not start_iso:
            continue
        try:
            s_dt = datetime.fromisoformat(str(start_iso))
        except ValueError:
            continue
        title = str(row.get("title") or "(no title)").strip() or "(no title)"
        candidates.append(HardAnchor(start=s_dt, title=title, source="personal"))
    candidates.sort(key=lambda x: x.start)
    return candidates


def resolve_hard_anchor(
    sorted_anchors: List[HardAnchor],
    cfg: ChiefOfStaffConfig,
    *,
    gemini_chosen_index: Optional[int] = None,
) -> Optional[HardAnchor]:
    """
    Pick Hard Anchor from a single sorted timed list (markers → Gemini index → keywords
    → default named titles → first timed).
    """
    if not sorted_anchors:
        return None

    markers = [m for m in (cfg.hard_title_markers or []) if str(m).strip()]
    if markers:
        for a in sorted_anchors:
            if _marker_match(a.title, markers):
                return a

    if gemini_chosen_index is not None:
        i = int(gemini_chosen_index)
        if 0 <= i < len(sorted_anchors):
            return sorted_anchors[i]

    tlow = tuple(k.lower() for k in HEURISTIC_KEYWORDS)
    for a in sorted_anchors:
        tl = a.title.lower()
        if any(k in tl for k in tlow):
            return a

    named = {_normalize_title_key(x) for x in DEFAULT_NAMED_ANCHOR_TITLES}
    for a in sorted_anchors:
        if _normalize_title_key(a.title) in named:
            return a

    return sorted_anchors[0]


RunwayOverrideTriple = Tuple[str, str, str]  # (start_iso, title, source google|personal)


def active_timed_anchor_list(
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
) -> List[HardAnchor]:
    """Google-first timed anchors for the day (same list ``resolve_hard_anchor`` uses)."""
    g = _google_events_to_sorted_anchors(list(google_events or []))
    p = _personal_rows_to_sorted_anchors(list(personal_rows or []))
    return g if g else p


def merged_timed_anchors(
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
) -> List[HardAnchor]:
    """Chronological merge of Google + personal timed anchors (for pickers / previews)."""
    g = _google_events_to_sorted_anchors(list(google_events or []))
    p = _personal_rows_to_sorted_anchors(list(personal_rows or []))
    return sorted(g + p, key=lambda x: x.start)


def _bounds_from_google_event(ev: Dict[str, Any]) -> Optional[Tuple[datetime, datetime]]:
    if not isinstance(ev, dict) or ev.get("transparency") == "transparent":
        return None
    si = ev.get("start") or {}
    ei = ev.get("end") or {}
    if "date" in si:
        return None
    s_raw = si.get("dateTime")
    e_raw = (ei or {}).get("dateTime")
    if not s_raw or not e_raw:
        return None
    try:
        s_dt = datetime.fromisoformat(str(s_raw).replace("Z", "+00:00"))
        e_dt = datetime.fromisoformat(str(e_raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return s_dt, e_dt


def _bounds_from_personal_row(row: Dict[str, Any]) -> Optional[Tuple[datetime, datetime]]:
    if not isinstance(row, dict) or row.get("all_day"):
        return None
    s_raw = row.get("start_iso")
    if not s_raw:
        return None
    try:
        s_dt = datetime.fromisoformat(str(s_raw))
    except ValueError:
        return None
    e_raw = row.get("end_iso")
    if e_raw:
        try:
            e_dt = datetime.fromisoformat(str(e_raw))
        except ValueError:
            e_dt = s_dt + timedelta(hours=1)
    else:
        e_dt = s_dt + timedelta(hours=1)
    return s_dt, e_dt


def _parse_hhmm_env(key: str, default: str) -> time:
    raw = (os.environ.get(key) or default).strip()
    try:
        h, m = raw.split(":", 1)
        return time(int(h), int(m))
    except (ValueError, TypeError):
        return datetime.strptime(default, "%H:%M").time()


def _earliest_integrity_wake_floor_dt(anchor_local: datetime) -> datetime:
    """Earliest realistic local 'Integrity Wake' time (default 05:00). Override: COCKPIT_EARLIEST_INTEGRITY_WAKE."""
    loc = to_local(anchor_local)
    d = loc.date()
    tz = loc.tzinfo or local_tz()
    ft = _parse_hhmm_env("COCKPIT_EARLIEST_INTEGRITY_WAKE", "05:00")
    return datetime.combine(d, ft).replace(tzinfo=tz)


def _floored_integrity_wake(raw_wake: datetime, floor_dt: datetime, anchor_start: datetime) -> datetime:
    """Never show a wake time before ``floor_dt``; if that still lands on/after the anchor, pin to ``floor_dt``."""
    w = max(raw_wake, floor_dt)
    if w >= anchor_start:
        return floor_dt
    return w


def _clip_gaps_to_awake_window(
    gaps: List[Tuple[datetime, datetime]],
    day: date,
    awake_start: time,
    awake_end: time,
    min_gap: timedelta,
) -> List[Tuple[datetime, datetime]]:
    """Keep only portions of gaps inside [awake_start, awake_end] on ``day`` (local)."""
    tz = local_tz()
    win0 = datetime.combine(day, awake_start).replace(tzinfo=tz)
    win1 = datetime.combine(day, awake_end).replace(tzinfo=tz)
    out: List[Tuple[datetime, datetime]] = []
    for s, e in gaps:
        s = to_local(s)
        e = to_local(e)
        cs = max(s, win0)
        ce = min(e, win1)
        if ce > cs and (ce - cs) >= min_gap:
            out.append((cs, ce))
    return out


def compute_deep_work_kill_zones(
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
    day: date,
    *,
    min_gap: timedelta = timedelta(hours=2),
    awake_start: Optional[time] = None,
    awake_end: Optional[time] = None,
    extra_busy_spans: Optional[Sequence[Tuple[datetime, datetime]]] = None,
) -> List[Tuple[datetime, datetime]]:
    """
    Intervals within the local calendar day with no overlapping timed event
    where the free span length is >= min_gap (Deep Work \"Kill Zones\").
    Results are clipped to the awake window (default 05:00–19:30 local), configurable via
    COCKPIT_AWAKE_START / COCKPIT_AWAKE_END.

    ``extra_busy_spans`` optional additional busy intervals (e.g. work calendar from
    screenshot advisory) merged into occupancy before gaps are computed.
    """
    tz = local_tz()
    day_start = datetime.combine(day, time.min).replace(tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    spans: List[Tuple[datetime, datetime]] = []
    for ev in google_events or []:
        b = _bounds_from_google_event(ev)
        if b:
            spans.append(b)
    for row in personal_rows or []:
        b = _bounds_from_personal_row(row)
        if b:
            spans.append(b)
    for pair in extra_busy_spans or ():
        if not pair or len(pair) != 2:
            continue
        s0, e0 = pair
        spans.append((s0, e0))
    if not spans:
        if (day_end - day_start) >= min_gap:
            return [(day_start, day_end)]
        return []
    spans.sort(key=lambda x: x[0])
    merged: List[Tuple[datetime, datetime]] = []
    for s, e in spans:
        s = max(to_local(s), day_start)
        e = min(to_local(e), day_end)
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
    gaps: List[Tuple[datetime, datetime]] = []
    cursor = day_start
    for s, e in merged:
        if s > cursor:
            gap = s - cursor
            if gap >= min_gap:
                gaps.append((cursor, s))
        cursor = max(cursor, e)
    if day_end > cursor:
        gap = day_end - cursor
        if gap >= min_gap:
            gaps.append((cursor, day_end))
    a0 = awake_start if awake_start is not None else _parse_hhmm_env("COCKPIT_AWAKE_START", "05:00")
    a1 = awake_end if awake_end is not None else _parse_hhmm_env("COCKPIT_AWAKE_END", "19:30")
    return _clip_gaps_to_awake_window(gaps, day, a0, a1, min_gap)


def select_integrity_anchor(
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
    cfg: ChiefOfStaffConfig,
    *,
    runway_override: Optional[RunwayOverrideTriple] = None,
    gemini_chosen_index: Optional[int] = None,
) -> Optional[HardAnchor]:
    """
    Google-first: use Google timed anchors when any exist; else personal.
    When ``runway_override`` is set, match it against the merged chronological
    list first (so a personal lock still works if Google has other events).
    """
    g = _google_events_to_sorted_anchors(list(google_events or []))
    p = _personal_rows_to_sorted_anchors(list(personal_rows or []))
    merged = sorted(g + p, key=lambda x: x.start)

    if runway_override:
        iso, ttl, src = runway_override
        src_l = str(src).strip().lower()
        if src_l in ("google", "personal"):
            for a in merged:
                if _anchor_matches_runway_override(a, iso, ttl, src_l):
                    return a

    active = g if g else p
    if not active:
        return None
    return resolve_hard_anchor(active, cfg, gemini_chosen_index=gemini_chosen_index)


def pick_hard_anchor_from_google(
    events: List[Dict[str, Any]],
    cfg: ChiefOfStaffConfig,
    *,
    gemini_chosen_index: Optional[int] = None,
) -> Optional[HardAnchor]:
    g = _google_events_to_sorted_anchors(events)
    if not g:
        return None
    return resolve_hard_anchor(g, cfg, gemini_chosen_index=gemini_chosen_index)


def pick_hard_anchor_from_personal_rows(
    rows: List[Dict[str, Any]],
    cfg: ChiefOfStaffConfig,
    *,
    gemini_chosen_index: Optional[int] = None,
) -> Optional[HardAnchor]:
    p = _personal_rows_to_sorted_anchors(rows)
    if not p:
        return None
    return resolve_hard_anchor(p, cfg, gemini_chosen_index=gemini_chosen_index)


def _fmt_clock_safe(dt: datetime) -> str:
    dt = to_local(dt)
    return dt.strftime("%I:%M %p").lstrip("0").replace("  ", " ")


def build_day_readiness(
    anchor: Optional[HardAnchor],
    protocols: IdentityProtocols,
    default_wake: datetime,
    recovery_target: timedelta,
    last_bedtime: Optional[datetime],
) -> DayReadiness:
    default_wake = to_local(default_wake)
    if last_bedtime is not None:
        last_bedtime = to_local(last_bedtime)

    used_synthetic_anchor = False
    if anchor is None:
        tz = default_wake.tzinfo or local_tz()
        morning = datetime.combine(default_wake.date(), time(8, 0)).replace(tzinfo=tz)
        anchor = HardAnchor(
            start=morning,
            title=DEFAULT_MORNING_OPS_ANCHOR_TITLE,
            source="personal",
        )
        used_synthetic_anchor = True

    integrity: Optional[datetime] = None
    tact_integrity: Optional[datetime] = None
    tact_p = tactical_compression_protocols(protocols)

    a_start = to_local(anchor.start)
    raw_integrity = a_start - protocols.total_prep()
    raw_tact_integrity = a_start - tact_p.total_prep()
    floor_dt = _earliest_integrity_wake_floor_dt(a_start)
    integrity = _floored_integrity_wake(raw_integrity, floor_dt, a_start)
    tact_integrity = _floored_integrity_wake(raw_tact_integrity, floor_dt, a_start)
    prep_impossible_from_floor = max(raw_integrity, floor_dt) >= a_start

    runway_conflict = False
    if integrity is not None:
        runway_conflict = default_wake > integrity

    assert integrity is not None and tact_integrity is not None
    a_local = to_local(anchor.start)

    who = (os.environ.get("COCKPIT_OPERATOR_NAME") or "").strip() or "You"

    md = ""
    if used_synthetic_anchor:
        md += (
            "**Integrity Runway:** No timed calendar anchor matched — using **08:00 Morning Ops** "
            "as the default hard anchor for runway math.\n\n"
        )
    md += f"**Hard anchor:** **{_fmt_clock_safe(a_local)}** — {anchor.title}.\n\n"
    md += f"**Integrity Wake (end of full-protocol prep):** {_fmt_clock_safe(integrity)}.\n\n"
    md += f"**Tactical Compression wake:** {_fmt_clock_safe(tact_integrity)}.\n\n"
    if raw_integrity < floor_dt and not prep_impossible_from_floor:
        md += (
            f"*Integrity / Tactical times use a **{_fmt_clock_safe(floor_dt)}** earliest-wake floor "
            f"(unfloored math was {_fmt_clock_safe(raw_integrity)}). Override with `COCKPIT_EARLIEST_INTEGRITY_WAKE`.*\n\n"
        )
    if prep_impossible_from_floor:
        md += (
            f"**Warning:** The hard anchor ({_fmt_clock_safe(a_local)}) is earlier than a full protocol "
            f"allows when honoring the **{_fmt_clock_safe(floor_dt)}** earliest wake — move the commitment, "
            f"use Tactical Compression, or accept partial prep.\n\n"
        )

    if last_bedtime is not None:
        md += f"*Bedtime logged: {_fmt_clock_safe(last_bedtime)}.*\n\n"

    conflict_summary: Optional[str] = None
    if prep_impossible_from_floor:
        conflict_summary = (
            f"Anchor {_fmt_clock_safe(a_local)} precedes achievable full-protocol prep from earliest wake "
            f"({_fmt_clock_safe(floor_dt)})."
        )
    if runway_conflict:
        delta = default_wake - integrity
        mins = max(0, int(delta.total_seconds() // 60))
        cs = (
            f"Default wake ({_fmt_clock_safe(default_wake)}) is {mins} min after full-protocol "
            f"Integrity Wake ({_fmt_clock_safe(integrity)}). Adjust default wake or use Tactical Compression "
            f"({_fmt_clock_safe(tact_integrity)})."
        )
        conflict_summary = f"{conflict_summary} {cs}" if conflict_summary else cs
        md += (
            f"**Conflict:** Default wake ({_fmt_clock_safe(default_wake)}) is **{mins} min after** "
            f"full-protocol Integrity Wake. Adjust your default wake, or plan for **Tactical Compression** "
            f"({_fmt_clock_safe(tact_integrity)}).\n"
        )

    return DayReadiness(
        anchor=anchor,
        protocols=protocols,
        integrity_wake=integrity,
        default_wake=default_wake,
        last_bedtime=last_bedtime,
        recovery_target=recovery_target,
        runway_conflict=runway_conflict,
        tactical_protocols=tact_p,
        tactical_integrity_wake=tact_integrity,
        notification_markdown=md,
        operator_display=who,
        conflict_summary=conflict_summary,
    )


def parse_marker_csv(s: str) -> List[str]:
    if not s or not str(s).strip():
        return []
    return [x.strip() for x in re.split(r"[,;]", s) if x.strip()]


def _count_timed_google_events(events: Sequence[Dict[str, Any]]) -> int:
    n = 0
    for ev in events:
        if not isinstance(ev, dict):
            continue
        if ev.get("transparency") == "transparent":
            continue
        start_info = ev.get("start") or {}
        if "dateTime" in start_info and start_info.get("dateTime"):
            n += 1
    return n


def build_preparation_brief_markdown(
    day: date,
    google_events: Optional[List[Dict[str, Any]]],
    personal_rows: Optional[List[Dict[str, Any]]],
    cfg: ChiefOfStaffConfig,
    *,
    runway_override: Optional[RunwayOverrideTriple] = None,
    gemini_chosen_index: Optional[int] = None,
) -> str:
    """Forward Recon: neutral prep copy for a future calendar day (no wake/protocol shift math)."""
    lines: List[str] = [
        f"### Preparation Brief — {day.strftime('%A · %b %d, %Y')}",
        "_Forward Recon: preview commitments; execution and integrity shifts apply on the live day._",
        "",
    ]
    g_evs = list(google_events or [])
    p_rows = list(personal_rows or [])
    anchor = select_integrity_anchor(
        g_evs,
        p_rows,
        cfg,
        runway_override=runway_override,
        gemini_chosen_index=gemini_chosen_index,
    )

    if anchor is not None:
        a_local = to_local(anchor.start)
        src = "Google" if anchor.source == "google" else "Personal"
        lines.append(
            f"- **Lead timed anchor** ({src}): **{_fmt_clock_safe(a_local)}** — _{anchor.title}_"
        )
    else:
        lines.append("- **Lead timed anchor:** none detected yet — add timed blocks or connect calendars.")

    n_g = _count_timed_google_events(g_evs)
    n_p = sum(1 for r in p_rows if isinstance(r, dict) and not r.get("all_day") and r.get("start_iso"))
    lines.append(f"- **Timed events (Google):** {n_g} · **(Personal):** {n_p}")
    lines.append("")
    lines.append("Scan the Vanguard personal column and Google for load spikes; lock prep the night before.")
    return "\n".join(lines)


def anchors_revision_hash(anchors: List[HardAnchor]) -> str:
    """Cheap fingerprint for Gemini cache invalidation."""
    parts: List[str] = []
    for a in anchors:
        cid = a.calendar_event_id or ""
        parts.append(f"{a.start.isoformat()}|{a.title}|{a.source}|{cid}")
    return str(hash(tuple(parts)))
