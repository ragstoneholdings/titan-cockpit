"""Assemble cockpit read model from domain modules (no Streamlit)."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from chief_of_staff.models import ChiefOfStaffConfig
from chief_of_staff.planning import (
    DEFAULT_MORNING_OPS_ANCHOR_TITLE,
    build_day_readiness,
    compute_deep_work_kill_zones,
    merged_timed_anchors,
    parse_marker_csv,
    select_integrity_anchor,
    to_local,
    _parse_iso_dt,
)
from focus_metrics import focus_score_percent
from api.services.cockpit_protocol_file import merged_chief_hard_markers_csv, merged_identity_protocols
from api.services.posture_protocol_read import (
    PROTOCOL_ITEM_IDS,
    load_protocol_history_bundle,
    protocol_confirmed_for_day,
)
from api.services.golden_path_proposal_store import (
    get_approved_ids,
    get_dismissed_ids,
    is_snoozed,
)
from api.services.golden_path_resolution import golden_path_resolution_summary
from api.services.golden_path_rule_proposals import build_rule_based_proposals
from api.services.landscape_tradeoff_resolve import apply_overlap_decisions_to_landscape
from api.services.schedule_day_signals import (
    _immovable_title,
    build_work_screenshot_busy_spans,
    compute_schedule_day_signals,
)
from api.services.schedule_tradeoff_store import get_answers_for_day
from api.services.work_advisory_store import (
    load_advisory_meta_for_day,
    load_landscape_rows_for_day,
    tactical_brief_has_content,
    work_calendar_week_gap_hint,
)
import commitments_store
import ragstone_ledger_store
import vanguard_health_store
from graveyard_store import list_entries as list_graveyard_entries
from identity_store import load_identity_purpose
from integrations.env_loader import env_str

from api.services import briefing_service, cockpit_integrity_coherence as cic, morning_brief_store
from api.services import dead_bug_navigator, firefighting_audit, sovereignty_metrics
from api.services.power_trio_state import trio_payload
from integrity_stats_store import load_bundle
from runway_store import load_runway_override_for_day

EXPECTED_PREP_TOTAL_MIN = 120
EXPECTED_POSTURE_MIN = 30
EXPECTED_NECK_MIN = 60
EXPECTED_OPS_MIN = 30


def _build_execution_day_summary(
    landscape: List[Dict[str, Any]],
    runway_payload: Dict[str, Any],
    personal_calendar_status: str,
    work_coaching_nonblank: bool,
    tactical_brief_nonempty: bool,
    schedule_summary_line: str,
) -> str:
    """One short paragraph: merged landscape + runway + work advisory + schedule read (truncated)."""
    n = len(landscape)
    n_ws = sum(1 for r in landscape if str(r.get("source_kind")) == "work_screenshot")
    n_cal = n - n_ws
    parts: List[str] = []
    if personal_calendar_status == "not_configured":
        parts.append("Personal calendar not connected.")
    elif personal_calendar_status == "error":
        parts.append("Personal calendar feed error.")
    if n == 0:
        parts.append("No merged timed blocks for this day.")
    else:
        if n_ws and n_cal:
            parts.append(f"{n} merged blocks ({n_ws} work screenshot, {n_cal} from calendars).")
        elif n_ws:
            parts.append(f"{n} merged blocks (work screenshot).")
        else:
            parts.append(f"{n} merged blocks from calendars.")
    at = runway_payload.get("anchor_title")
    if at:
        parts.append(f"Runway anchor: {at}.")
    parts.append(
        "Work tactical brief on file."
        if tactical_brief_nonempty
        else (
            "Work Gemini coaching saved for this day."
            if work_coaching_nonblank
            else "No work-calendar Gemini note saved for this day."
        )
    )
    sig = (schedule_summary_line or "").strip()
    if sig:
        cap = 180
        if len(sig) > cap:
            sig = sig[: cap - 1] + "…"
        parts.append(sig)
    return " ".join(parts)


def _runway_override_triple(day: date) -> Optional[Tuple[str, str, str]]:
    o = load_runway_override_for_day(day)
    if not o:
        return None
    return (o.start_iso, o.title, o.source)


def _parse_iso_dt(iso: str) -> Optional[datetime]:
    try:
        s = iso.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _find_dup_landscape_index(merged: List[Dict[str, Any]], new_row: Dict[str, Any]) -> Optional[int]:
    t_new = _parse_iso_dt(str(new_row.get("start_iso") or ""))
    if t_new is None:
        return None
    title_new = str(new_row.get("title") or "").strip().lower()
    for i, e in enumerate(merged):
        t_e = _parse_iso_dt(str(e.get("start_iso") or ""))
        if t_e is None:
            continue
        if (
            abs((t_e - t_new).total_seconds()) < 180
            and str(e.get("title") or "").strip().lower() == title_new
        ):
            return i
    return None


def _merge_work_screenshot_into_landscape(
    landscape: List[Dict[str, Any]], extra: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Merge saved screenshot rows: replace matching API row so Work (screenshot) is visible; else append."""
    merged = list(landscape)
    replaced_api = 0
    appended = 0
    skipped_dup_ws = 0
    for row in extra:
        if str(row.get("source_kind")) != "work_screenshot":
            continue
        idx = _find_dup_landscape_index(merged, row)
        if idx is not None:
            if str(merged[idx].get("source_kind")) == "work_screenshot":
                skipped_dup_ws += 1
                continue
            merged[idx] = row
            replaced_api += 1
            continue
        merged.append(row)
        appended += 1
    merged.sort(key=lambda r: str(r.get("start_iso") or ""))
    return merged


