"""Golden path day timeline rows (end_iso, badges)."""

from api.services.cockpit_snapshot import _build_golden_path_timeline


def test_timeline_includes_end_iso_from_row_end():
    landscape = [
        {
            "start_iso": "2026-04-11T10:00:00-07:00",
            "end_iso": "2026-04-11T11:00:00-07:00",
            "title": "Block A",
            "source": "cal",
            "source_kind": "personal_google",
        },
    ]
    rows = _build_golden_path_timeline(landscape, "", {})
    assert len(rows) == 1
    assert rows[0]["start_iso"] == landscape[0]["start_iso"]
    assert rows[0]["end_iso"] == landscape[0]["end_iso"]


def test_timeline_end_iso_fallback_start_plus_one_hour():
    landscape = [
        {
            "start_iso": "2026-04-11T14:30:00+00:00",
            "title": "No end",
            "source": "cal",
            "source_kind": "personal_ics",
        },
    ]
    rows = _build_golden_path_timeline(landscape, "", {})
    assert len(rows) == 1
    assert rows[0]["end_iso"] == "2026-04-11T15:30:00+00:00"
