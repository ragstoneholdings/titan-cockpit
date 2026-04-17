"""
Todoist REST v2 client with timeouts, disk cache for ranked tasks, and Gemini ranking with deadline fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

logger = logging.getLogger(__name__)

# Todoist REST v2 is deprecated (410); unified API v1 replaces it.
TODOIST_API_V1 = "https://api.todoist.com/api/v1"
ROOT = Path(__file__).resolve().parent
RANKED_CACHE_FILENAME = "ranked_cache.json"
RANKED_CACHE_PATH = ROOT / RANKED_CACHE_FILENAME

# Timeouts (seconds) — hangs are usually network or Gemini without limits.
TIMEOUT_PROJECTS = 45
TIMEOUT_TASKS = 60
TIMEOUT_CLOSE = 45
GEMINI_RANK_JOIN_TIMEOUT_SEC = 120

MAX_TASKS_RANK = 200


def ranked_cache_path() -> Path:
    return RANKED_CACHE_PATH


def _headers(api_key: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {api_key}"}


def _paginate_v1_list(api_key: str, path: str, page_limit: int = 200) -> List[Dict[str, Any]]:
    """GET /api/v1/... endpoints that return {results, next_cursor}."""
    if not requests:
        return []
    out: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    for _ in range(500):
        params: Dict[str, Any] = {"limit": min(max(page_limit, 1), 200)}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(
            f"{TODOIST_API_V1}{path}",
            headers=_headers(api_key),
            params=params,
            timeout=TIMEOUT_TASKS,
        )
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            _log_http_failure(f"_paginate_v1_list:{path}", e)
            raise
        data = r.json()
        if not isinstance(data, dict):
            break
        batch = data.get("results")
        if not isinstance(batch, list):
            break
        out.extend(t for t in batch if isinstance(t, dict))
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return out


def _snippet(text: Optional[str], n: int = 400) -> str:
    if not text:
        return ""
    t = str(text).strip()
    return t[:n] + ("…" if len(t) > n else "")


def _log_http_failure(where: str, exc: BaseException) -> str:
    if requests and isinstance(exc, requests.exceptions.HTTPError):
        resp = getattr(exc, "response", None)
        if resp is not None:
            code = getattr(resp, "status_code", "?")
            body = _snippet(getattr(resp, "text", None))
            msg = f"{where}: HTTP {code} body={body!r}"
            logger.warning(msg)
            return msg
    msg = f"{where}: {exc!r}"
    logger.warning(msg)
    return msg


def fetch_todoist_label_id_to_name(api_key: str) -> Dict[str, str]:
    """Todoist API v1: label id -> display name (for resolving task label_ids)."""
    data = _paginate_v1_list(api_key, "/labels", page_limit=200)
    out: Dict[str, str] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        if row.get("is_deleted"):
            continue
        lid = str(row.get("id") or "").strip()
        nm = str(row.get("name") or "").strip() or "(label)"
        if lid:
            out[lid] = nm
    return out


def fetch_todoist_projects(api_key: str) -> Dict[str, str]:
    """project_id -> project name (Todoist API v1)."""
    if not requests:
        return {}
    data = _paginate_v1_list(api_key, "/projects", page_limit=200)
    out: Dict[str, str] = {}
    for p in data:
        if not isinstance(p, dict):
            continue
        if p.get("is_deleted") or p.get("is_archived"):
            continue
        pid = str(p.get("id") or "").strip()
        name = str(p.get("name") or "").strip() or "(project)"
        if pid:
            out[pid] = name
    return out


def fetch_all_tasks_rest_v2(api_key: str) -> List[Dict[str, Any]]:
    """Active tasks via Todoist API v1 (name kept for power_trio / callers)."""
    if not requests:
        return []
    raw = _paginate_v1_list(api_key, "/tasks", page_limit=200)
    return [
        t
        for t in raw
        if isinstance(t, dict) and not t.get("checked") and not t.get("is_deleted")
    ]


def _task_label_names_from_raw(raw: Dict[str, Any], label_id_to_name: Dict[str, str]) -> List[str]:
    names: List[str] = []
    labs = raw.get("labels")
    if isinstance(labs, list):
        for x in labs:
            if isinstance(x, str) and x.strip():
                names.append(x.strip())
            elif isinstance(x, dict):
                n = str(x.get("name") or "").strip()
                if n:
                    names.append(n)
    lids = raw.get("label_ids")
    if isinstance(lids, list):
        for lid in lids:
            lk = str(lid).strip()
            if lk in label_id_to_name:
                names.append(label_id_to_name[lk])
    return list(dict.fromkeys(names))


def _due_date_iso_from_raw(raw: Dict[str, Any]) -> str:
    due = raw.get("due")
    if isinstance(due, dict):
        s = str(due.get("datetime") or due.get("date") or "").strip()
        if "T" in s:
            return s[:10]
        if len(s) >= 10:
            return s[:10]
    return ""


def normalize_power_task(
    raw: Dict[str, Any],
    project_names: Dict[str, str],
    label_id_to_name: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    lid_map = label_id_to_name or {}
    pid = str(raw.get("project_id") or "").strip()
    return {
        "id": str(raw.get("id") or "").strip(),
        "content": str(raw.get("content") or "").strip(),
        "description": str(raw.get("description") or "").strip(),
        "priority": int(raw.get("priority") or 1),
        "project_id": pid,
        "project_name": project_names.get(pid, ""),
        "labels": _task_label_names_from_raw(raw, lid_map),
        "due_date": _due_date_iso_from_raw(raw),
        "updated_at": str(raw.get("updated_at") or raw.get("created_at") or "").strip(),
    }


def add_task_v1(
    api_key: str,
    *,
    content: str,
    description: str = "",
    priority: int = 1,
    labels: Optional[List[str]] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a task via Todoist REST API v1 (`POST /api/v1/tasks`)."""
    if not requests:
        return {"error": "requests_unavailable"}
    body: Dict[str, Any] = {
        "content": (content or "").strip()[:500],
        "priority": max(1, min(4, int(priority or 1))),
    }
    desc = (description or "").strip()
    if desc:
        body["description"] = desc[:16000]
    if labels:
        body["labels"] = [str(x).strip() for x in labels if str(x).strip()][:50]
    if project_id and str(project_id).strip():
        body["project_id"] = str(project_id).strip()
    r = requests.post(
        f"{TODOIST_API_V1}/tasks",
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=body,
        timeout=TIMEOUT_CLOSE,
    )
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        _log_http_failure("add_task_v1", e)
        raise
    data = r.json()
    return data if isinstance(data, dict) else {"raw": data}


