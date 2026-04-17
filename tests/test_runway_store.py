"""runway_overrides.json persistence."""

from datetime import date

import runway_store
from runway_store import RunwayDayOverride, clear_runway_override_for_day, load_runway_override_for_day, save_runway_override_for_day


def test_save_clear_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(runway_store, "RUNWAY_OVERRIDES_PATH", tmp_path / "runway_overrides.json")
    d = date(2026, 6, 15)
    assert load_runway_override_for_day(d) is None
    save_runway_override_for_day(
        d,
        RunwayDayOverride(
            start_iso="2026-06-15T09:00:00-07:00",
            title="Board",
            source="google",
        ),
    )
    o = load_runway_override_for_day(d)
    assert o is not None
    assert o.title == "Board"
    clear_runway_override_for_day(d)
    assert load_runway_override_for_day(d) is None
