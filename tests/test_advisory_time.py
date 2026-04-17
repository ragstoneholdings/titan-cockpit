"""Unit tests for screenshot advisory time normalization."""

from datetime import date

from api.services.advisory_time import (
    landscape_rows_from_advisory_events,
    local_iso_from_day_and_time_guess,
)


def test_local_iso_24h():
    d = date(2026, 4, 11)
    iso = local_iso_from_day_and_time_guess(d, "09:30")
    assert iso is not None
    assert "09:30" in iso or "T09:30" in iso.replace("Z", "")


def test_local_iso_am_pm():
    d = date(2026, 4, 11)
    iso = local_iso_from_day_and_time_guess(d, "5:00 PM")
    assert iso is not None


def test_landscape_rows_from_events():
    d = date(2026, 4, 11)
    rows = landscape_rows_from_advisory_events(
        d,
        [{"title": "Standup", "start_local_guess": "10:00", "confidence": 0.9}],
    )
    assert len(rows) == 1
    assert rows[0]["source_kind"] == "work_screenshot"
    assert rows[0]["title"] == "Standup"


def test_landscape_rows_passthrough_column_metadata():
    d = date(2026, 4, 12)
    rows = landscape_rows_from_advisory_events(
        d,
        [
            {
                "title": "Block",
                "start_local_guess": "10:00",
                "column_date_iso": "2026-04-12",
                "column_weekday": "Sunday",
            }
        ],
    )
    assert rows[0].get("column_date_iso") == "2026-04-12"
    assert rows[0].get("column_weekday") == "Sunday"


def test_landscape_rows_use_column_date_for_start_iso():
    mon = date(2026, 4, 13)
    rows = landscape_rows_from_advisory_events(
        mon,
        [
            {
                "title": "Tuesday block",
                "start_local_guess": "14:00",
                "column_date_iso": "2026-04-14",
                "column_weekday": "Tuesday",
            }
        ],
    )
    assert len(rows) == 1
    assert "2026-04-14" in rows[0]["start_iso"]
    assert rows[0]["title"] == "Tuesday block"
