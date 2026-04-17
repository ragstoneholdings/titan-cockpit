"""Unit tests for Integrity Runway planning."""

from datetime import date, datetime, timedelta

from chief_of_staff.models import ChiefOfStaffConfig, HardAnchor, IdentityProtocols
from chief_of_staff.planning import (
    build_day_readiness,
    compute_deep_work_kill_zones,
    pick_hard_anchor_from_google,
    resolve_hard_anchor,
    select_integrity_anchor,
    tactical_compression_protocols,
)


def test_tactical_compression_shortens_stack():
    p = IdentityProtocols(
        posture=timedelta(minutes=20),
        neck=timedelta(minutes=10),
        morning_ops=timedelta(minutes=30),
    )
    t = tactical_compression_protocols(p)
    assert t.morning_ops == timedelta(0)
    assert t.posture == timedelta(minutes=10)
    assert t.neck == timedelta(minutes=5)


def test_pick_google_prefers_marker():
    cfg = ChiefOfStaffConfig(hard_title_markers=["HARD"])
    events = [
        {
            "summary": "Soft standup",
            "start": {"dateTime": "2026-04-10T09:00:00-07:00"},
            "transparency": None,
        },
        {
            "summary": "HARD — Board",
            "start": {"dateTime": "2026-04-10T08:00:00-07:00"},
            "transparency": None,
        },
    ]
    a = pick_hard_anchor_from_google(events, cfg)
    assert a is not None
    assert "Board" in a.title


def test_integrity_wake_floored_to_earliest_realistic_time():
    """Raw anchor-minus-prep must never land before 05:00 local (COCKPIT_EARLIEST_INTEGRITY_WAKE)."""
    tz = datetime.now().astimezone().tzinfo
    d = date(2026, 4, 11)
    anchor = HardAnchor(
        start=datetime(2026, 4, 11, 6, 0, tzinfo=tz),
        title="Standup",
        source="google",
    )
    p = IdentityProtocols(
        posture=timedelta(hours=2),
        neck=timedelta(hours=1),
        morning_ops=timedelta(hours=1),
    )
    dw = datetime.combine(d, datetime.strptime("07:00", "%H:%M").time()).replace(tzinfo=tz)
    r = build_day_readiness(anchor, p, dw, timedelta(hours=7.5), None)
    assert r.integrity_wake is not None
    assert r.integrity_wake.hour >= 5
    assert r.tactical_integrity_wake is not None
    assert r.tactical_integrity_wake.hour >= 5
    assert "05:00" in r.notification_markdown or "5:00" in r.notification_markdown


def test_build_day_readiness_no_anchor():
    tz = datetime.now().astimezone().tzinfo
    dw = datetime.combine(date.today(), datetime.strptime("06:30", "%H:%M").time()).replace(tzinfo=tz)
    p = IdentityProtocols(
        posture=timedelta(minutes=15),
        neck=timedelta(minutes=10),
        morning_ops=timedelta(minutes=15),
    )
    r = build_day_readiness(None, p, dw, timedelta(hours=7.5), None)
    assert r.integrity_wake is not None
    assert "08:00" in r.notification_markdown or "default" in r.notification_markdown.lower()


def test_pick_google_prefers_heuristic_keyword_over_first_timed():
    cfg = ChiefOfStaffConfig(hard_title_markers=[])
    events = [
        {
            "summary": "Deep work block",
            "start": {"dateTime": "2026-04-10T08:00:00-07:00"},
            "transparency": None,
        },
        {
            "summary": "Vendor sync",
            "start": {"dateTime": "2026-04-10T10:00:00-07:00"},
            "transparency": None,
        },
    ]
    a = pick_hard_anchor_from_google(events, cfg)
    assert a is not None
    assert "sync" in a.title.lower()


def test_pick_google_named_default_title():
    cfg = ChiefOfStaffConfig(hard_title_markers=[])
    events = [
        {
            "summary": "Loose block",
            "start": {"dateTime": "2026-04-10T07:00:00-07:00"},
            "transparency": None,
        },
        {
            "summary": "Morning Ops and Alignment",
            "start": {"dateTime": "2026-04-10T09:00:00-07:00"},
            "transparency": None,
        },
    ]
    a = pick_hard_anchor_from_google(events, cfg)
    assert a is not None
    assert "Morning Ops" in a.title


def test_invalid_gemini_index_skips_to_heuristics():
    cfg = ChiefOfStaffConfig(hard_title_markers=[])
    tz = datetime.now().astimezone().tzinfo
    anchors = [
        HardAnchor(
            start=datetime(2026, 4, 10, 8, 0, tzinfo=tz),
            title="Block",
            source="google",
        ),
        HardAnchor(
            start=datetime(2026, 4, 10, 9, 0, tzinfo=tz),
            title="Ragstone check-in",
            source="google",
        ),
    ]
    a = resolve_hard_anchor(anchors, cfg, gemini_chosen_index=99)
    assert "Ragstone" in a.title


def test_deep_work_kill_zones_excludes_sleep_window():
    """Gaps are clipped to awake hours (default 05:00–19:30); overnight free time does not count."""
    tz = datetime.now().astimezone().tzinfo
    d = date(2026, 4, 11)
    # One meeting 9–10; huge "free" gap 00:00–09:00 should clip to 05:00–09:00 (4h) for kill zone
    g = [
        {
            "summary": "A",
            "start": {"dateTime": datetime(2026, 4, 11, 9, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 4, 11, 10, 0, tzinfo=tz).isoformat()},
        },
    ]
    zones = compute_deep_work_kill_zones(g, [], d, min_gap=timedelta(hours=2))
    assert zones
    gap_start, gap_end = zones[0]
    assert gap_start.hour >= 5
    assert gap_end.hour <= 19 or (gap_end.hour == 19 and gap_end.minute <= 30)


def test_deep_work_kill_zones_finds_gap():
    tz = datetime.now().astimezone().tzinfo
    d = date(2026, 4, 11)
    g = [
        {
            "summary": "A",
            "start": {"dateTime": datetime(2026, 4, 11, 9, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 4, 11, 10, 0, tzinfo=tz).isoformat()},
        },
        {
            "summary": "B",
            "start": {"dateTime": datetime(2026, 4, 11, 14, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 4, 11, 15, 0, tzinfo=tz).isoformat()},
        },
    ]
    zones = compute_deep_work_kill_zones(g, [], d)
    assert len(zones) >= 1
    gap_start, gap_end = zones[0]
    assert (gap_end - gap_start) >= timedelta(hours=2)


def test_select_integrity_anchor_runway_override_personal_with_google_present():
    cfg = ChiefOfStaffConfig(hard_title_markers=[])
    google = [
        {
            "summary": "Corporate standup",
            "start": {"dateTime": "2026-04-10T10:00:00-07:00"},
            "transparency": None,
        },
    ]
    personal = [
        {
            "title": "Vanguard Bridge",
            "start_iso": "2026-04-10T08:00:00-07:00",
            "all_day": False,
        },
    ]
    ov = ("2026-04-10T08:00:00-07:00", "Vanguard Bridge", "personal")
    a = select_integrity_anchor(google, personal, cfg, runway_override=ov)
    assert a is not None
    assert a.source == "personal"
    assert "Vanguard" in a.title
