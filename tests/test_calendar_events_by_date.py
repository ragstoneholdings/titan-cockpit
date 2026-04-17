"""advisory_events_by_date bucketed JSON → per-row column_date_iso."""

from datetime import date

from api.services.calendar_advisory_gemini import (
    _apply_advisory_events_by_date,
    _flatten_advisory_events_by_date,
)


def test_flatten_coerces_single_object_to_list():
    recon = date(2026, 4, 13)
    raw = {"2026-04-14": {"title": "solo", "start_local_guess": "10:00"}}
    out = _flatten_advisory_events_by_date(raw, recon)
    assert len(out) == 1
    assert out[0]["title"] == "solo"
    assert out[0]["column_date_iso"] == "2026-04-14"


def test_flatten_by_date_sets_column_iso_and_weekday():
    recon = date(2026, 4, 13)
    raw = {
        "2026-04-13": [{"title": "Mon meet", "start_local_guess": "09:00", "confidence": 0.9}],
        "2026-04-14": [{"title": "Tue meet", "start_local_guess": "10:00", "confidence": 0.9}],
    }
    out = _flatten_advisory_events_by_date(raw, recon)
    assert len(out) == 2
    assert out[0]["column_date_iso"] == "2026-04-13"
    assert out[0]["column_weekday"] == "Monday"
    assert out[1]["column_date_iso"] == "2026-04-14"
    assert out[1]["column_weekday"] == "Tuesday"


def test_flatten_keeps_keys_outside_iso_week_filter_applies_later():
    """Flatten does not drop by-date keys; same-ISO-week filter runs in analyze pipeline."""
    recon = date(2026, 4, 14)
    raw = {
        "2026-04-07": [{"title": "old", "start_local_guess": "09:00"}],
    }
    out = _flatten_advisory_events_by_date(raw, recon)
    assert len(out) == 1
    assert out[0]["column_date_iso"] == "2026-04-07"


def test_apply_merges_into_advisory_events():
    recon = date(2026, 4, 13)
    data = {
        "recon_day": recon.isoformat(),
        "advisory_events": [{"title": "ignored", "column_date_iso": "2026-04-13"}],
        "advisory_events_by_date": {
            "2026-04-14": [{"title": "Tue only", "start_local_guess": "11:00"}],
        },
    }
    assert _apply_advisory_events_by_date(data, recon) is True
    assert len(data["advisory_events"]) == 2
    titles = {str(e.get("title")) for e in data["advisory_events"]}
    assert titles == {"Tue only", "ignored"}


def test_apply_dedupes_bucket_over_flat():
    recon = date(2026, 4, 13)
    data = {
        "recon_day": recon.isoformat(),
        "advisory_events": [{"title": "Dup", "start_local_guess": "09:00", "column_date_iso": "2026-04-13"}],
        "advisory_events_by_date": {
            "2026-04-13": [{"title": "Dup", "start_local_guess": "09:00"}],
        },
    }
    assert _apply_advisory_events_by_date(data, recon) is True
    assert len(data["advisory_events"]) == 1
