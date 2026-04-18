"""Store boundary for iOS mobile read models.

This module intentionally avoids the web cockpit aggregate assembly path.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Protocol

import ragstone_ledger_store
import vanguard_health_store
from api.services import (
    cockpit_integrity_coherence as cic,
    dead_bug_navigator,
    firefighting_audit,
    power_trio_state as pts,
    qbo_scaffold,
    sovereignty_metrics,
)
from integrations.google_calendar import calendar_service_from_token, safe_list_google_calendar_events_for_day
from integrations.personal_calendar import (
    fetch_personal_calendar_events_from_env,
    personal_calendar_source_status_from_env,
)
from integrations.paths import data_root
from todoist_service import count_inbox_open_tasks


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MobileStore(Protocol):
    def load_dashboard_snapshot(self, day: date | None) -> Dict[str, Any]:
        ...

    def load_power_trio_snapshot(self, day: date | None) -> Dict[str, Any]:
        ...

    def load_qbo_status(self) -> Dict[str, Any]:
        ...

    def load_day_plan(self, day: date) -> Dict[str, Any] | None:
        ...

    def save_day_plan(self, day: date, plan: Dict[str, Any], *, source: str) -> Dict[str, Any]:
        ...

    def accept_day_plan(self, day: date, plan_id: str) -> Dict[str, Any]:
        ...

    def record_execution_event(self, day: date, block_id: str, status: str, reason: str) -> Dict[str, Any]:
        ...

    def load_execution_events(self, day: date) -> List[Dict[str, Any]]:
        ...

    def assistant_metrics(self, trailing_days: int = 14) -> Dict[str, Any]:
        ...


class SQLiteBackedMobileStore:
    """Mobile-native store (SQLite + direct service reads), no web aggregate dependency."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_root() / "mobile_dashboard.sqlite")
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _init_db(self) -> None:
        with self._conn() as cx:
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_daily_overrides (
                  day TEXT PRIMARY KEY,
                  execution_day_summary TEXT NOT NULL DEFAULT '',
                  runway_notification_markdown TEXT NOT NULL DEFAULT '',
                  runway_default_wake_iso TEXT NOT NULL DEFAULT '',
                  runway_prep_gap_minutes INTEGER NOT NULL DEFAULT 0,
                  runway_conflict INTEGER NOT NULL DEFAULT 0,
                  runway_conflict_summary TEXT
                )
                """
            )
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_day_plans (
                  day TEXT PRIMARY KEY,
                  plan_id TEXT NOT NULL,
                  source TEXT NOT NULL DEFAULT '',
                  accepted INTEGER NOT NULL DEFAULT 0,
                  plan_json TEXT NOT NULL DEFAULT '{}',
                  updated_at TEXT NOT NULL DEFAULT ''
                )
                """
            )
            cx.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_execution_events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  day TEXT NOT NULL,
                  block_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  reason TEXT NOT NULL DEFAULT '',
                  created_at TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def _daily_overrides(self, d: date) -> Dict[str, Any]:
        with self._conn() as cx:
            row = cx.execute(
                """
                SELECT execution_day_summary,
                       runway_notification_markdown,
                       runway_default_wake_iso,
                       runway_prep_gap_minutes,
                       runway_conflict,
                       runway_conflict_summary
                FROM mobile_daily_overrides
                WHERE day = ?
                """,
                (d.isoformat(),),
            ).fetchone()
        if not row:
            return {}
        return {
            "execution_day_summary": row[0] or "",
            "runway_notification_markdown": row[1] or "",
            "runway_default_wake_iso": row[2] or "",
            "runway_prep_gap_minutes": int(row[3] or 0),
            "runway_conflict": bool(row[4] or 0),
            "runway_conflict_summary": row[5],
        }

    def load_dashboard_snapshot(self, day: date | None) -> Dict[str, Any]:
        d = day or date.today()
        ov = self._daily_overrides(d)

        state = pts.load_state()
        tasks_by_id = state.get("tasks_by_id") if isinstance(state.get("tasks_by_id"), dict) else {}

        # Mobile can redefine this later; starting baseline keeps behavior predictable.
        vanguard_executed = {"deep": 0, "mixed": 0, "shallow": 0}
        consistency_pct = 100.0
        sentry_state = cic.compute_integrity_sentry_state(
            identity_alert=False,
            consistency_percent=consistency_pct,
            protocol_confirmed_today=True,
        )
        sov = sovereignty_metrics.build_sovereignty_with_todoist(
            vanguard_executed=vanguard_executed,
            integrity_consistency_percent=consistency_pct,
            tasks_by_id=tasks_by_id,
        )

        ledger = dict(ragstone_ledger_store.load_bundle())
        ledger.update(ragstone_ledger_store.computed_kpis())

        inbox_n = 0
        key = pts.todoist_api_key()
        if key:
            try:
                inbox_n, _ = count_inbox_open_tasks(key)
            except Exception:
                inbox_n = 0
        row_day = vanguard_health_store.get_day(d)
        inbox_cleared = bool(row_day.get("inbox_cleared"))
        inbox_gate_ok = inbox_n == 0 or inbox_cleared

        ff_signals = firefighting_audit.detect_firefighting_signals(tasks_by_id) if tasks_by_id else []
        dead_alerts = dead_bug_navigator.compute_dead_bug_alerts(tasks_by_id) if tasks_by_id else []

        summary = str(ov.get("execution_day_summary") or "").strip()
        if not summary:
            summary = f"Sentry {sentry_state} · Inbox {inbox_n} open"

        runway_note = str(ov.get("runway_notification_markdown") or "").strip()
        if not runway_note and ledger.get("cash_runway_months") is not None:
            runway_note = f"Cash runway {ledger.get('cash_runway_months')} months"

        gsvc = calendar_service_from_token()
        google_events, google_err = safe_list_google_calendar_events_for_day(gsvc, d, "primary")
        personal_rows, personal_hours, personal_err = fetch_personal_calendar_events_from_env(d)
        psrc = personal_calendar_source_status_from_env()

        return {
            "date": d.isoformat(),
            "google_calendar_connected": gsvc is not None,
            "executive_score_percent": 0.0,
            "execution_day_summary": summary,
            "identity_purpose": "",
            "vanguard_executed": vanguard_executed,
            "runway": {
                "notification_markdown": runway_note,
                "prep_gap_minutes": int(ov.get("runway_prep_gap_minutes") or 0),
                "default_wake_iso": str(ov.get("runway_default_wake_iso") or ""),
                "runway_conflict": bool(ov.get("runway_conflict") or False),
                "operator_display": "You",
                "conflict_summary": ov.get("runway_conflict_summary"),
            },
            "sovereignty": sov,
            "air_gap_active": cic.air_gap_window_active(recon_day=d),
            "midday_shield_active": cic.midday_shield_window_active(recon_day=d),
            "identity_alignment_window_active": cic.identity_alignment_window_active(recon_day=d),
            "todoist_inbox_open_count": inbox_n,
            "inbox_slaughter_gate_ok": inbox_gate_ok,
            "dead_bug_alerts": dead_alerts,
            "firefighting_signals": ff_signals,
            "firewall_audit_summary": "",
            "schedule_day_signals": {
                "summary_line": summary,
                "meeting_load_warning": False,
                "fragmented_day": False,
            },
            "integrity_sentry_state": sentry_state,
            "ragstone_ledger": ledger,
            "calendar_signals": {
                "google": {
                    "connected": gsvc is not None,
                    "event_count": len(google_events),
                    "error": google_err,
                },
                "personal": {
                    "configured": bool(psrc.get("configured")),
                    "mode": str(psrc.get("mode") or "none"),
                    "event_count": len(personal_rows),
                    "hours": float(personal_hours or 0.0),
                    "error": personal_err,
                },
            },
        }

    def load_power_trio_snapshot(self, day: date | None) -> Dict[str, Any]:
        d = day or date.today()
        return pts.trio_payload(day=d)

    def load_qbo_status(self) -> Dict[str, Any]:
        return qbo_scaffold.qbo_placeholder()

    def load_day_plan(self, day: date) -> Dict[str, Any] | None:
        with self._conn() as cx:
            row = cx.execute(
                "SELECT plan_id, source, accepted, plan_json, updated_at FROM mobile_day_plans WHERE day = ?",
                (day.isoformat(),),
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row[3] or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload.setdefault("day", day.isoformat())
        payload.setdefault("plan_id", row[0])
        payload.setdefault("source", row[1] or "")
        payload.setdefault("accepted", bool(row[2]))
        payload.setdefault("updated_at", row[4] or "")
        return payload

    def save_day_plan(self, day: date, plan: Dict[str, Any], *, source: str) -> Dict[str, Any]:
        out = dict(plan if isinstance(plan, dict) else {})
        out["day"] = day.isoformat()
        out["plan_id"] = str(out.get("plan_id") or uuid.uuid4())
        out["source"] = source
        out["accepted"] = bool(out.get("accepted", False))
        out["updated_at"] = _utc_now_iso()
        with self._conn() as cx:
            cx.execute(
                """
                INSERT INTO mobile_day_plans(day, plan_id, source, accepted, plan_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                  plan_id = excluded.plan_id,
                  source = excluded.source,
                  accepted = excluded.accepted,
                  plan_json = excluded.plan_json,
                  updated_at = excluded.updated_at
                """,
                (
                    day.isoformat(),
                    out["plan_id"],
                    source,
                    1 if out["accepted"] else 0,
                    json.dumps(out, ensure_ascii=False),
                    out["updated_at"],
                ),
            )
        return out

    def accept_day_plan(self, day: date, plan_id: str) -> Dict[str, Any]:
        cur = self.load_day_plan(day) or {}
        if cur and str(cur.get("plan_id") or "") != str(plan_id):
            return {"ok": False, "error": "plan_id_mismatch"}
        cur["accepted"] = True
        cur["plan_id"] = str(plan_id or cur.get("plan_id") or "")
        self.save_day_plan(day, cur, source=str(cur.get("source") or "manual_accept"))
        return {"ok": True, "plan_id": cur.get("plan_id"), "day": day.isoformat()}

    def record_execution_event(self, day: date, block_id: str, status: str, reason: str) -> Dict[str, Any]:
        st = str(status).strip().lower()
        if st not in {"completed", "skipped"}:
            st = "skipped"
        ts = _utc_now_iso()
        with self._conn() as cx:
            cx.execute(
                """
                INSERT INTO mobile_execution_events(day, block_id, status, reason, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (day.isoformat(), str(block_id).strip(), st, str(reason or ""), ts),
            )
        return {"ok": True, "day": day.isoformat(), "block_id": block_id, "status": st, "created_at": ts}

    def load_execution_events(self, day: date) -> List[Dict[str, Any]]:
        with self._conn() as cx:
            rows = cx.execute(
                "SELECT block_id, status, reason, created_at FROM mobile_execution_events WHERE day = ? ORDER BY id ASC",
                (day.isoformat(),),
            ).fetchall()
        out: List[Dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "block_id": r[0] or "",
                    "status": r[1] or "",
                    "reason": r[2] or "",
                    "created_at": r[3] or "",
                }
            )
        return out

    def assistant_metrics(self, trailing_days: int = 14) -> Dict[str, Any]:
        n_days = max(1, int(trailing_days or 14))
        with self._conn() as cx:
            plans = cx.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(accepted), 0)
                FROM mobile_day_plans
                WHERE day >= date('now', ?)
                """,
                (f"-{n_days} day",),
            ).fetchone()
            evs = cx.execute(
                """
                SELECT
                  COUNT(*) as total,
                  COALESCE(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END), 0) as completed,
                  COALESCE(SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END), 0) as skipped
                FROM mobile_execution_events
                WHERE day >= date('now', ?)
                """,
                (f"-{n_days} day",),
            ).fetchone()
        total_plans = int((plans or [0, 0])[0] or 0)
        accepted = int((plans or [0, 0])[1] or 0)
        total_events = int((evs or [0, 0, 0])[0] or 0)
        completed = int((evs or [0, 0, 0])[1] or 0)
        skipped = int((evs or [0, 0, 0])[2] or 0)
        acceptance_rate = (accepted / total_plans) if total_plans else 0.0
        adherence = (completed / total_events) if total_events else 0.0
        return {
            "trailing_days": n_days,
            "plans_total": total_plans,
            "plans_accepted": accepted,
            "plan_acceptance_rate": round(acceptance_rate, 3),
            "execution_events_total": total_events,
            "blocks_completed": completed,
            "blocks_skipped": skipped,
            "planned_vs_executed_adherence": round(adherence, 3),
            "replans": max(0, total_plans - accepted),
        }


store: MobileStore = SQLiteBackedMobileStore()
