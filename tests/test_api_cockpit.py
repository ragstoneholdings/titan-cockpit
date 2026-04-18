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


def test_mobile_dashboard_and_power_trio_json():
    c = TestClient(app)
    r = c.get("/api/mobile/dashboard", params={"day": "2026-04-11"})
    assert r.status_code == 200
    data = r.json()
    assert "cockpit" in data
    cockpit = data["cockpit"]
    assert cockpit["date"] == "2026-04-11"
    assert "identity_purpose" in cockpit
    assert isinstance(cockpit["identity_purpose"], str)
    assert "runway" in cockpit
    assert "sovereignty" in cockpit
    assert "schedule_day_signals" in cockpit
    assert "ragstone_line" in data
    assert "qbo_line" in data

    t = c.get("/api/mobile/power-trio", params={"day": "2026-04-11"})
    assert t.status_code == 200
    trio = t.json()
    assert "slots" in trio
    assert "ranked_total" in trio
    assert trio["recon_day"] == "2026-04-11"


def test_mobile_readiness_and_day_plan_flow():
    c = TestClient(app)

    rd = c.get("/api/mobile/readiness")
    assert rd.status_code == 200
    readiness = rd.json()
    assert readiness["ok"] is True
    assert "gemini_configured" in readiness
    assert "google_calendar_connected" in readiness

    gen = c.post(
        "/api/mobile/day-plan/generate",
        json={"day": "2026-04-11", "objective": "Protect deep work and calendar control"},
    )
    assert gen.status_code == 200
    plan = gen.json()
    assert plan["day"] == "2026-04-11"
    assert isinstance(plan.get("blocks"), list)
    assert len(plan.get("blocks") or []) >= 1
    assert "plan_id" in plan and plan["plan_id"]

    repl = c.post(
        "/api/mobile/day-plan/replan",
        json={"day": "2026-04-11", "reason": "meeting moved"},
    )
    assert repl.status_code == 200
    repl_plan = repl.json()
    assert repl_plan["day"] == "2026-04-11"
    assert isinstance(repl_plan.get("blocks"), list)
    assert repl_plan.get("plan_id")

    acc = c.post(
        "/api/mobile/day-plan/accept",
        json={"day": "2026-04-11", "plan_id": repl_plan["plan_id"]},
    )
    assert acc.status_code == 200
    assert acc.json().get("ok") is True

    blk = repl_plan["blocks"][0]
    ev = c.post(
        "/api/mobile/day-plan/event",
        json={"day": "2026-04-11", "block_id": blk["id"], "status": "completed", "reason": "executed"},
    )
    assert ev.status_code == 200
    assert ev.json().get("ok") is True

    get_plan = c.get("/api/mobile/day-plan", params={"day": "2026-04-11"})
    assert get_plan.status_code == 200
    assert get_plan.json().get("accepted") is True

    mx = c.get("/api/mobile/assistant-metrics", params={"trailing_days": 14})
    assert mx.status_code == 200
    metrics = mx.json()
    assert "plan_acceptance_rate" in metrics
    assert "planned_vs_executed_adherence" in metrics