def count_inbox_open_tasks(api_key: str) -> Tuple[int, Optional[str]]:
    """Count active tasks in the Todoist Inbox project (by project name 'Inbox')."""
    if not requests:
        return 0, None
    pmap = fetch_todoist_projects(api_key)
    inbox_id: Optional[str] = None
    for pid, name in pmap.items():
        if str(name).strip().lower() == "inbox":
            inbox_id = pid
            break
    if not inbox_id:
        return 0, None
    raw_tasks = fetch_all_tasks_rest_v2(api_key)
    n = sum(1 for t in raw_tasks if isinstance(t, dict) and str(t.get("project_id") or "") == inbox_id)
    return n, inbox_id


def close_task_rest_v2(api_key: str, task_id: str) -> None:
    if not requests:
        raise RuntimeError("requests not installed")
    tid = str(task_id).strip()
    if not tid:
        raise ValueError("task_id required")
    r = requests.post(
        f"{TODOIST_API_V1}/tasks/{tid}/close",
        headers=_headers(api_key),
        timeout=TIMEOUT_CLOSE,
    )
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        _log_http_failure("close_task_rest_v2", e)
        raise


def reopen_task_rest_v1(api_key: str, task_id: str) -> None:
    """Undo complete: restore a closed task as active (Todoist REST v1)."""
    if not requests:
        raise RuntimeError("requests not installed")
    tid = str(task_id).strip()
    if not tid:
        raise ValueError("task_id required")
    r = requests.post(
        f"{TODOIST_API_V1}/tasks/{tid}/reopen",
        headers=_headers(api_key),
        timeout=TIMEOUT_CLOSE,
    )
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        _log_http_failure("reopen_task_rest_v1", e)
        raise


