"""Weekly work calendar helpers."""

from datetime import date, timedelta

from command_center_v2 import (
    expected_week_day_keys,
    normalize_work_week_hours,
    week_load_summary_line,
    week_start_monday,
)


def test_week_start_monday():
    d = date(2026, 4, 15)  # Wednesday
    assert week_start_monday(d) == date(2026, 4, 13)


def test_expected_week_day_keys_seven_days():
    mon = date(2026, 4, 13)
    keys = expected_week_day_keys(mon)
    assert len(keys) == 7
    assert keys[0] == "2026-04-13"
    assert keys[-1] == "2026-04-19"


def test_normalize_merges_and_caps():
    mon = date(2026, 4, 13)
    raw = {
        "2026-04-13": 3.0,
        "2026-04-14": 99.0,
        "bad": 1.0,
    }
    out = normalize_work_week_hours(raw, mon)
    assert out["2026-04-13"] == 3.0
    assert out["2026-04-14"] == 24.0
    assert out["2026-04-19"] == 0.0


def test_week_load_summary_nonempty():
    mon = date(2026, 4, 13)
    h = { (mon + timedelta(days=i)).isoformat(): float(i) for i in range(7) }
    s = week_load_summary_line(h, mon)
    assert "heaviest" in s and "lightest" in s
