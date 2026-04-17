"""Disk-backed Power Trio state for the FastAPI cockpit (mirrors Streamlit session fields)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import identity_store
import power_trio
import todoist_service
from integrations.env_loader import env_str
from integrations.paths import data_root

STATE_PATH = data_root() / "cockpit_power_trio_state.json"
SLOT_LABELS = ("Combat", "Momentum", "Admin / Ops")

# v2: per-recon-day ranks in `days["YYYY-MM-DD"]`; v1 had global ranked_ids.
STATE_VERSION = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _day_key(d: date) -> str:
    return d.isoformat()


def _empty_day() -> Dict[str, Any]:
    return {
        "ranked_ids": [],
        "rank_warning": "",
        "last_rank_iso": "",
        "tactical_steps_by_task_id": {},
    }


def _empty_state() -> Dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "tasks_by_id": {},
        "days": {},
        "rank_warning": "",
        "last_sync_iso": "",
        "last_rank_iso": "",
        "merge_note": "",
    }


def _migrate_v1_to_v2(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Move legacy top-level ranked_ids into days[today]."""
    out = _empty_state()
    out["tasks_by_id"] = raw.get("tasks_by_id") if isinstance(raw.get("tasks_by_id"), dict) else {}
    out["last_sync_iso"] = str(raw.get("last_sync_iso") or "")
    out["merge_note"] = str(raw.get("merge_note") or "")
    rk = raw.get("ranked_ids")
    if isinstance(rk, list) and rk:
        today_k = _day_key(date.today())
        out["days"][today_k] = {
            "ranked_ids": [str(x) for x in rk if str(x).strip()],
            "rank_warning": str(raw.get("rank_warning") or ""),
            "last_rank_iso": str(raw.get("last_rank_iso") or ""),
        }
    return out


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.is_file():
        return _empty_state()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(raw, dict):
        return _empty_state()

    ver = int(raw.get("version") or 1)
    if ver < STATE_VERSION:
        raw = _migrate_v1_to_v2(raw)

    raw.setdefault("version", STATE_VERSION)
    raw.setdefault("tasks_by_id", {})
    raw.setdefault("days", {})
    raw.setdefault("rank_warning", "")
    raw.setdefault("last_sync_iso", "")
    raw.setdefault("last_rank_iso", "")
    raw.setdefault("merge_note", "")
    if not isinstance(raw["tasks_by_id"], dict):
        raw["tasks_by_id"] = {}
    if not isinstance(raw["days"], dict):
        raw["days"] = {}

    # Drop stale v1 keys on disk next save (optional hygiene)
    for k in ("ranked_ids",):
        if k in raw:
            del raw[k]

    return raw


def _get_day_bucket(state: Dict[str, Any], d: date) -> Dict[str, Any]:
    days = state.setdefault("days", {})
    if not isinstance(days, dict):
        days = {}
        state["days"] = days
    k = _day_key(d)
    if k not in days or not isinstance(days.get(k), dict):
        days[k] = _empty_day()
    b = days[k]
    b.setdefault("ranked_ids", [])
    b.setdefault("rank_warning", "")
    b.setdefault("last_rank_iso", "")
    b.setdefault("tactical_steps_by_task_id", {})
    if not isinstance(b.get("tactical_steps_by_task_id"), dict):
        b["tactical_steps_by_task_id"] = {}
    return b


def save_state(state: Dict[str, Any]) -> None:
    state = dict(state)
    state["version"] = STATE_VERSION
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_PATH)


def todoist_api_key() -> str:
    return env_str("TODOIST_API_KEY", "")


