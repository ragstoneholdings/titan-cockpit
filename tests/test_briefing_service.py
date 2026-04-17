"""Morning brief deterministic payload."""

from datetime import date, datetime

from api.services import briefing_service, morning_brief_store


def test_briefing_window_respects_env(monkeypatch):
    monkeypatch.setenv("BRIEFING_ACTIVE_START_HOUR", "9")
    monkeypatch.setenv("BRIEFING_ACTIVE_END_HOUR", "12")
    assert briefing_service.briefing_active_hour_range() == (9, 12)
    assert briefing_service.briefing_window_active(datetime(2026, 4, 11, 10, 0)) is True
    assert briefing_service.briefing_window_active(datetime(2026, 4, 11, 8, 0)) is False


def test_build_morning_brief_payload_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(morning_brief_store, "_STORE_PATH", tmp_path / "mb.json")
    d = date(2026, 4, 11)
    runway = {"anchor_title": "Stand-up", "anchor_start_iso": "2026-04-11T09:00:00-05:00"}
    kz = [{"start_iso": "2026-04-11T13:00:00+00:00", "end_iso": "2026-04-11T15:00:00+00:00"}]
    mb = briefing_service.build_morning_brief_payload(
        d,
        runway,
        kz,
        "Ship the Titan deck",
        dismissed=False,
        window_active=True,
    )
    assert mb["trio_slot1_title"] == "Ship the Titan deck"
    assert mb["matched_zone_index"] == 0
    assert len(mb["kill_zones_top3"]) == 1
    assert "Stand-up" in mb["anchors_summary"]
    assert "###" in mb["brief_markdown"] or "Hard anchor" in mb["brief_markdown"]
