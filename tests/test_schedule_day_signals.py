"""Tests for schedule_day_signals (intake-aligned conflict + meeting load)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from api.services.schedule_day_signals import compute_schedule_day_signals


def _tz():
    return datetime.now().astimezone().tzinfo


def test_overlap_two_google_events():
    tz = _tz()
    d = date(2026, 6, 10)
    g = [
        {
            "summary": "A",
            "start": {"dateTime": datetime(2026, 6, 10, 9, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 10, 10, 0, tzinfo=tz).isoformat()},
        },
        {
            "summary": "B",
            "start": {"dateTime": datetime(2026, 6, 10, 9, 30, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 10, 10, 30, tzinfo=tz).isoformat()},
        },
    ]
    sig = compute_schedule_day_signals(d, g, [], [])
    assert sig["overlap_count"] >= 1
    assert "overlap" in sig["summary_line"].lower()
    assert sig.get("overlaps")
    assert all(str(ov.get("id") or "") for ov in sig["overlaps"])
    assert not any(it.get("id") == "overlap_winner" for it in (sig.get("suggestion_items") or []))
    items = sig.get("suggestion_items") or []
    assert items and items[0].get("id") == "overlap_resolution_hint"
    assert len(items[0].get("options") or []) >= 3


def test_meeting_load_warning_at_five_hours_union():
    tz = _tz()
    d = date(2026, 6, 11)  # Thursday
    g = [
        {
            "summary": f"M{i}",
            "start": {"dateTime": datetime(2026, 6, 11, 8 + i, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 11, 8 + i, 50, tzinfo=tz).isoformat()},
        }
        for i in range(6)
    ]
    sig = compute_schedule_day_signals(d, g, [], [])
    assert sig["meeting_load_minutes"] >= 300
    assert sig["meeting_load_warning"] is True


def test_weekend_suppresses_meeting_load_warning():
    """Saturday/Sunday: still count blocked minutes but do not set meeting_load_warning."""
    tz = _tz()
    d = date(2026, 6, 13)  # Saturday
    g = [
        {
            "summary": f"M{i}",
            "start": {"dateTime": datetime(2026, 6, 13, 8 + i, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 13, 8 + i, 50, tzinfo=tz).isoformat()},
        }
        for i in range(6)
    ]
    sig = compute_schedule_day_signals(d, g, [], [])
    assert sig["meeting_load_minutes"] >= 300
    assert sig["meeting_load_warning"] is False


def test_summary_line_avoids_meeting_ish_phrase():
    tz = _tz()
    d = date(2026, 6, 11)
    g = [
        {
            "summary": "Block",
            "start": {"dateTime": datetime(2026, 6, 11, 9, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 11, 15, 0, tzinfo=tz).isoformat()},
        },
    ]
    sig = compute_schedule_day_signals(d, g, [], [])
    low = sig["summary_line"].lower()
    assert "meeting-ish" not in low
    assert "feels heavy" not in low


def test_schedule_meeting_exclude_substrings_env(monkeypatch):
    tz = _tz()
    d = date(2026, 6, 15)
    monkeypatch.setenv("SCHEDULE_MEETING_EXCLUDE_SUBSTRINGS", "deep work buffer")
    g = [
        {
            "summary": "Deep work buffer",
            "start": {"dateTime": datetime(2026, 6, 15, 10, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 15, 16, 0, tzinfo=tz).isoformat()},
        },
    ]
    sig = compute_schedule_day_signals(d, g, [], [])
    assert sig["meeting_load_minutes"] == 0


def test_rdw_excluded_from_meeting_load():
    tz = _tz()
    d = date(2026, 6, 12)
    g = [
        {
            "summary": "RDW block",
            "start": {"dateTime": datetime(2026, 6, 12, 10, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 12, 16, 0, tzinfo=tz).isoformat()},
        },
    ]
    sig = compute_schedule_day_signals(d, g, [], [])
    assert sig["meeting_load_minutes"] == 0


def test_work_screenshot_overlaps_personal_flag():
    tz = _tz()
    d = date(2026, 6, 13)
    p = [
        {
            "all_day": False,
            "start_iso": datetime(2026, 6, 13, 11, 0, tzinfo=tz).isoformat(),
            "end_iso": datetime(2026, 6, 13, 12, 0, tzinfo=tz).isoformat(),
            "title": "Gym",
        }
    ]
    landscape = [
        {
            "start_iso": datetime(2026, 6, 13, 11, 15, tzinfo=tz).isoformat(),
            "title": "Staff sync",
            "source": "google",
            "source_kind": "work_screenshot",
        }
    ]
    sig = compute_schedule_day_signals(d, [], p, landscape)
    assert sig["source_flags"], "expected work vs personal overlap flag"


def test_extra_busy_spans_shrink_kill_zone_gap():
    from chief_of_staff.planning import compute_deep_work_kill_zones

    tz = _tz()
    d = date(2026, 6, 14)
    g = [
        {
            "summary": "Early",
            "start": {"dateTime": datetime(2026, 6, 14, 9, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 14, 10, 0, tzinfo=tz).isoformat()},
        },
        {
            "summary": "Late",
            "start": {"dateTime": datetime(2026, 6, 14, 14, 0, tzinfo=tz).isoformat()},
            "end": {"dateTime": datetime(2026, 6, 14, 15, 0, tzinfo=tz).isoformat()},
        },
    ]
    extra = [
        (
            datetime(2026, 6, 14, 12, 0, tzinfo=tz),
            datetime(2026, 6, 14, 13, 0, tzinfo=tz),
        )
    ]
    z_plain = compute_deep_work_kill_zones(g, [], d, min_gap=timedelta(hours=2))
    z_extra = compute_deep_work_kill_zones(g, [], d, min_gap=timedelta(hours=2), extra_busy_spans=extra)
    assert len(z_extra) >= len(z_plain)
    # Middle gap 10–14 is 4h; splitting with 12–13 busy may still yield one ≥2h gap depending on clip;
    # at minimum extra span consumes an hour from a gap.
    total_plain = sum((b - a).total_seconds() for a, b in z_plain)
    total_extra = sum((b - a).total_seconds() for a, b in z_extra)
    assert total_extra <= total_plain + 1e-6
