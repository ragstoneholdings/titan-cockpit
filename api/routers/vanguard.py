"""Vanguard Cockpit: LLM tools, health/day ledger, bug backlog, firewall audit."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

import bug_backlog_store
import commitments_store
import ragstone_ledger_store
import vanguard_health_store
from api.services import firefighting_audit, vanguard_llm
from fastapi import APIRouter, Body, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/vanguard", tags=["vanguard"])


class OpportunityCostBody(BaseModel):
    title: str = Field(..., min_length=1)
    notes: str = ""
    estimated_minutes: Optional[int] = None


@router.post("/opportunity-cost")
def post_opportunity_cost(body: OpportunityCostBody) -> dict:
    return vanguard_llm.opportunity_cost_narrative(
        title=body.title,
        notes=body.notes,
        estimated_minutes=body.estimated_minutes,
    )


class TriageBody(BaseModel):
    text: str = Field(..., min_length=1)
    mode: str = "windshield"
    append_bug_backlog: bool = False


@router.post("/windshield-triage")
def post_windshield_triage(body: TriageBody) -> dict:
    mode = "utility_alarm" if body.mode.strip().lower() == "utility_alarm" else "windshield"
    out = vanguard_llm.windshield_triage(text=body.text, mode=mode)
    if out.get("ok") and body.append_bug_backlog:
        v = str(out.get("verdict") or "")
        if v == "bug" or (mode == "utility_alarm" and v in ("bug", "soft")):
            bug_backlog_store.append_bug(body.text[:2000], str(out.get("one_line_reason") or ""))
    return out


class PastInPastBody(BaseModel):
    text: str = Field(..., min_length=1)


@router.post("/past-in-past")
def post_past_in_past(body: PastInPastBody) -> dict:
    return vanguard_llm.past_in_the_past(text=body.text)


class CalendarLeanBody(BaseModel):
    rows: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/calendar-leanness")
def post_calendar_leanness(body: CalendarLeanBody) -> dict:
    return vanguard_llm.calendar_leanness(rows=body.rows)


class FirewallAuditBody(BaseModel):
    signals: List[str] = Field(default_factory=list)


@router.post("/firewall-audit-summary")
def post_firewall_audit(body: FirewallAuditBody) -> dict:
    sigs = [str(s).strip() for s in body.signals if str(s).strip()]
    if not sigs:
        return {"ok": True, "summary": ""}
    summary = firefighting_audit.gemini_firewall_audit_summary(sigs)
    return {"ok": bool(summary), "summary": summary}


@router.get("/health")
def get_vanguard_health() -> dict:
    return vanguard_health_store.load_bundle()


class HealthPutBody(BaseModel):
    targets: Optional[Dict[str, Any]] = None
    current: Optional[Dict[str, Any]] = None
    executive_time_value_usd_per_hour: Optional[float] = None


@router.put("/health")
def put_vanguard_health(body: HealthPutBody) -> dict:
    b = vanguard_health_store.load_bundle()
    if body.targets is not None and isinstance(body.targets, dict):
        b.setdefault("targets", {}).update(body.targets)
    if body.current is not None and isinstance(body.current, dict):
        b.setdefault("current", {}).update(body.current)
    if body.executive_time_value_usd_per_hour is not None:
        b["executive_time_value_usd_per_hour"] = body.executive_time_value_usd_per_hour
    vanguard_health_store.save_bundle(b)
    return b


class DayPatchBody(BaseModel):
    inbox_cleared: Optional[bool] = None
    sleep_hours: Optional[float] = None
    zero_utility_labor: Optional[bool] = None
    evening_wins: Optional[List[str]] = None
    evening_leaks: Optional[List[str]] = None


@router.put("/day")
def put_vanguard_day(
    day: Optional[date] = Query(None, description="Defaults to today"),
    body: DayPatchBody = Body(default=DayPatchBody()),
) -> dict:
    d = day or date.today()
    patch: Dict[str, Any] = {}
    if body.inbox_cleared is not None:
        patch["inbox_cleared"] = bool(body.inbox_cleared)
    if body.sleep_hours is not None:
        patch["sleep_hours"] = float(body.sleep_hours)
    if body.zero_utility_labor is not None:
        patch["zero_utility_labor"] = bool(body.zero_utility_labor)
    if body.evening_wins is not None:
        patch["evening_wins"] = [str(x) for x in body.evening_wins[:20]]
    if body.evening_leaks is not None:
        patch["evening_leaks"] = [str(x) for x in body.evening_leaks[:20]]
    row = vanguard_health_store.put_day_merge(d, patch)
    return {"day": d.isoformat(), "row": row}


@router.get("/day")
def get_vanguard_day(day: Optional[date] = Query(None)) -> dict:
    d = day or date.today()
    return {"day": d.isoformat(), "row": vanguard_health_store.get_day(d)}


@router.get("/bug-backlog")
def get_bug_backlog() -> dict:
    return {"items": bug_backlog_store.items_list()}


@router.post("/bug-backlog/clear")
def clear_bug_backlog() -> dict:
    bug_backlog_store.clear_items()
    return {"ok": True}


@router.get("/commitments")
def get_commitments() -> dict:
    return commitments_store.load_bundle()


class CommitmentsPutBody(BaseModel):
    partners: List[Dict[str, Any]] = Field(default_factory=list)


@router.put("/commitments")
def put_commitments(body: CommitmentsPutBody) -> dict:
    commitments_store.save_bundle({"version": 1, "partners": body.partners})
    return commitments_store.load_bundle()


@router.get("/ragstone-ledger")
def get_ragstone_ledger() -> dict:
    b = dict(ragstone_ledger_store.load_bundle())
    b.update(ragstone_ledger_store.computed_kpis())
    return b


class RagstoneLedgerPutBody(BaseModel):
    revenue_ytd_usd: Optional[float] = None
    revenue_prior_ytd_usd: Optional[float] = None
    cash_balance_usd: Optional[float] = None
    monthly_burn_usd: Optional[float] = None
    fte_count: Optional[float] = None
    s_corp_election_note: Optional[str] = None
    tax_posture_note: Optional[str] = None


@router.put("/ragstone-ledger")
def put_ragstone_ledger(body: RagstoneLedgerPutBody) -> dict:
    b = ragstone_ledger_store.load_bundle()
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            b[k] = v
    ragstone_ledger_store.save_bundle(b)
    out = dict(ragstone_ledger_store.load_bundle())
    out.update(ragstone_ledger_store.computed_kpis())
    return out