def _default_wake_datetime(day: date) -> datetime:
    """Global default integrity wake baseline (5:00 AM local); matches Streamlit seed."""
    tzinfo = datetime.now().astimezone().tzinfo
    return datetime.combine(day, time(5, 0)).replace(tzinfo=tzinfo)


def _gp_norm_title(t: str) -> str:
    return " ".join(str(t or "").strip().lower().split())


def _purpose_tokens(purpose: str) -> List[str]:
    seen: List[str] = []
    for m in re.finditer(r"[a-z0-9]{5,}", str(purpose or "").lower()):
        tok = m.group(0)
        if tok not in seen:
            seen.append(tok)
        if len(seen) >= 20:
            break
    return seen


def _row_end_fallback(row: Dict[str, Any]) -> Optional[datetime]:
    s = _parse_iso_dt(str(row.get("start_iso") or ""))
    if s is None:
        return None
    e = _parse_iso_dt(str(row.get("end_iso") or ""))
    if e is None:
        return s + timedelta(hours=1)
    return e


def _row_in_any_overlap(row: Dict[str, Any], overlaps: List[Dict[str, Any]]) -> bool:
    rt = _gp_norm_title(str(row.get("title") or ""))
    rs = _parse_iso_dt(str(row.get("start_iso") or ""))
    if rs is None or not rt:
        return False
    for ov in overlaps:
        if not isinstance(ov, dict):
            continue
        for lbl in ("a", "b"):
            if _gp_norm_title(str(ov.get(f"title_{lbl}") or "")) != rt:
                continue
            hint = str(ov.get(f"start_{lbl}_iso") or ov.get("start_iso") or "")
            oh = _parse_iso_dt(hint)
            if oh is None:
                continue
            if abs((to_local(rs) - to_local(oh)).total_seconds()) <= 360:
                return True
    return False


