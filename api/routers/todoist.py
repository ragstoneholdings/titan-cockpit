"""Todoist Power Trio endpoints (sync, rank, complete, Gemini assists)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from api.schemas.todoist import (
    CompleteBody,
    CompleteResponse,
    GeminiAssistBody,
    GeminiAssistResponse,
    GraveyardReopenBody,
    GraveyardReopenResponse,
    PowerTrioSlot,
    PowerTrioView,
    RankResponse,
    SyncResponse,
    TodoistStatusResponse,
)
from api.services import power_trio_state as pts
from api.services.gemini_runtime import configure_genai_from_env
from graveyard_store import append_entries, list_entries
from integrations.paths import data_root

router = APIRouter(prefix="/todoist", tags=["todoist"])

JANITOR_GRAVEYARD_SOURCES = frozenset({"janitor", "janitor_auto"})


def _parse_day(s: Optional[str]) -> date:
    if not s or not str(s).strip():
        return date.today()
    try:
        return date.fromisoformat(str(s).strip()[:10])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid day: {s}") from e


@router.get("/status", response_model=TodoistStatusResponse)
def todoist_status() -> TodoistStatusResponse:
    key_ok = bool(pts.todoist_api_key())
    genai, _ = configure_genai_from_env()
    dr = data_root()
    try:
        state_rel = str(pts.STATE_PATH.relative_to(dr))
    except ValueError:
        state_rel = str(pts.STATE_PATH)
    return TodoistStatusResponse(
        todoist_configured=key_ok,
        gemini_configured=genai is not None,
        state_path=state_rel,
    )


def _view_from_state(state: Optional[dict] = None, *, day: Optional[date] = None) -> PowerTrioView:
    d = day or date.today()
    raw = pts.trio_payload(state, day=d)
    slots = [PowerTrioSlot(**s) for s in raw["slots"]]
    return PowerTrioView(
        slots=slots,
        ranked_total=raw["ranked_total"],
        task_total=raw["task_total"],
        rank_warning=raw["rank_warning"],
        merge_note=raw["merge_note"],
        last_sync_iso=raw["last_sync_iso"],
        last_rank_iso=raw["last_rank_iso"],
        recon_day=raw.get("recon_day") or d.isoformat(),
    )


@router.get("/power-trio", response_model=PowerTrioView)
def get_power_trio(day: Optional[date] = Query(None, description="Recon date (defaults to today)")) -> PowerTrioView:
    d = day or date.today()
    return _view_from_state(None, day=d)


@router.post("/sync", response_model=SyncResponse)
def post_sync() -> SyncResponse:
    try:
        _state, n, merge_msg = pts.sync_tasks()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e)) from e
    return SyncResponse(task_count=n, merge_note=merge_msg or "")


@router.post("/rank", response_model=RankResponse)
def post_rank(day: Optional[date] = Query(None, description="Recon date (weekday/weekend rules)")) -> RankResponse:
    d = day or date.today()
    try:
        state = pts.rank_tasks_for_day(d)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e)) from e
    v = _view_from_state(state, day=d)
    return RankResponse(rank_warning=v.rank_warning, trio=v)


@router.post("/complete", response_model=CompleteResponse)
def post_complete(body: CompleteBody) -> CompleteResponse:
    d = _parse_day(body.day)
    try:
        state = pts.complete_task(body.task_id, day=d)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e)) from e
    return CompleteResponse(trio=_view_from_state(state, day=d))


@router.post("/assist", response_model=GeminiAssistResponse)
def post_assist(body: GeminiAssistBody) -> GeminiAssistResponse:
    mode = (body.mode or "").strip().lower()
    if mode not in ("plan", "strike"):
        raise HTTPException(status_code=400, detail="mode must be 'plan' or 'strike'")
    try:
        text = pts.gemini_plan_or_strike(body.task_id, mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e)) from e
    return GeminiAssistResponse(text=text)


@router.post("/janitor")
def post_janitor() -> dict[str, Any]:
    key = pts.todoist_api_key()
    if not key:
        raise HTTPException(status_code=503, detail="TODOIST_API_KEY not set.")
    from todoist_service import janitor_auto_archive_fluff, janitor_close_stale_open_tasks

    n, hint, closed_log = janitor_close_stale_open_tasks(key)
    appended = append_entries(closed_log, source="janitor")
    n_fluff, hint_fluff, fluff_log = janitor_auto_archive_fluff(key)
    appended_fluff = append_entries(fluff_log, source="janitor_auto")
    hints = [x for x in (hint, hint_fluff) if str(x).strip()]
    return {
        "ok": True,
        "closed_count": n,
        "auto_fluff_closed_count": n_fluff,
        "hint": " ".join(hints).strip(),
        "graveyard_appended": appended + appended_fluff,
    }


@router.get("/graveyard")
def get_graveyard(limit: int = Query(200, ge=1, le=2000)) -> dict[str, Any]:
    return {"entries": list_entries(limit=limit)}


@router.post("/graveyard/reopen", response_model=GraveyardReopenResponse)
def post_graveyard_reopen(body: GraveyardReopenBody) -> GraveyardReopenResponse:
    """Reopen Todoist tasks that the janitor closed (graveyard source janitor / janitor_auto)."""
    key = pts.todoist_api_key()
    if not key:
        raise HTTPException(status_code=503, detail="TODOIST_API_KEY not set.")
    want = [str(x).strip() for x in (body.task_ids or []) if str(x).strip()]
    if not want:
        raise HTTPException(status_code=400, detail="Provide at least one task_id.")

    entries = list_entries(limit=3000)
    allowed: set[str] = set()
    for e in entries:
        if not isinstance(e, dict):
            continue
        src = str(e.get("source") or "").strip()
        if src not in JANITOR_GRAVEYARD_SOURCES:
            continue
        tid = str(e.get("task_id") or "").strip()
        if tid:
            allowed.add(tid)
    filtered = [t for t in want if t in allowed]
    skipped = [t for t in want if t not in allowed]
    if not filtered:
        return GraveyardReopenResponse(
            ok=True,
            reopened=0,
            errors=[],
            skipped_not_in_janitor_graveyard=skipped,
            reopened_task_ids=[],
        )
    from todoist_service import reopen_tasks_for_ids

    n_ok, errs, ok_ids = reopen_tasks_for_ids(key, filtered)
    return GraveyardReopenResponse(
        ok=True,
        reopened=n_ok,
        errors=errs,
        skipped_not_in_janitor_graveyard=skipped,
        reopened_task_ids=ok_ids,
    )
