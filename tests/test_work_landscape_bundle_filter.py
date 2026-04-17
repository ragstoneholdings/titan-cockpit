"""Load-time filtering of saved work screenshot rows (week view / column metadata)."""

from __future__ import annotations

from datetime import date

from api.services.work_advisory_store import filter_work_landscape_rows_for_bundle


def test_week_view_notes_drop_rows_without_column_date():
    day = date(2026, 4, 12)  # Sunday
    rows = [
        {
            "start_iso": "2026-04-12T10:00:00-05:00",
            "title": "Strategic Planning",
            "source": "google",
            "source_kind": "work_screenshot",
        },
    ]
    notes = "Visible: week of April 12-19, 2026, in a week view."
    out = filter_work_landscape_rows_for_bundle(day, rows, notes)
    assert out == []


def test_week_view_drops_wrong_column_weekday():
    day = date(2026, 4, 12)
    rows = [
        {
            "start_iso": "2026-04-12T10:00:00-05:00",
            "title": "Sunday block",
            "source": "google",
            "source_kind": "work_screenshot",
            "column_date_iso": "2026-04-12",
            "column_weekday": "Saturday",
        },
    ]
    notes = "week view"
    out = filter_work_landscape_rows_for_bundle(day, rows, notes)
    assert out == []


def test_week_view_keeps_matching_column_and_weekday():
    day = date(2026, 4, 12)
    rows = [
        {
            "start_iso": "2026-04-12T10:00:00-05:00",
            "title": "Sunday block",
            "source": "google",
            "source_kind": "work_screenshot",
            "column_date_iso": "2026-04-12",
            "column_weekday": "Sunday",
        },
    ]
    notes = "week view"
    out = filter_work_landscape_rows_for_bundle(day, rows, notes)
    assert len(out) == 1


def test_non_week_notes_keeps_legacy_rows_without_column():
    day = date(2026, 4, 14)
    rows = [
        {
            "start_iso": "2026-04-14T09:00:00-05:00",
            "title": "Standup",
            "source": "google",
            "source_kind": "work_screenshot",
        },
    ]
    notes = "Visible: day agenda for Apr 14."
    out = filter_work_landscape_rows_for_bundle(day, rows, notes)
    assert len(out) == 1
