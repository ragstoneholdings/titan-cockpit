"""Integrity consistency %, Sentry state, focus-shell flags, and Ops-block posture nudge signals."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Tuple

from chief_of_staff.planning import to_local

IntegritySentryState = Literal["NOMINAL", "WARNING", "CRITICAL"]


def compute_integrity_consistency_percent(
    *,
    protocol_confirmed_today: bool,
    sidebar_integrity: Dict[str, Any],
) -> float:
    """
    Trailing discipline visibility (0–100): 7d posture + 7d neck from sidebar_integrity,
    blended with today's full protocol confirmation (20%).
    """
    pd = sidebar_integrity.get("posture_days") or []
    nd = sidebar_integrity.get("neck_days") or []
    if not isinstance(pd, list):
        pd = []
    if not isinstance(nd, list):
        nd = []
    tail_p = [bool(x) for x in pd[-7:]]
    tail_n = [bool(x) for x in nd[-7:]]
    pr = sum(1 for x in tail_p if x) / max(len(tail_p), 1)
    nr = sum(1 for x in tail_n if x) / max(len(tail_n), 1)
    proto_w = 1.0 if protocol_confirmed_today else 0.0
    return round(100.0 * (0.4 * pr + 0.4 * nr + 0.2 * proto_w), 1)


def compute_integrity_sentry_state(
    *,
    identity_alert: bool,
    consistency_percent: float,
    protocol_confirmed_today: bool = False,
) -> IntegritySentryState:
    """Server-driven Sentry band; CRITICAL aligns with legacy identity_alert + severe drift.

    When today's full protocol is confirmed, do not mark CRITICAL for low *trailing* consistency
    alone (that is a discipline tail problem → WARNING). CRITICAL still applies for identity_alert
    or unconfirmed protocol with consistency under 50%.
    """
    consistency_critical = consistency_percent < 50.0 and not protocol_confirmed_today
    if identity_alert or consistency_critical:
        return "CRITICAL"
    if consistency_percent < 80.0:
        return "WARNING"
    return "NOMINAL"


def focus_shell_window_active(*, recon_day: date, now: Optional[datetime] = None) -> bool:
    """True when recon is today and local hour in [FOCUS_SHELL_START, FOCUS_SHELL_END) (defaults = briefing hours)."""
    if recon_day != date.today():
        return False
    now = now or datetime.now().astimezone()
    tz = now.tzinfo
    loc = now.astimezone(tz) if tz else now
    try:
        start = int(os.environ.get("FOCUS_SHELL_START_HOUR", os.environ.get("BRIEFING_ACTIVE_START_HOUR", "8")) or 8)
    except ValueError:
        start = 8
    try:
        end = int(os.environ.get("FOCUS_SHELL_END_HOUR", os.environ.get("BRIEFING_ACTIVE_END_HOUR", "11")) or 11)
    except ValueError:
        end = 11
    if end <= start:
        end = min(23, start + 1)
    return start <= loc.hour < end


def _hour_window_active(
    *,
    recon_day: date,
    start_hour: int,
    end_hour: int,
    now: Optional[datetime] = None,
) -> bool:
    if recon_day != date.today():
        return False
    now = now or datetime.now().astimezone()
    tz = now.tzinfo
    loc = now.astimezone(tz) if tz else now
    if end_hour <= start_hour:
        end_hour = min(23, start_hour + 1)
    return start_hour <= loc.hour < end_hour


def air_gap_window_active(*, recon_day: date, now: Optional[datetime] = None) -> bool:
    """60-minute-style deep-work protection band (default 08:00–09:00 local). Signal-only on web."""
    try:
        sh = int(os.environ.get("AIR_GAP_START_HOUR", "8") or 8)
    except ValueError:
        sh = 8
    try:
        eh = int(os.environ.get("AIR_GAP_END_HOUR", "9") or 9)
    except ValueError:
        eh = 9
    return _hour_window_active(recon_day=recon_day, start_hour=sh, end_hour=eh, now=now)


def midday_shield_window_active(*, recon_day: date, now: Optional[datetime] = None) -> bool:
    """Midday Slack/email windshield + posture (default 12:00–13:00 local). Signal-only on web."""
    try:
        sh = int(os.environ.get("MIDDAY_SHIELD_START_HOUR", "12") or 12)
    except ValueError:
        sh = 12
    try:
        eh = int(os.environ.get("MIDDAY_SHIELD_END_HOUR", "13") or 13)
    except ValueError:
        eh = 13
    return _hour_window_active(recon_day=recon_day, start_hour=sh, end_hour=eh, now=now)


def identity_alignment_window_active(*, recon_day: date, now: Optional[datetime] = None) -> bool:
    """07:00 identity alignment / inbox slaughter band (default 07:00–08:00 local)."""
    try:
        sh = int(os.environ.get("IDENTITY_ALIGNMENT_START_HOUR", "7") or 7)
    except ValueError:
        sh = 7
    try:
        eh = int(os.environ.get("IDENTITY_ALIGNMENT_END_HOUR", "8") or 8)
    except ValueError:
        eh = 8
    return _hour_window_active(recon_day=recon_day, start_hour=sh, end_hour=eh, now=now)


def _parse_iso_dt(iso: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ops_nudge_substrings() -> List[str]:
    raw = (os.environ.get("COCKPIT_OPS_POSTURE_NUDGE_SUBSTRINGS") or "").strip()
    if raw:
        return [x.strip().lower() for x in raw.split(",") if x.strip()]
    return ["sync", "standup", "qbr", "1:1", "google", "ops", "review"]


def compute_ops_posture_nudge(
    *,
    recon_day: date,
    landscape: List[Dict[str, Any]],
    now: Optional[datetime] = None,
) -> Tuple[bool, str]:
    """
    True when 'now' falls inside a calendar block that looks like Google / corporate ops,
    so the UI can show a symmetry & posture reminder (today only).
    """
    if recon_day != date.today():
        return False, ""
    now = now or datetime.now().astimezone()
    tz = now.tzinfo
    if tz is None:
        return False, ""
    now_l = now.astimezone(tz)
    hints = _ops_nudge_substrings()
    for row in landscape:
        if not isinstance(row, dict):
            continue
        st = str(row.get("start_iso") or "").strip()
        title = str(row.get("title") or "").lower()
        sk = str(row.get("source_kind") or "")
        src = str(row.get("source") or "")
        if not st:
            continue
        if sk != "personal_google" and sk != "work_screenshot":
            continue
        end_iso = str(row.get("end_iso") or "").strip()
        t0 = _parse_iso_dt(st)
        if t0 is None:
            continue
        t1 = _parse_iso_dt(end_iso) if end_iso else t0 + timedelta(hours=1)
        if t1 <= t0:
            t1 = t0 + timedelta(hours=1)
        t0l = to_local(t0)
        t1l = to_local(t1)
        if not (t0l <= now_l < t1l):
            continue
        blob = title + " " + src.lower()
        if sk == "work_screenshot" or src == "google" or any(h in blob for h in hints):
            return True, "Symmetry & posture: hold the frame through this ops block."
    return False, ""


def sacred_preserve_substrings() -> List[str]:
    raw = (os.environ.get("JANITOR_SACRED_SUBSTRINGS") or "").strip()
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def task_blob_matches_sacred(content: str, description: str) -> bool:
    blob = f"{content} {description}".lower()
    for s in sacred_preserve_substrings():
        if s and s in blob:
            return True
    return False


def count_sacred_overdue_tasks(by_id: Dict[str, Any], recon_day: date) -> int:
    """Open tasks matching sacred substrings with due_date strictly before recon_day."""
    if not sacred_preserve_substrings():
        return 0
    dk = recon_day.isoformat()
    n = 0
    for t in by_id.values():
        if not isinstance(t, dict):
            continue
        c = str(t.get("content") or "")
        d = str(t.get("description") or "")
        if not task_blob_matches_sacred(c, d):
            continue
        due = str(t.get("due_date") or "").strip()[:10]
        if due and due < dk:
            n += 1
    return n
