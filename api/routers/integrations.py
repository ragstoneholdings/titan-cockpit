"""Inbound webhooks (Zapier, etc.)."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import zapier_idempotency_store
import zapier_trace_store
from api.services import power_trio_state as pts
from fastapi import APIRouter, Body, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from todoist_service import add_task_v1, fetch_todoist_projects

router = APIRouter(prefix="/integrations", tags=["integrations"])
_log = logging.getLogger("api.integrations")

_zapier_window_sec = 60.0
_zapier_max_per_window = 120
_zapier_hits: Dict[str, List[float]] = {}


def _client_ip(request: Request) -> str:
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _zapier_rate_ok(ip: str) -> bool:
    now = time.time()
    q = _zapier_hits.setdefault(ip, [])
    q[:] = [t for t in q if now - t < _zapier_window_sec]
    if len(q) >= _zapier_max_per_window:
        return False
    q.append(now)
    return True


class ZapierInboundPayload(BaseModel):
    """MindManager → Zapier → Titan: optional structured fields; unknown keys allowed for Zapier passthrough."""

    model_config = ConfigDict(extra="allow")

    source: Optional[str] = Field(None, description="e.g. mindmanager")
    mind_map_node_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None
    priority: Optional[int] = Field(None, ge=1, le=4, description="Todoist 1–4 (4 = urgent)")
    labels: List[str] = Field(default_factory=list)
    project_name: Optional[str] = None
    create_todoist_task: bool = False


def _resolve_project_id(api_key: str, project_name: Optional[str]) -> Optional[str]:
    if not project_name or not str(project_name).strip():
        return None
    want = str(project_name).strip().lower()
    pmap = fetch_todoist_projects(api_key)
    for pid, nm in pmap.items():
        if str(nm).strip().lower() == want:
            return pid
    return None


def _err(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(
        {"ok": False, "error": {"code": code, "message": message}},
        status_code=status,
    )


@router.post("/zapier/inbound")
def post_zapier_inbound(request: Request, payload: Dict[str, Any] = Body(default_factory=dict)) -> Any:
    ip = _client_ip(request)
    if not _zapier_rate_ok(ip):
        return _err("rate_limited", "Too many requests; slow down or narrow Zapier fan-out", status=429)

    idem = (request.headers.get("x-idempotency-key") or request.headers.get("idempotency-key") or "").strip()
    if idem and not zapier_idempotency_store.remember_if_new(idem):
        return {"ok": True, "idempotent": True, "deduped": True}

    raw = payload if isinstance(payload, dict) else {"raw": payload}
    parsed: Optional[ZapierInboundPayload] = None
    validation_note = ""
    try:
        parsed = ZapierInboundPayload.model_validate(raw)
    except Exception as e:
        validation_note = str(e)[:200]

    zapier_trace_store.append_event(raw)
    out: Dict[str, Any] = {"ok": True, "stored": True}
    if parsed is not None:
        out["validated"] = True
    elif validation_note:
        out["validation_warning"] = validation_note
        out["validation_error"] = {"code": "payload_validation", "message": validation_note}

    if parsed and parsed.create_todoist_task:
        title = (parsed.title or "").strip()
        if not title:
            out["todoist_skipped"] = "missing_title"
            return out
        key = pts.todoist_api_key()
        if not key:
            out["todoist_skipped"] = "todoist_not_configured"
            return out
        desc_parts = [x for x in (parsed.description, parsed.notes) if x and str(x).strip()]
        description = "\n\n".join(str(x).strip() for x in desc_parts if x)
        if parsed.mind_map_node_id:
            description = (description + "\n\n" if description else "") + f"MindManager node: {parsed.mind_map_node_id}"
        pid = _resolve_project_id(key, parsed.project_name)
        try:
            task = add_task_v1(
                key,
                content=title,
                description=description.strip(),
                priority=parsed.priority or 1,
                labels=parsed.labels or [],
                project_id=pid,
            )
            tid = str(task.get("id") or "").strip()
            out["todoist_task"] = {"id": tid or None, "content": task.get("content")}
        except Exception as e:
            err = str(e)[:500]
            out["todoist_error"] = err
            out["error"] = {"code": "todoist_delegate", "message": err}
            _log.warning("zapier_inbound todoist delegate failed: %s", err)
    return out
