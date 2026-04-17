"""Server-side alignment of column_date_iso with column_weekday for week-view screenshots."""

from datetime import date

from api.services.calendar_advisory_gemini import (
    _events_imply_distinct_weekday_columns,
    _normalize_week_column_dates,
    _weekday_date_in_iso_week,
)


def test_weekday_date_in_iso_week_tuesday_from_monday_recon():
    mon = date(2026, 4, 13)
    assert mon.weekday() == 0
    tue = _weekday_date_in_iso_week(mon, "Tuesday")
    assert tue == date(2026, 4, 14)


def test_events_imply_distinct_weekday_columns():
    ev = [
        {"column_weekday": "Monday", "column_date_iso": "2026-04-13"},
        {"column_weekday": "Tuesday", "column_date_iso": "2026-04-13"},
    ]
    assert _events_imply_distinct_weekday_columns(ev) is True


def test_normalize_same_iso_distinct_weekdays_splits_columns():
    recon = date(2026, 4, 13)
    events = [
        {
            "title": "A",
            "start_local_guess": "09:00",
            "column_date_iso": "2026-04-13",
            "column_weekday": "Monday",
        },
        {
            "title": "B",
            "start_local_guess": "10:00",
            "column_date_iso": "2026-04-13",
            "column_weekday": "Tuesday",
        },
        {
            "title": "C",
            "start_local_guess": "11:00",
            "column_date_iso": "2026-04-13",
            "column_weekday": "Wednesday",
        },
    ]
    out, n = _normalize_week_column_dates(recon, events, week_viewish=True)
    # Monday row already had the correct ISO date; Tue/Wed are rewritten.
    assert n == 2
    cols = {str(e["column_date_iso"])[:10] for e in out}
    assert cols == {"2026-04-13", "2026-04-14", "2026-04-15"}


def test_normalize_mismatch_weekday_vs_date():
    recon = date(2026, 4, 14)
    events = [
        {
            "title": "Meet",
            "start_local_guess": "11:00",
            "column_date_iso": "2026-04-13",
            "column_weekday": "Tuesday",
        },
    ]
    out, n = _normalize_week_column_dates(recon, events, week_viewish=False)
    assert n == 1
    assert out[0]["column_date_iso"].startswith("2026-04-14")