def _build_golden_path_timeline(
    landscape: List[Dict[str, Any]],
    purpose: str,
    schedule_signals: Dict[str, Any],
) -> List[Dict[str, Any]]:
    overlaps = schedule_signals.get("overlaps") or []
    tokens = _purpose_tokens(purpose)
    rows = sorted(landscape, key=lambda r: str(r.get("start_iso") or ""))
    out: List[Dict[str, Any]] = []
    prev_end: Optional[datetime] = None
    for r in rows:
        st = str(r.get("start_iso") or "")
        if not st:
            continue
        title = str(r.get("title") or "")
        sk = str(r.get("source_kind") or "")
        cur = _parse_iso_dt(st)
        badges: List[str] = []
        if sk == "work_screenshot":
            badges.append("screenshot")
        if _immovable_title(title):
            badges.append("immovable")
        title_l = _gp_norm_title(title)
        if tokens and any(tok in title_l for tok in tokens):
            badges.append("purpose_match")
        if overlaps and _row_in_any_overlap(r, overlaps):
            badges.append("overlap")
        hints: List[str] = []
        if "immovable" in badges:
            hints.append("Treat as fixed unless you explicitly negotiate it.")
        if "purpose_match" in badges:
            hints.append("Title echoes your purpose statement — worth defending.")
        if "overlap" in badges:
            hints.append(
                "This row still sits in an overlap window — pick a winner under Daily landscape if needed."
            )
        if prev_end and cur:
            gap_min = (to_local(cur) - to_local(prev_end)).total_seconds() / 60.0
            if 0 <= gap_min < 10:
                badges.append("tight_buffer")
                hints.append("Tight handoff — under 10m after the prior block ends.")
        e = _row_end_fallback(r)
        end_iso_str = e.isoformat() if e is not None else ""
        out.append(
            {
                "start_iso": st,
                "end_iso": end_iso_str,
                "title": title,
                "source": str(r.get("source") or ""),
                "source_kind": sk,
                "badges": badges,
                "expand_hint": " ".join(hints).strip(),
            }
        )
        if e is not None:
            prev_end = e
        elif cur is not None:
            prev_end = cur + timedelta(hours=1)
    return out