def _refresh_tactical_steps_for_day_bucket(bucket: Dict[str, Any], by_id: Dict[str, Any]) -> None:
    """After rank or complete: Gemini fills three micro-steps per top-3 task_id; persisted on bucket."""
    from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name
    from api.services import intel_service

    ranked = [str(x) for x in (bucket.get("ranked_ids") or []) if str(x).strip()][:3]
    genai, _ = configure_genai_from_env()
    tactical: Dict[str, Any] = {}
    purpose = identity_store.load_identity_purpose()
    if genai:
        for i, tid in enumerate(ranked):
            t = by_id.get(tid)
            if not t:
                continue
            title = str(t.get("content") or "")
            desc = str(t.get("description") or "")
            try:
                if i == 0:
                    steps = intel_service.gemini_immediate_physical_steps(
                        genai, gemini_model_name(), title, desc, purpose
                    )
                    if sum(1 for s in steps if str(s).strip()) < 2:
                        steps = power_trio.gemini_tactical_micro_steps(
                            genai, gemini_model_name(), title, desc
                        )
                else:
                    steps = power_trio.gemini_tactical_micro_steps(genai, gemini_model_name(), title, desc)
            except Exception:
                steps = []
            row: List[str] = [str(s).strip() for s in steps if str(s).strip()][:3]
            while len(row) < 3:
                row.append("")
            tactical[tid] = row[:3]
    bucket["tactical_steps_by_task_id"] = tactical


def ranking_context_for_day(d: date) -> Tuple[str, str, str, List[str], List[str]]:
    purpose = env_str("POWER_PURPOSE_STATEMENT", "").strip() or identity_store.load_identity_purpose()
    rstrat = env_str("POWER_RAGSTONE_STRATEGY", "")
    scaled = env_str("POWER_SCALED_OPS", "")
    id_csv = env_str("POWER_IDENTITY_PROJECT_SUBSTRINGS", "Ragstone,Home,Titan")
    op_csv = env_str("POWER_GOOGLE_OPS_SUBSTRINGS", "Google,Work")
    id_sub = power_trio.split_substrings_csv(id_csv)
    op_sub = power_trio.split_substrings_csv(op_csv)
    return purpose, rstrat, scaled, id_sub, op_sub


def sync_tasks() -> Tuple[Dict[str, Any], int, str]:
    """Fetch Todoist tasks; merge ranked_cache if API empty. Updates disk state."""
    key = todoist_api_key()
    if not key:
        raise RuntimeError("TODOIST_API_KEY not set.")

    raw = todoist_service.fetch_all_tasks_rest_v2(key)
    pmap = todoist_service.fetch_todoist_projects(key)
    try:
        label_map = todoist_service.fetch_todoist_label_id_to_name(key)
    except Exception:
        label_map = {}
    by_id: Dict[str, Any] = {}
    for t in raw:
        nt = todoist_service.normalize_power_task(t, pmap, label_map)
        tid = nt.get("id")
        if tid:
            by_id[str(tid)] = nt
    by_id, merge_msg = todoist_service.merge_tasks_from_cache_if_api_empty(by_id, len(raw))

    state = load_state()
    state["tasks_by_id"] = by_id
    state["rank_warning"] = ""
    state["merge_note"] = merge_msg
    state["last_sync_iso"] = _utc_now_iso()
    # Prune dead task ids from each day's ranked_ids
    valid = set(by_id.keys())
    days = state.get("days")
    if isinstance(days, dict):
        for _dk, bucket in list(days.items()):
            if not isinstance(bucket, dict):
                continue
            rids = bucket.get("ranked_ids")
            if isinstance(rids, list):
                bucket["ranked_ids"] = [x for x in rids if str(x).strip() in valid]
    save_state(state)
    return state, len(by_id), merge_msg


def rank_tasks_for_day(day: date) -> Dict[str, Any]:
    """Gemini rank (or priority fallback). Requires non-empty tasks_by_id."""
    from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name

    genai, err = configure_genai_from_env()
    state = load_state()
    by_id: Dict[str, Any] = dict(state.get("tasks_by_id") or {})
    if not by_id:
        raise RuntimeError("No tasks loaded. POST /api/todoist/sync first.")

    purpose, rstrat, scaled, id_sub, op_sub = ranking_context_for_day(day)
    wd = day.strftime("%A")
    is_weekend = day.weekday() >= 5
    local_hour = datetime.now().astimezone().hour
    drain_profile = identity_store.load_identity_drain_profile()

    if genai is None:
        ranked = todoist_service.sort_known_ids_by_priority(by_id, list(by_id.keys()))
        ranked = todoist_service.apply_peak_cognitive_drain_guard(
            ranked, by_id, drain_profile, local_hour
        )
        warn = err or "Gemini not configured; using Todoist priority order."
    else:
        ranked, warn = power_trio.rank_tasks_for_power_trio(
            genai,
            gemini_model_name(),
            by_id,
            purpose,
            rstrat,
            scaled,
            wd,
            is_weekend,
            id_sub,
            op_sub,
            drain_profile=drain_profile,
            local_hour=local_hour,
        )

    bucket = _get_day_bucket(state, day)
    bucket["ranked_ids"] = ranked
    bucket["rank_warning"] = warn or ""
    bucket["last_rank_iso"] = _utc_now_iso()
    _refresh_tactical_steps_for_day_bucket(bucket, by_id)
    state["version"] = STATE_VERSION
    save_state(state)
    todoist_service.save_ranked_cache(ranked, by_id, day=day)
    return state


