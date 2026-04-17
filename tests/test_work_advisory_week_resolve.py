"""Week-view work advisory: rows keyed under one day still load for Tue–Fri recon."""

import json
from datetime import date

from api.services import work_advisory_store as wa


def test_work_calendar_week_gap_hint_when_all_rows_one_column(tmp_path, monkeypatch):
    p = tmp_path / "w.json"
    monkeypatch.setattr(wa, "WORK_CALENDAR_ADVISORY_PATH", p)
    mon = date(2026, 1, 5)
    tue = date(2026, 1, 6)
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "by_date": {
                    mon.isoformat(): {
                        "saved_at": "2026-01-05T12:00:00+00:00",
                        "notes": "Visible: week of Jan 5-11",
                        "landscape_rows": [
                            {
                                "start_iso": "2026-01-05T09:00:00",
                                "title": "A",
                                "column_date_iso": mon.isoformat(),
                            },
                            {
                                "start_iso": "2026-01-05T10:00:00",
                                "title": "B",
                                "column_date_iso": mon.isoformat(),
                            },
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    hint = wa.work_calendar_week_gap_hint(tue, work_screenshot_row_count=0)
    assert mon.isoformat() in hint
    assert tue.isoformat() in hint
    assert wa.work_calendar_week_gap_hint(tue, work_screenshot_row_count=1) == ""


def test_load_landscape_rows_from_sibling_bundle_same_iso_week(tmp_path, monkeypatch):
    p = tmp_path / "w.json"
    monkeypatch.setattr(wa, "WORK_CALENDAR_ADVISORY_PATH", p)
    mon = date(2026, 1, 5)
    assert mon.weekday() == 0
    tue = date(2026, 1, 6)
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "by_date": {
                    mon.isoformat(): {
                        "saved_at": "2026-01-05T18:00:00+00:00",
                        "notes": "Visible: week of Jan 5-11 (work week view)",
                        "landscape_rows": [
                            {
                                "start_iso": "2026-01-06T10:00:00+00:00",
                                "title": "Ops standup",
                                "source_kind": "work_screenshot",
                                "column_date_iso": tue.isoformat(),
                            },
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rows = wa.load_landscape_rows_for_day(tue)
    assert len(rows) == 1
    assert rows[0]["title"] == "Ops standup"
    meta = wa.load_advisory_meta_for_day(tue)
    assert meta is not None
    assert "week" in (meta.get("notes") or "").lower()


def test_load_advisory_meta_direct_day_without_rows(tmp_path, monkeypatch):
    """Day-only coaching saved under that key still returns meta."""
    p = tmp_path / "w.json"
    monkeypatch.setattr(wa, "WORK_CALENDAR_ADVISORY_PATH", p)
    d = date(2026, 2, 2)
    p.write_text(
        json.dumps(
            {
                "version": 1,
                "by_date": {
                    d.isoformat(): {
                        "saved_at": "2026-02-02T12:00:00+00:00",
                        "notes": "Single-day agenda",
                        "time_coaching": "Pack deep work before noon.",
                        "landscape_rows": [],
                    }
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert wa.load_landscape_rows_for_day(d) == []
    meta = wa.load_advisory_meta_for_day(d)
    assert meta is not None
    assert "deep work" in (meta.get("time_coaching") or "").lower()
