"""API smoke tests (no live Google/Todoist)."""

from fastapi.testclient import TestClient

from api.main import app


def test_health():
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_zapier_inbound():
    c = TestClient(app)
    r = c.post("/api/integrations/zapier/inbound", json={"event": "test"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_cockpit_json():
    c = TestClient(app)
    r = c.get("/api/cockpit", params={"day": "2026-04-11"})
    assert r.status_code == 200
    data = r.json()
    assert data["date"] == "2026-04-11"
    assert "runway" in data
    rw = data["runway"]
    assert "integrity_wake_iso" in rw or rw["integrity_wake_iso"] is None
    assert "operator_display" in rw
    assert "conflict_summary" in rw
    assert "personal_calendar_status" in data
    assert data["personal_calendar_status"] in ("ok", "not_configured", "error")
    assert isinstance(data["executive_score_percent"], (int, float))
    assert "work_calendar_advisory" in data
    assert "schedule_day_signals" in data
    sds = data["schedule_day_signals"]
    assert "summary_line" in sds
    assert "overlap_count" in sds
    assert "deep_slot_60_available" in sds
    for ev in data.get("daily_landscape") or []:
        assert ev.get("source_kind") in ("personal_google", "personal_ics", "work_screenshot")
    assert "execution_day_summary" in data
    assert isinstance(data["execution_day_summary"], str)
    assert len(data["execution_day_summary"]) > 0
    assert "golden_path_resolution_summary" in data
    assert isinstance(data["golden_path_resolution_summary"], str)
    assert "schedule_tradeoff_answers" in data
    assert isinstance(data["schedule_tradeoff_answers"], dict)
    assert "golden_path_proposals" in data
    assert isinstance(data["golden_path_proposals"], list)
    assert "golden_path_timeline" in data
    assert isinstance(data["golden_path_timeline"], list)
    assert "identity_purpose" in data
    assert isinstance(data["identity_purpose"], str)
    assert "golden_path_snoozed" in data
    assert isinstance(data["golden_path_snoozed"], bool)
    assert "integrity_habit_snapshot" in data
    assert data["integrity_habit_snapshot"] is not None
    assert len(data["integrity_habit_snapshot"]["posture_sessions_7d"]) == 7
    assert "sidebar_integrity" in data
    si = data["sidebar_integrity"]
    assert len(si.get("posture_days") or []) == 28
    assert len(si.get("neck_days") or []) == 28
    assert len(si.get("labels") or []) == 28
    assert "graveyard_preview" in data
    assert isinstance(data["graveyard_preview"], list)
    assert "suggestion_items" in sds
    assert isinstance(sds["suggestion_items"], list)
    mb = data.get("morning_brief")
    assert isinstance(mb, dict)
    assert "visible" in mb and "dismissed" in mb
    assert "brief_markdown" in mb
    assert isinstance(mb.get("kill_zones_top3"), list)
    assert "integrity_consistency_percent" in data
    assert "integrity_sentry_state" in data
    assert data["integrity_sentry_state"] in ("NOMINAL", "WARNING", "CRITICAL")
    assert "focus_shell_window_active" in data
    assert "sacred_integrity_debt_count" in data
    assert "cockpit_operator_name" in data
    assert "sovereignty" in data and isinstance(data["sovereignty"], dict)
    assert "air_gap_active" in data
    assert "midday_shield_active" in data
    assert "identity_alignment_window_active" in data
    assert "air_gap_extension_suggested" in data
    assert "todoist_inbox_open_count" in data
    assert "inbox_slaughter_gate_ok" in data
    assert "dead_bug_alerts" in data
    assert "firefighting_signals" in data
    assert "firewall_audit_summary" in data
    assert "favor_strike_days_clean_7d" in data
    assert "favor_strike_streak_7d" in data
    assert "commitments_partner_overdue" in data
    assert "ragstone_ledger" in data
    assert "zero_utility_labor_today" in data
    assert "evening_wins_count" in data
    assert "evening_leaks_count" in data