def reopen_tasks_for_ids(api_key: str, task_ids: List[str]) -> Tuple[int, List[str], List[str]]:
    """
    Reopen each completed task id. Returns (success_count, error_messages, reopened_ids).
    Continues on per-task failure.
    """
    seen: set[str] = set()
    errs: List[str] = []
    ok_ids: List[str] = []
    for raw in task_ids:
        tid = str(raw or "").strip()
        if not tid or tid in seen:
            continue
        seen.add(tid)
        try:
            reopen_task_rest_v1(api_key, tid)
            ok_ids.append(tid)
        except Exception as e:  # noqa: BLE001
            errs.append(f"{tid}: {e!s}")
    return len(ok_ids), errs, ok_ids


def validate_and_fill_order(ordered_ids: List[str], known_ids: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    known_set = list(dict.fromkeys(known_ids))
    for oid in ordered_ids:
        s = str(oid).strip()
        if s and s in known_set and s not in seen:
            seen.add(s)
            out.append(s)
    for kid in known_set:
        if kid not in seen:
            out.append(kid)
    return out


def sort_known_ids_by_priority(by_id: Dict[str, Any], known_ids: List[str]) -> List[str]:
    """Fallback ordering when Gemini fails or times out (Todoist priority: 4 highest)."""

    def key(tid: str) -> Tuple[int, str]:
        t = by_id.get(tid) or {}
        pr = int(t.get("priority") or 1)
        return (-pr, tid)

    return sorted([k for k in known_ids if k in by_id], key=key)


def task_energy_drain_level(task: Dict[str, Any], drain_profile: Optional[Dict[str, Any]]) -> str:
    """Classify a normalized task for peak-hours ranking rules (labels + title + description)."""
    prof = drain_profile or {}
    parts: List[str] = [str(task.get("content") or ""), str(task.get("description") or "")]
    labs = task.get("labels")
    if isinstance(labs, list):
        parts.extend(str(x) for x in labs if str(x).strip())
    blob = " ".join(parts).lower()
    for tok in prof.get("high_drain_labels") or []:
        t = str(tok).lower().strip()
        if t and t in blob:
            return "high"
    for sub in prof.get("high_drain_title_substrings") or []:
        s = str(sub).lower().strip()
        if s and s in blob:
            return "high"
    return "normal"


def _peak_cognitive_bounds() -> tuple[int, int]:
    try:
        a = int(os.environ.get("PEAK_COGNITIVE_START_HOUR", "8") or 8)
    except ValueError:
        a = 8
    try:
        b = int(os.environ.get("PEAK_COGNITIVE_END_HOUR", "11") or 11)
    except ValueError:
        b = 11
    if b <= a:
        b = min(23, a + 1)
    return a, b


def apply_peak_cognitive_drain_guard(
    ranked: List[str],
    by_id: Dict[str, Any],
    drain_profile: Optional[Dict[str, Any]],
    local_hour: Optional[int],
) -> List[str]:
    """If local hour is in peak window and drain_profile is configured, demote high-drain from slots 1–2."""
    if local_hour is None or not ranked:
        return ranked
    a, b = _peak_cognitive_bounds()
    if not (a <= local_hour < b):
        return ranked
    prof = drain_profile or {}
    if not (prof.get("high_drain_labels") or prof.get("high_drain_title_substrings")):
        return ranked

    def _lvl(tid: str) -> str:
        return task_energy_drain_level(by_id.get(tid) or {}, prof)

    out = list(ranked)
    if out and _lvl(out[0]) == "high":
        for i in range(1, len(out)):
            if _lvl(out[i]) != "high":
                out[0], out[i] = out[i], out[0]
                break
    if len(out) >= 2 and _lvl(out[1]) == "high":
        for j in range(2, len(out)):
            if _lvl(out[j]) != "high":
                out[1], out[j] = out[j], out[1]
                break
    return out


def _gemini_rank_tasks_inner(
    genai_module: Any,
    model_name: str,
    tasks_payload: List[Dict[str, Any]],
    purpose: str,
    ragstone_strategy: str,
    scaled_ops: str,
    weekday_name: str,
    is_weekend: bool,
    identity_project_substr: List[str],
    google_ops_substr: List[str],
    *,
    local_hour: Optional[int] = None,
) -> Tuple[List[str], str]:
    """Synchronous rank; run inside a thread with join timeout from the caller."""
    model = genai_module.GenerativeModel(model_name)
    rules = ""
    if is_weekend:
        rules = (
            "WEEKEND ISOLATION (Saturday/Sunday): Strongly prefer tasks whose project_name matches identity "
            f"hints {identity_project_substr!r} (Ragstone, hypertrophy, deep work, home). "
            f"Demote tasks whose project_name matches Google / corporate ops hints {google_ops_substr!r}. "
            "Do not let Google Ops crowd out identity execution (e.g. early Saturday training blocks).\n"
        )
    peak_extra = ""
    if local_hour is not None:
        ps, pe = _peak_cognitive_bounds()
        if ps <= int(local_hour) < pe:
            peak_extra = (
                f"\nPEAK COGNITIVE WINDOW (operator local hour {local_hour}, window {ps}:00–{pe}:00):\n"
                '- Each task may include "energy_drain": "high" or "normal".\n'
                '- Do NOT place any energy_drain "high" task in position 1 (and avoid positions 1–2) '
                "unless every task in the list is high-drain.\n"
            )

    prompt = f"""You rank Todoist tasks by Impact vs Identity Alignment for an executive operator.

Today is {weekday_name}. {"Weekend rules apply." if is_weekend else "Standard weekday ranking."}
Operator local hour (24h): {local_hour if local_hour is not None else "(unknown)"}.

{rules}

Life purpose / Titan identity:
{purpose or "(not set)"}

Ragstone Strategy (execution thesis, portfolio priorities):
{ragstone_strategy or "(not set)"}

Google Scaled Ops context (weekday weight; demote on weekends per rules above):
{scaled_ops or "(not set)"}
{peak_extra}
Tasks (JSON array of objects with id, content, project_name, energy_drain):
{json.dumps(tasks_payload[:MAX_TASKS_RANK], ensure_ascii=False)}

Reply with ONLY valid JSON, no markdown:
{{"ordered_ids": ["<task id strings in best order>", ...]}}
Include every task id exactly once. Deprioritize fluff; surface heavy hitters first.
Task 1 in ordered_ids must be the single highest ROI / identity-alignment move for today."""
    resp = model.generate_content(prompt)
    text = (resp.text or "").strip()
    m = re.search(r"\{[^{}]*\"ordered_ids\"[^{}]*\}", text, re.DOTALL)
    if not m:
        m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return [], text
    try:
        obj = json.loads(m.group())
        ids = obj.get("ordered_ids")
        if not isinstance(ids, list):
            return [], text
        parsed = [str(x).strip() for x in ids if str(x).strip()]
        return parsed, text
    except json.JSONDecodeError:
        return [], text


def gemini_rank_tasks(
    genai_module: Any,
    model_name: str,
    tasks_payload: List[Dict[str, Any]],
    purpose: str,
    ragstone_strategy: str,
    scaled_ops: str,
    weekday_name: str,
    is_weekend: bool,
    identity_project_substr: List[str],
    google_ops_substr: List[str],
    *,
    local_hour: Optional[int] = None,
) -> Tuple[List[str], str]:
    """
    Returns ordered task ids (may be empty before validate_and_fill_order) and raw model text.
    Enforces a wall-clock deadline via thread join so the UI does not hang indefinitely.
    """
    result: List[Optional[Any]] = [None]
    error: List[Optional[BaseException]] = [None]

    def target() -> None:
        try:
            result[0] = _gemini_rank_tasks_inner(
                genai_module,
                model_name,
                tasks_payload,
                purpose,
                ragstone_strategy,
                scaled_ops,
                weekday_name,
                is_weekend,
                identity_project_substr,
                google_ops_substr,
                local_hour=local_hour,
            )
        except BaseException as e:  # noqa: BLE001 — propagate any model/SDK failure
            error[0] = e

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(GEMINI_RANK_JOIN_TIMEOUT_SEC)
    if th.is_alive():
        logger.warning("gemini_rank_tasks: join timeout after %ss", GEMINI_RANK_JOIN_TIMEOUT_SEC)
        return [], "(rank timed out)"
    if error[0] is not None:
        logger.warning("gemini_rank_tasks: %r", error[0])
        return [], str(error[0])
    pair = result[0]
    if not isinstance(pair, tuple) or len(pair) != 2:
        return [], ""
    ids, text = pair
    return (ids if isinstance(ids, list) else []), str(text or "")


def rank_tasks_for_power_trio(
    genai_module: Any,
    model_name: str,
    by_id: Dict[str, Any],
    purpose: str,
    ragstone_strategy: str,
    scaled_ops: str,
    weekday_name: str,
    is_weekend: bool,
    identity_project_substr: List[str],
    google_ops_substr: List[str],
    *,
    drain_profile: Optional[Dict[str, Any]] = None,
    local_hour: Optional[int] = None,
) -> Tuple[List[str], str]:
    """
    Full rank pipeline: Gemini (with timeout) then validate_and_fill_order.
    If Gemini yields no valid ordered_ids before merge, falls back to Todoist priority sort.
    Returns (ranked_ids, warning_or_empty).
    """
    known = list(by_id.keys())
    payload = []
    for tid, v in by_id.items():
        row = {
            "id": tid,
            "content": v.get("content"),
            "project_name": v.get("project_name"),
            "energy_drain": task_energy_drain_level(v, drain_profile),
        }
        payload.append(row)
    ordered, raw_text = gemini_rank_tasks(
        genai_module,
        model_name,
        payload,
        purpose,
        ragstone_strategy,
        scaled_ops,
        weekday_name,
        is_weekend,
        identity_project_substr,
        google_ops_substr,
        local_hour=local_hour,
    )
    warning = ""
    if not ordered:
        warning = (
            "Gemini returned no usable ordered_ids (empty, timeout, or parse error). "
            "Using Todoist priority fallback."
        )
        if raw_text and len(raw_text) < 200:
            warning += f" Raw: {raw_text!r}"
        ordered = sort_known_ids_by_priority(by_id, known)
    ranked = validate_and_fill_order(ordered, known)
    ranked = apply_peak_cognitive_drain_guard(ranked, by_id, drain_profile, local_hour)
    if not ranked:
        warning = warning or "Ranking produced an empty list; check tasks."
    return ranked, warning


def save_ranked_cache(
    ordered_ids: List[str],
    tasks_by_id: Dict[str, Any],
    *,
    day: Optional[date] = None,
) -> None:
    """Persist last successful rank for offline debugging (cockpit state is source of truth)."""
    serializable = {k: tasks_by_id[k] for k in ordered_ids if k in tasks_by_id}
    dkey = day.isoformat() if day else ""
    payload: Dict[str, Any] = {
        "version": 2,
        "ordered_ids": list(ordered_ids),
        "tasks_by_id": serializable,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "day": dkey,
    }
    try:
        raw_existing: Optional[Dict[str, Any]] = None
        if RANKED_CACHE_PATH.is_file():
            try:
                raw_existing = json.loads(RANKED_CACHE_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                raw_existing = None
        days: Dict[str, Any] = {}
        if isinstance(raw_existing, dict) and isinstance(raw_existing.get("days"), dict):
            days = dict(raw_existing["days"])
        if dkey:
            days[dkey] = {
                "ordered_ids": list(ordered_ids),
                "tasks_by_id": serializable,
                "updated_at": payload["updated_at"],
            }
        payload["days"] = days
        RANKED_CACHE_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        logger.warning("save_ranked_cache: %s", e)


def load_ranked_cache() -> Optional[Dict[str, Any]]:
    if not RANKED_CACHE_PATH.is_file():
        return None
    try:
        raw = json.loads(RANKED_CACHE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def merge_tasks_from_cache_if_api_empty(
    by_id: Dict[str, Any],
    raw_task_count: int,
) -> Tuple[Dict[str, Any], str]:
    """
    If the REST response was empty but disk cache exists, merge cached tasks for offline debugging.
    """
    if raw_task_count > 0 or by_id:
        return by_id, ""
    cached = load_ranked_cache()
    if not cached:
        return by_id, ""
    tb = cached.get("tasks_by_id")
    if not isinstance(tb, dict):
        days = cached.get("days") if isinstance(cached.get("days"), dict) else {}
        # Prefer most recently updated day bucket
        best_tb: Optional[Dict[str, Any]] = None
        best_ts = ""
        for _dk, bucket in days.items():
            if not isinstance(bucket, dict):
                continue
            tbx = bucket.get("tasks_by_id")
            if isinstance(tbx, dict):
                u = str(bucket.get("updated_at") or "")
                if u >= best_ts:
                    best_ts = u
                    best_tb = tbx
        tb = best_tb or {}
    if not isinstance(tb, dict):
        return by_id, ""
    merged = dict(by_id)
    n = 0
    for k, v in tb.items():
        ks = str(k).strip()
        if ks and isinstance(v, dict) and ks not in merged:
            merged[ks] = v
            n += 1
    if n:
        return merged, f"API returned 0 tasks; merged **{n}** from `{RANKED_CACHE_FILENAME}` (offline debug)."
    return by_id, ""


def todoist_auth_error_hint(exc: BaseException) -> str:
    if not requests or not isinstance(exc, requests.exceptions.HTTPError):
        return ""
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None) if resp is not None else None
    if code in (401, 403):
        return " Check **TODOIST_API_KEY** (401/403: invalid or revoked token)."
    return ""


def _parse_task_timestamp(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    raw = str(s).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def janitor_close_stale_open_tasks(
    api_key: str,
    *,
    max_age_days: int = 14,
    preserve_substr: str = "@Titan_Core",
) -> Tuple[int, str, List[Dict[str, Any]]]:
    """
    Close (complete) open tasks older than max_age_days unless content/description
    contains preserve_substr (default @Titan_Core). Returns (count, error hint, closed log).
    """
    raw = fetch_all_tasks_rest_v2(api_key)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    ps = (preserve_substr or "").strip()
    n_closed = 0
    errs: List[str] = []
    closed_log: List[Dict[str, Any]] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "").strip()
        if not tid:
            continue
        blob = f"{t.get('content') or ''} {t.get('description') or ''}"
        if _janitor_preserve_match(blob, ps):
            continue
        ts = _parse_task_timestamp(
            str(t.get("added_at") or t.get("created_at") or "").strip() or None
        )
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        if ts > cutoff:
            continue
        title = str(t.get("content") or "(no title)")
        try:
            close_task_rest_v2(api_key, tid)
            n_closed += 1
            closed_log.append(
                {
                    "task_id": tid,
                    "title": title,
                    "closed_at": now.isoformat(),
                }
            )
        except Exception as e:  # noqa: BLE001
            errs.append(f"{tid}:{e!s}")
    hint = ""
    if errs:
        hint = "Janitor errors (first few): " + "; ".join(errs[:5])
    return n_closed, hint, closed_log


# Fluff auto-close: case-insensitive title/description substring matches (extend as needed).
AUTO_ARCHIVE_TITLE_SUBSTRINGS: Tuple[str, ...] = (
    "check latest news",
    "read newsletter",
    "browse twitter",
    "scroll social",
    "watch youtube",
    "read rss",
)
AUTO_ARCHIVE_PRESERVE_SUBSTRINGS: Tuple[str, ...] = (
    "@titan_core",
    "titan_core",
)


def _janitor_sacred_substrings() -> List[str]:
    raw = (os.environ.get("JANITOR_SACRED_SUBSTRINGS") or "").strip()
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


def _janitor_preserve_match(blob: str, preserve_substr: str) -> bool:
    """Do not close tasks matching @Titan_Core, explicit preserve token, or sacred name list."""
    blob_l = blob.lower()
    ps = (preserve_substr or "").strip().lower()
    if ps and ps in blob_l:
        return True
    if "@titan_core" in blob_l or "titan_core" in blob_l:
        return True
    for s in _janitor_sacred_substrings():
        if s and s in blob_l:
            return True
    return False


def janitor_auto_archive_fluff_enabled() -> bool:
    v = (os.environ.get("JANITOR_AUTO_ARCHIVE_FLUFF") or "").strip().lower()
    return v in ("1", "true", "yes", "on")


def _task_blob_matches_auto_archive_fluff(content: str, description: str) -> bool:
    blob = f"{content} {description}".lower()
    for pres in AUTO_ARCHIVE_PRESERVE_SUBSTRINGS:
        if pres.lower() in blob:
            return False
    for s in _janitor_sacred_substrings():
        if s and s in blob:
            return False
    for frag in AUTO_ARCHIVE_TITLE_SUBSTRINGS:
        if frag.lower() in blob:
            return True
    return False


def janitor_auto_archive_fluff(api_key: str) -> Tuple[int, str, List[Dict[str, Any]]]:
    """
    Close open tasks that match fluff heuristics (any age). Silent in UI; caller logs to graveyard.
    Gated by env JANITOR_AUTO_ARCHIVE_FLUFF=1.
    """
    if not janitor_auto_archive_fluff_enabled():
        return 0, "", []
    raw = fetch_all_tasks_rest_v2(api_key)
    now = datetime.now(timezone.utc)
    n_closed = 0
    errs: List[str] = []
    closed_log: List[Dict[str, Any]] = []
    for t in raw:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "").strip()
        if not tid:
            continue
        title = str(t.get("content") or "")
        desc = str(t.get("description") or "")
        if not _task_blob_matches_auto_archive_fluff(title, desc):
            continue
        try:
            close_task_rest_v2(api_key, tid)
            n_closed += 1
            closed_log.append(
                {
                    "task_id": tid,
                    "title": title or "(no title)",
                    "closed_at": now.isoformat(),
                }
            )
        except Exception as e:  # noqa: BLE001
            errs.append(f"{tid}:{e!s}")
    hint = ""
    if errs:
        hint = "Auto-fluff errors (first few): " + "; ".join(errs[:5])
    return n_closed, hint, closed_log


def sliding_trio_after_complete(ranked_ids: List[str], completed_id: str) -> List[str]:
    """Remove completed id; positions 2–3 slide up; former slot 3 is refilled from rank tail."""
    cid = str(completed_id).strip()
    return [x for x in ranked_ids if str(x).strip() != cid]
