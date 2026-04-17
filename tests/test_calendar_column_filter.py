"""column_date_iso / column_weekday filtering for work screenshot advisory."""

from __future__ import annotations

from datetime import date

from api.services.calendar_advisory_gemini import (
    _filter_advisory_events_for_recon_day,
    _filter_advisory_events_same_iso_week,
)


def test_filter_drops_mismatched_column_date():
    recon = date(2026, 4, 12)
    events = [
        {"title": "Monday column", "start_local_guess": "10:00", "column_date_iso": "2026-04-13"},
        {"title": "Sunday column", "start_local_guess": "11:00", "column_date_iso": "2026-04-12"},
    ]
    kept, dropped = _filter_advisory_events_for_recon_day(recon, events)
    assert dropped == 1
    assert len(kept) == 1
    assert kept[0]["title"] == "Sunday column"


def test_filter_drops_mismatched_weekday():
    recon = date(2026, 4, 12)  # Sunday
    events = [
        {"title": "Wrong weekday", "start_local_guess": "10:00", "column_weekday": "Monday"},
        {"title": "Right weekday", "start_local_guess": "11:00", "column_weekday": "Sunday"},
    ]
    kept, dropped = _filter_advisory_events_for_recon_day(recon, events)
    assert dropped == 1
    assert kept[0]["title"] == "Right weekday"


def test_filter_keeps_when_metadata_absent():
    recon = date(2026, 4, 12)
    events = [{"title": "Legacy", "start_local_guess": "10:00"}]
    kept, dropped = _filter_advisory_events_for_recon_day(recon, events)
    assert dropped == 0
    assert kept == events


def test_same_week_filter_keeps_other_weekdays():
    """Week bundle anchored on Monday keeps Tue–Sun columns in the same ISO week."""
    mon = date(2026, 4, 13)
    events = [
        {"title": "Mon", "column_date_iso": "2026-04-13"},
        {"title": "Tue", "column_date_iso": "2026-04-14"},
        {"title": "Next week", "column_date_iso": "2026-04-20"},
        {"title": "No col"},
    ]
    kept, dropped = _filter_advisory_events_same_iso_week(mon, events)
    titles = {e["title"] for e in kept}
    assert titles == {"Mon", "Tue"}
    assert dropped == 2


def test_same_week_truncates_datetime_suffix_in_column():
    mon = date(2026, 4, 13)
    events = [{"title": "Tue", "column_date_iso": "2026-04-14T00:00:00"}]
    kept, dropped = _filter_advisory_events_same_iso_week(mon, events)
    assert dropped == 0
    assert len(kept) == 1