def trio_payload(state: Optional[Dict[str, Any]] = None, *, day: Optional[date] = None) -> Dict[str, Any]:
    state = state or load_state()
    d = day or date.today()
    bucket = _get_day_bucket(state, d)
    by_id: Dict[str, Any] = dict(state.get("tasks_by_id") or {})
    ranked: List[str] = [str(x) for x in (bucket.get("ranked_ids") or []) if str(x).strip()]
    ts_map_raw = bucket.get("tactical_steps_by_task_id")
    ts_map: Dict[str, Any] = ts_map_raw if isinstance(ts_map_raw, dict) else {}
    slots = []
    for i, tid in enumerate(ranked[:3]):
        t = by_id.get(tid)
        if not t:
            continue
        raw_steps = ts_map.get(tid)
        steps: List[str] = []
        if isinstance(raw_steps, list):
            steps = [str(s).strip() for s in raw_steps[:3]]
        while len(steps) < 3:
            steps.append("")
        slots.append(
            {
                "slot": i,
                "label": SLOT_LABELS[i] if i < len(SLOT_LABELS) else f"Slot {i + 1}",
                "task_id": tid,
                "title": str(t.get("content") or "(no title)"),
                "description": str(t.get("description") or ""),
                "project_name": str(t.get("project_name") or ""),
                "priority": int(t.get("priority") or 1),
                "tactical_steps": steps[:3],
            }
        )
    return {
        "slots": slots,
        "ranked_total": len(ranked),
        "task_total": len(by_id),
        "rank_warning": str(bucket.get("rank_warning") or ""),
        "merge_note": str(state.get("merge_note") or ""),
        "last_sync_iso": str(state.get("last_sync_iso") or ""),
        "last_rank_iso": str(bucket.get("last_rank_iso") or ""),
        "recon_day": _day_key(d),
    }


def complete_task(task_id: str, day: Optional[date] = None) -> Dict[str, Any]:
    key = todoist_api_key()
    if not key:
        raise RuntimeError("TODOIST_API_KEY not set.")
    tid = str(task_id).strip()
    if not tid:
        raise ValueError("task_id required")

    d = day or date.today()

    todoist_service.close_task_rest_v2(key, tid)

    state = load_state()
    bucket = _get_day_bucket(state, d)
    ranked = list(bucket.get("ranked_ids") or [])
    by_id: Dict[str, Any] = dict(state.get("tasks_by_id") or {})

    ranked_new = todoist_service.sliding_trio_after_complete(ranked, tid)
    by_id.pop(tid, None)
    bucket["ranked_ids"] = ranked_new
    state["tasks_by_id"] = by_id
    _refresh_tactical_steps_for_day_bucket(bucket, by_id)
    save_state(state)
    todoist_service.save_ranked_cache(ranked_new, by_id, day=d)
    return state


def gemini_plan_or_strike(task_id: str, mode: str) -> str:
    """mode: 'plan' | 'strike'."""
    from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name

    state = load_state()
    by_id: Dict[str, Any] = dict(state.get("tasks_by_id") or {})
    t = by_id.get(str(task_id).strip())
    if not t:
        raise ValueError("Unknown task_id (sync and rank first).")

    genai, err = configure_genai_from_env()
    if genai is None:
        raise RuntimeError(err or "Gemini not configured.")

    title = str(t.get("content") or "")
    desc = str(t.get("description") or "")
    if mode == "plan":
        return power_trio.gemini_the_plan_three_steps(genai, gemini_model_name(), title, desc)
    if mode == "strike":
        return power_trio.gemini_quick_execution(genai, gemini_model_name(), title, desc)
    raise ValueError("mode must be 'plan' or 'strike'")
