"""Mobile-specific read models decoupled from web API contracts."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

from api.services import mobile_store


def _fmt_num(v: Any, digits: int = 1) -> str:
    try:
        if v is None:
            return "—"
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _ragstone_line(raw: Dict[str, Any]) -> str:
    runway = _fmt_num(raw.get("cash_runway_months"), digits=1)
    yoy = _fmt_num(raw.get("yoy_revenue_growth_percent"), digits=1)
    return f"Runway {runway} mo · YoY {yoy}%"


def _qbo_line() -> str:
    q = mobile_store.store.load_qbo_status()
    status = str(q.get("status") or "").strip()
    msg = str(q.get("message") or "").strip()
    if not status:
        return ""
    return f"{status}: {msg}" if msg else status


def _drift_signals(day: date) -> list[str]:
    plan = mobile_store.store.load_day_plan(day)
    if not isinstance(plan, dict):
        return []
    blocks = plan.get("blocks") if isinstance(plan.get("blocks"), list) else []
    if not blocks:
        return []
    events = mobile_store.store.load_execution_events(day)
    by_block = {str(e.get("block_id") or ""): str(e.get("status") or "") for e in events}
    pending = 0
    skipped = 0
    for b in blocks:
        if not isinstance(b, dict):
            continue
        bid = str(b.get("id") or "")
        st = by_block.get(bid)
        if st == "skipped":
            skipped += 1
        elif st != "completed":
            pending += 1
    out: list[str] = []
    if skipped:
        out.append(f"{skipped} block(s) skipped")
    if pending >= 2:
        out.append(f"{pending} block(s) still unclosed")
    return out


def get_drift_signals(day: date) -> list[str]:
    return _drift_signals(day)


def build_mobile_dashboard(day: date | None) -> Dict[str, Any]:
    d = day or date.today()
    raw = mobile_store.store.load_dashboard_snapshot(d)
    runway = raw.get("runway") if isinstance(raw.get("runway"), dict) else {}
    vex = raw.get("vanguard_executed") if isinstance(raw.get("vanguard_executed"), dict) else {}
    sov = raw.get("sovereignty") if isinstance(raw.get("sovereignty"), dict) else {}
    sig = raw.get("schedule_day_signals") if isinstance(raw.get("schedule_day_signals"), dict) else {}

    cockpit = {
        "date": raw.get("date") or "",
        "identity_purpose": str(raw.get("identity_purpose") or ""),
        "google_calendar_connected": bool(raw.get("google_calendar_connected")),
        "executive_score_percent": float(raw.get("executive_score_percent") or 0),
        "execution_day_summary": str(raw.get("execution_day_summary") or ""),
        "vanguard_executed": {
            "deep": int(vex.get("deep") or 0),
            "mixed": int(vex.get("mixed") or 0),
            "shallow": int(vex.get("shallow") or 0),
        },
        "runway": {
            "notification_markdown": str(runway.get("notification_markdown") or ""),
            "prep_gap_minutes": int(runway.get("prep_gap_minutes") or 0),
            "default_wake_iso": str(runway.get("default_wake_iso") or ""),
            "runway_conflict": bool(runway.get("runway_conflict")),
            "operator_display": str(runway.get("operator_display") or "You"),
            "conflict_summary": runway.get("conflict_summary"),
        },
        "sovereignty": {
            "sovereignty_quotient_percent": float(sov.get("sovereignty_quotient_percent") or 0),
            "sovereignty_quotient_blended_percent": float(sov.get("sovereignty_quotient_blended_percent") or 0),
            "deep_work_sessions_logged": int(sov.get("deep_work_sessions_logged") or 0),
            "execution_mix_total": int(sov.get("execution_mix_total") or 0),
            "utility_tagged_open_count": int(sov.get("utility_tagged_open_count") or 0),
            "sovereignty_line": str(sov.get("sovereignty_line") or ""),
            "operational_authority_line": str(sov.get("operational_authority_line") or ""),
            "financial_sovereignty_line": str(sov.get("financial_sovereignty_line") or ""),
            "physical_baseline_line": str(sov.get("physical_baseline_line") or ""),
        },
        "air_gap_active": bool(raw.get("air_gap_active")),
        "midday_shield_active": bool(raw.get("midday_shield_active")),
        "identity_alignment_window_active": bool(raw.get("identity_alignment_window_active")),
        "todoist_inbox_open_count": int(raw.get("todoist_inbox_open_count") or 0),
        "inbox_slaughter_gate_ok": bool(raw.get("inbox_slaughter_gate_ok")),
        "dead_bug_alerts": raw.get("dead_bug_alerts") if isinstance(raw.get("dead_bug_alerts"), list) else [],
        "firefighting_signals": raw.get("firefighting_signals") if isinstance(raw.get("firefighting_signals"), list) else [],
        "firewall_audit_summary": str(raw.get("firewall_audit_summary") or ""),
        "schedule_day_signals": {
            "summary_line": str(sig.get("summary_line") or ""),
            "meeting_load_warning": bool(sig.get("meeting_load_warning")),
            "fragmented_day": bool(sig.get("fragmented_day")),
        },
        "integrity_sentry_state": str(raw.get("integrity_sentry_state") or "NOMINAL"),
        "calendar_signals": raw.get("calendar_signals") if isinstance(raw.get("calendar_signals"), dict) else {},
        "drift_signals": _drift_signals(d),
    }
    rag = raw.get("ragstone_ledger") if isinstance(raw.get("ragstone_ledger"), dict) else {}
    return {
        "cockpit": cockpit,
        "ragstone_line": _ragstone_line(rag),
        "qbo_line": _qbo_line(),
    }


def build_mobile_power_trio(day: date | None) -> Dict[str, Any]:
    d = day or date.today()
    raw = mobile_store.store.load_power_trio_snapshot(d)
    slots = []
    for s in raw.get("slots") or []:
        if not isinstance(s, dict):
            continue
        slots.append(
            {
                "slot": int(s.get("slot") or 0),
                "label": str(s.get("label") or ""),
                "task_id": str(s.get("task_id") or ""),
                "title": str(s.get("title") or ""),
                "description": str(s.get("description") or ""),
                "project_name": str(s.get("project_name") or ""),
                "priority": int(s.get("priority") or 1),
                "tactical_steps": [str(x) for x in (s.get("tactical_steps") or [])],
            }
        )
    return {
        "slots": slots,
        "ranked_total": int(raw.get("ranked_total") or 0),
        "task_total": int(raw.get("task_total") or 0),
        "rank_warning": str(raw.get("rank_warning") or ""),
        "merge_note": str(raw.get("merge_note") or ""),
        "last_sync_iso": str(raw.get("last_sync_iso") or ""),
        "last_rank_iso": str(raw.get("last_rank_iso") or ""),
        "recon_day": str(raw.get("recon_day") or d.isoformat()),
    }