def _compute_runway_slice(
    day: date,
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Any]:
    """Build runway_payload dict + readiness record for one calendar day."""
    markers = parse_marker_csv(merged_chief_hard_markers_csv())
    cfg = ChiefOfStaffConfig(hard_title_markers=markers)
    override_t = _runway_override_triple(day)

    anchor = select_integrity_anchor(
        google_events,
        personal_rows,
        cfg,
        runway_override=override_t,
        gemini_chosen_index=None,
    )

    protocols = merged_identity_protocols()
    default_wake = _default_wake_datetime(day)
    bed: Optional[datetime] = None

    rec = build_day_readiness(
        anchor,
        protocols,
        default_wake,
        timedelta(hours=7.5),
        bed,
    )

    pm = int(protocols.posture.total_seconds() // 60)
    nm = int(protocols.neck.total_seconds() // 60)
    om = int(protocols.morning_ops.total_seconds() // 60)
    prep_total = pm + nm + om
    prep_gap = EXPECTED_PREP_TOTAL_MIN - prep_total

    runway_payload: Dict[str, Any] = {
        "integrity_wake_iso": rec.integrity_wake.isoformat() if rec.integrity_wake else None,
        "tactical_integrity_wake_iso": rec.tactical_integrity_wake.isoformat()
        if rec.tactical_integrity_wake
        else None,
        "default_wake_iso": rec.default_wake.isoformat(),
        "runway_conflict": rec.runway_conflict,
        "anchor_title": rec.anchor.title if rec.anchor else None,
        "anchor_start_iso": rec.anchor.start.isoformat() if rec.anchor else None,
        "anchor_source": rec.anchor.source if rec.anchor else None,
        "synthetic_default_anchor": bool(
            rec.anchor is not None and rec.anchor.title == DEFAULT_MORNING_OPS_ANCHOR_TITLE
        ),
        "notification_markdown": rec.notification_markdown,
        "prep_posture_minutes": pm,
        "prep_neck_minutes": nm,
        "prep_ops_minutes": om,
        "prep_total_minutes": prep_total,
        "prep_expected_total_minutes": EXPECTED_PREP_TOTAL_MIN,
        "prep_gap_minutes": prep_gap,
        "prep_expected_posture_minutes": EXPECTED_POSTURE_MIN,
        "prep_expected_neck_minutes": EXPECTED_NECK_MIN,
        "prep_expected_ops_minutes": EXPECTED_OPS_MIN,
        "prep_shortfall_labels": _prep_shortfall_labels(pm, nm, om),
        "operator_display": rec.operator_display,
        "conflict_summary": rec.conflict_summary,
        "tomorrow_preview": None,
    }
    return runway_payload, rec


def build_cockpit_response(
    day: date,
    *,
    google_events: List[Dict[str, Any]],
    personal_rows: List[Dict[str, Any]],
    personal_calendar_note: str = "",
    personal_calendar_status: str = "ok",
    vanguard_deep: int = 0,
    vanguard_mixed: int = 0,
    vanguard_shallow: int = 0,
    google_events_tomorrow: Optional[List[Dict[str, Any]]] = None,
    personal_rows_tomorrow: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    runway_payload, rec = _compute_runway_slice(day, google_events, personal_rows)

    synthetic = bool(
        rec.anchor is not None and rec.anchor.title == DEFAULT_MORNING_OPS_ANCHOR_TITLE
    )

    merged = merged_timed_anchors(google_events, personal_rows)
    landscape = []
    for a in merged:
        sk = "personal_google" if a.source == "google" else "personal_ics"
        landscape.append(
            {
                "start_iso": a.start.isoformat(),
                "title": a.title,
                "source": a.source,
                "source_kind": sk,
            }
        )

    ws_pre = load_landscape_rows_for_day(day)
    landscape = _merge_work_screenshot_into_landscape(landscape, ws_pre)
    work_cal_week_gap = work_calendar_week_gap_hint(day, work_screenshot_row_count=len(ws_pre))

    tradeoff_answers = get_answers_for_day(day)
    schedule_signals_pre = compute_schedule_day_signals(
        day,
        google_events,
        personal_rows,
        landscape,
        runway_conflict=bool(rec.runway_conflict),
    )
    landscape = apply_overlap_decisions_to_landscape(
        landscape,
        schedule_signals_pre.get("overlaps") or [],
        tradeoff_answers,
    )

    work_busy = build_work_screenshot_busy_spans(day, landscape)
    zones = compute_deep_work_kill_zones(
        google_events,
        personal_rows,
        day,
        extra_busy_spans=work_busy or None,
    )
    kill_out = [{"start_iso": a.isoformat(), "end_iso": b.isoformat()} for a, b in zones]

    score = focus_score_percent(vanguard_deep, vanguard_mixed, vanguard_shallow)

    runway_payload["synthetic_default_anchor"] = synthetic

    if day == date.today() and google_events_tomorrow is not None and personal_rows_tomorrow is not None:
        tm = day + timedelta(days=1)
        tr_payload, _tr_rec = _compute_runway_slice(tm, google_events_tomorrow, personal_rows_tomorrow)
        runway_payload["tomorrow_preview"] = {
            "date": tm.isoformat(),
            "integrity_wake_iso": tr_payload.get("integrity_wake_iso"),
            "tactical_integrity_wake_iso": tr_payload.get("tactical_integrity_wake_iso"),
            "default_wake_iso": tr_payload.get("default_wake_iso") or "",
            "runway_conflict": bool(tr_payload.get("runway_conflict")),
            "anchor_title": tr_payload.get("anchor_title"),
            "anchor_start_iso": tr_payload.get("anchor_start_iso"),
            "anchor_source": tr_payload.get("anchor_source"),
            "synthetic_default_anchor": bool(tr_payload.get("synthetic_default_anchor")),
            "prep_shortfall_labels": tr_payload.get("prep_shortfall_labels") or [],
            "conflict_summary": tr_payload.get("conflict_summary"),
        }

    tzinfo = datetime.now().astimezone().tzinfo
    proto_ok_recon = protocol_confirmed_for_day(day)
    proto_ok_today = protocol_confirmed_for_day(date.today())
    # Urgency (Sentry, consistency blend, web red shell) must track the real clock, not an unconfirmed future recon day.
    proto_for_discipline = proto_ok_today if day != date.today() else proto_ok_recon
    identity_alert = _compute_identity_alert(day, rec.integrity_wake, proto_ok_recon, tzinfo)

    wca = load_advisory_meta_for_day(day)

    schedule_signals = compute_schedule_day_signals(
        day,
        google_events,
        personal_rows,
        landscape,
        runway_conflict=bool(runway_payload.get("runway_conflict")),
    )

    identity_purpose = load_identity_purpose()
    golden_path_timeline = _build_golden_path_timeline(landscape, identity_purpose, schedule_signals)

    work_coaching_nonblank = bool(
        str((wca or {}).get("time_coaching") or "").strip()
    )
    tb_raw = (wca or {}).get("tactical_brief")
    tactical_brief_nonempty = tactical_brief_has_content(tb_raw) if tb_raw else False
    execution_day_summary = _build_execution_day_summary(
        landscape,
        runway_payload,
        personal_calendar_status,
        work_coaching_nonblank,
        tactical_brief_nonempty,
        str(schedule_signals.get("summary_line") or ""),
    )

    gp_summary = golden_path_resolution_summary(tradeoff_answers)
    dismissed = get_dismissed_ids(day)
    approved_ids = get_approved_ids(day)
    snoozed = is_snoozed(day)
    raw_props = build_rule_based_proposals(
        runway_payload,
        schedule_signals,
        dismissed=dismissed,
        snoozed=snoozed,
    )
    golden_path_proposals = []
    for p in raw_props:
        pid = str(p.get("id") or "")
        st = "approved" if pid in approved_ids else "pending"
        golden_path_proposals.append(
            {
                "id": pid,
                "headline": str(p.get("headline") or ""),
                "detail": str(p.get("detail") or ""),
                "deltas": p.get("deltas") if isinstance(p.get("deltas"), dict) else {},
                "status": st,
            }
        )

    ib = load_bundle()
    raw_posture = ib.get("posture_sessions_7d")
    posture_7d: List[bool] = []
    if isinstance(raw_posture, list):
        for x in raw_posture[:7]:
            posture_7d.append(bool(x))
    while len(posture_7d) < 7:
        posture_7d.append(False)
    integrity_habit_snapshot = {
        "posture_sessions_7d": posture_7d,
        "notes": str(ib.get("notes") or ""),
    }

    sidebar_integrity = _build_sidebar_integrity_28d(day)
    graveyard_preview: List[Dict[str, Any]] = []
    for row in list_graveyard_entries(8):
        if not isinstance(row, dict):
            continue
        graveyard_preview.append(
            {
                "task_id": str(row.get("task_id") or ""),
                "title": str(row.get("title") or ""),
                "closed_at": str(row.get("closed_at") or ""),
                "source": str(row.get("source") or ""),
            }
        )

    slot1_title = ""
    try:
        trio_raw = trio_payload(day=day)
        slots0 = trio_raw.get("slots") or []
        if slots0 and isinstance(slots0[0], dict):
            slot1_title = str(slots0[0].get("title") or "").strip()
    except Exception:
        slot1_title = ""

    wb_active = briefing_service.briefing_window_active()
    mb_dismissed = morning_brief_store.is_morning_brief_dismissed(day)
    morning_brief = briefing_service.build_morning_brief_payload(
        day,
        runway_payload,
        kill_out,
        slot1_title,
        dismissed=mb_dismissed,
        window_active=wb_active,
    )

    consistency_pct = cic.compute_integrity_consistency_percent(
        protocol_confirmed_today=proto_for_discipline,
        sidebar_integrity=sidebar_integrity,
    )
    sentry_state = cic.compute_integrity_sentry_state(
        identity_alert=identity_alert,
        consistency_percent=consistency_pct,
        protocol_confirmed_today=proto_for_discipline,
    )
    nudge_vis, nudge_msg = cic.compute_ops_posture_nudge(recon_day=day, landscape=landscape)
    focus_shell_eligible = cic.focus_shell_window_active(recon_day=day)
    sacred_debt = 0
    try:
        from api.services import power_trio_state as _pts

        _st = _pts.load_state()
        _by = _st.get("tasks_by_id") if isinstance(_st.get("tasks_by_id"), dict) else {}
        sacred_debt = cic.count_sacred_overdue_tasks(_by, day)
    except Exception:
        sacred_debt = 0
    cockpit_operator_name = (
        env_str("COCKPIT_OPERATOR_NAME", "").strip()
        or str(runway_payload.get("operator_display") or "").strip()
    )

    tasks_by_id: Dict[str, Any] = {}
    try:
        from api.services import power_trio_state as _pts

        _st = _pts.load_state()
        _tb = _st.get("tasks_by_id")
        if isinstance(_tb, dict):
            tasks_by_id = _tb
    except Exception:
        tasks_by_id = {}

    vex = {"deep": vanguard_deep, "mixed": vanguard_mixed, "shallow": vanguard_shallow}
    sovereignty_block = sovereignty_metrics.build_sovereignty_with_todoist(
        vanguard_executed=vex,
        integrity_consistency_percent=consistency_pct,
        tasks_by_id=tasks_by_id,
    )

    air_gap_on = cic.air_gap_window_active(recon_day=day)
    midday_on = cic.midday_shield_window_active(recon_day=day)
    align_on = cic.identity_alignment_window_active(recon_day=day)

    sleep_prior = vanguard_health_store.sleep_hours_for_prior_day(recon_day=day)
    hb = vanguard_health_store.load_bundle()
    ht = hb.get("targets") if isinstance(hb.get("targets"), dict) else {}
    try:
        sleep_tgt = float(ht.get("sleep_hours_target") or 7.5)
    except (TypeError, ValueError):
        sleep_tgt = 7.5
    air_ext = bool(
        day == date.today()
        and sleep_prior is not None
        and sleep_prior < sleep_tgt
    )

    inbox_n = 0
    try:
        from api.services.power_trio_state import todoist_api_key
        from todoist_service import count_inbox_open_tasks

        _k = todoist_api_key()
        if _k:
            inbox_n, _ = count_inbox_open_tasks(_k)
    except Exception:
        inbox_n = 0

    row_day = vanguard_health_store.get_day(day)
    inbox_cleared_flag = bool(row_day.get("inbox_cleared"))
    inbox_gate_ok = inbox_n == 0 or inbox_cleared_flag
    zul_today = bool(row_day.get("zero_utility_labor"))
    ew = row_day.get("evening_wins")
    el = row_day.get("evening_leaks")
    evening_wins_n = len(ew) if isinstance(ew, list) else 0
    evening_leaks_n = len(el) if isinstance(el, list) else 0

    dead_alerts = dead_bug_navigator.compute_dead_bug_alerts(tasks_by_id) if tasks_by_id else []
    ff_signals = firefighting_audit.detect_firefighting_signals(tasks_by_id) if tasks_by_id else []

    rag = dict(ragstone_ledger_store.load_bundle())
    rag.update(ragstone_ledger_store.computed_kpis())

    favor_clean = vanguard_health_store.rolling_utility_free_days_7d(ending=day)
    favor_streak = vanguard_health_store.favor_strike_streak_7d(ending=day)
    comm_overdue = commitments_store.has_overdue_partner()

    return {
        "date": day.isoformat(),
        "executive_score_percent": round(score, 1),
        "vanguard_executed": {
            "deep": vanguard_deep,
            "mixed": vanguard_mixed,
            "shallow": vanguard_shallow,
        },
        "runway": runway_payload,
        "kill_zones": kill_out,
        "schedule_day_signals": schedule_signals,
        "daily_landscape": landscape,
        "personal_calendar_note": personal_calendar_note,
        "identity_alert": identity_alert,
        "integrity_protocol_confirmed": proto_for_discipline,
        "work_calendar_advisory": wca,
        "work_calendar_week_gap_hint": work_cal_week_gap,
        "execution_day_summary": execution_day_summary,
        "golden_path_resolution_summary": gp_summary,
        "schedule_tradeoff_answers": tradeoff_answers,
        "golden_path_proposals": golden_path_proposals,
        "golden_path_timeline": golden_path_timeline,
        "golden_path_snoozed": snoozed,
        "integrity_habit_snapshot": integrity_habit_snapshot,
        "identity_purpose": identity_purpose,
        "sidebar_integrity": sidebar_integrity,
        "graveyard_preview": graveyard_preview,
        "morning_brief": morning_brief,
        "integrity_consistency_percent": consistency_pct,
        "integrity_sentry_state": sentry_state,
        "ops_posture_nudge_visible": nudge_vis,
        "ops_posture_nudge_message": nudge_msg,
        "focus_shell_window_active": focus_shell_eligible,
        "sacred_integrity_debt_count": sacred_debt,
        "cockpit_operator_name": cockpit_operator_name,
        "sovereignty": sovereignty_block,
        "air_gap_active": air_gap_on,
        "midday_shield_active": midday_on,
        "identity_alignment_window_active": align_on,
        "air_gap_extension_suggested": air_ext,
        "todoist_inbox_open_count": inbox_n,
        "inbox_slaughter_gate_ok": inbox_gate_ok,
        "dead_bug_alerts": dead_alerts,
        "firefighting_signals": ff_signals,
        "firewall_audit_summary": "",
        "favor_strike_days_clean_7d": favor_clean,
        "favor_strike_streak_7d": favor_streak,
        "commitments_partner_overdue": comm_overdue,
        "ragstone_ledger": rag,
        "zero_utility_labor_today": zul_today,
        "evening_wins_count": evening_wins_n,
        "evening_leaks_count": evening_leaks_n,
    }


def _build_sidebar_integrity_28d(recon_day: date) -> Dict[str, Any]:
    hist = load_protocol_history_bundle()
    bundle = load_bundle()
    neck_raw = bundle.get("neck_last_dates") or []
    neck_dates: set[str] = set()
    for x in neck_raw:
        if not isinstance(x, str):
            continue
        s = x.strip()
        if len(s) >= 10:
            neck_dates.add(s[:10])
    labels: List[str] = []
    posture_days: List[bool] = []
    neck_days: List[bool] = []
    for offset in range(27, -1, -1):
        d = recon_day - timedelta(days=offset)
        dk = d.isoformat()
        labels.append(d.strftime("%a")[:3])
        snap = hist.get(dk, {})
        posture_days.append(all(bool(snap.get(pid, False)) for pid in PROTOCOL_ITEM_IDS))
        neck_days.append(dk in neck_dates)
    return {"labels": labels, "posture_days": posture_days, "neck_days": neck_days}


def _prep_shortfall_labels(pm: int, nm: int, om: int) -> List[str]:
    labels: List[str] = []
    if pm < EXPECTED_POSTURE_MIN:
        labels.append(f"Posture −{EXPECTED_POSTURE_MIN - pm}m vs {EXPECTED_POSTURE_MIN}m target")
    if nm < EXPECTED_NECK_MIN:
        labels.append(f"Neck −{EXPECTED_NECK_MIN - nm}m vs {EXPECTED_NECK_MIN}m target")
    if om < EXPECTED_OPS_MIN:
        labels.append(f"Morning Ops −{EXPECTED_OPS_MIN - om}m vs {EXPECTED_OPS_MIN}m target")
    return labels


def _compute_identity_alert(
    day: date,
    integrity_wake: Optional[datetime],
    protocol_ok: bool,
    tzinfo,
) -> bool:
    """Past integrity wake + 15m and protocol not fully confirmed (today only)."""
    if day != date.today() or integrity_wake is None:
        return False
    iw = integrity_wake
    if iw.tzinfo is None:
        iw = iw.replace(tzinfo=tzinfo)
    else:
        iw = iw.astimezone(tzinfo)
    now = datetime.now(tzinfo)
    if now <= iw + timedelta(minutes=15):
        return False
    return not protocol_ok
