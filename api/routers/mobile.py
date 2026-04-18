"""Mobile-first API surface for Vanguard iOS."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.schemas.mobile import (
    MobileDashboardResponse,
    MobileDayPlan,
    MobileExecutionEventBody,
    MobilePlanAcceptBody,
    MobilePlanGenerateBody,
    MobilePlanReplanBody,
    MobilePowerTrioView,
    MobileReadinessResponse,
)
from api.services import mobile_calendar_agent, mobile_snapshot, mobile_store, vanguard_llm
from api.services.gemini_runtime import configure_genai_from_env
from integrations.env_loader import env_str
from integrations.google_calendar import calendar_service_from_token
from integrations.personal_calendar import personal_calendar_source_status_from_env

router = APIRouter(prefix="/mobile", tags=["mobile"])


@router.get("/dashboard", response_model=MobileDashboardResponse)
def get_mobile_dashboard(day: Optional[date] = Query(None, description="Recon date (defaults to today)")) -> MobileDashboardResponse:
    return MobileDashboardResponse(**mobile_snapshot.build_mobile_dashboard(day))


@router.get("/readiness", response_model=MobileReadinessResponse)
def get_mobile_readiness() -> MobileReadinessResponse:
    genai, _ = configure_genai_from_env()
    p = personal_calendar_source_status_from_env()
    key_required = bool(env_str("COCKPIT_API_KEY", "").strip())
    return MobileReadinessResponse(
        ok=True,
        api_ready=True,
        mobile_routes_ready=True,
        api_key_required=key_required,
        gemini_configured=genai is not None,
        google_calendar_connected=calendar_service_from_token() is not None,
        personal_calendar_configured=bool(p.get("configured")),
        personal_calendar_mode=str(p.get("mode") or "none"),
    )


@router.get("/power-trio", response_model=MobilePowerTrioView)
def get_mobile_power_trio(day: Optional[date] = Query(None, description="Recon date (defaults to today)")) -> MobilePowerTrioView:
    return MobilePowerTrioView(**mobile_snapshot.build_mobile_power_trio(day))


class OpportunityCostBody(BaseModel):
    title: str = Field(..., min_length=1)
    notes: str = ""
    estimated_minutes: Optional[int] = None


@router.post("/opportunity-cost")
def post_mobile_opportunity_cost(body: OpportunityCostBody) -> dict:
    return vanguard_llm.opportunity_cost_narrative(
        title=body.title,
        notes=body.notes,
        estimated_minutes=body.estimated_minutes,
    )


class WindshieldTriageBody(BaseModel):
    text: str = Field(..., min_length=1)
    mode: str = "windshield"


@router.post("/windshield-triage")
def post_mobile_windshield_triage(body: WindshieldTriageBody) -> dict:
    mode = "utility_alarm" if body.mode.strip().lower() == "utility_alarm" else "windshield"
    return vanguard_llm.windshield_triage(text=body.text, mode=mode)


def _parse_day(day_raw: str | None) -> date:
    if not day_raw or not str(day_raw).strip():
        return date.today()
    try:
        return date.fromisoformat(str(day_raw).strip()[:10])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid day: {day_raw}") from e


@router.post("/day-plan/generate", response_model=MobileDayPlan)
def post_mobile_day_plan_generate(body: MobilePlanGenerateBody) -> MobileDayPlan:
    d = _parse_day(body.day)
    ctx = mobile_store.store.load_dashboard_snapshot(d)
    plan = mobile_calendar_agent.generate_day_plan(day=d, context=ctx, objective=body.objective)
    saved = mobile_store.store.save_day_plan(d, plan, source=str(plan.get("generated_by") or "fallback"))
    return MobileDayPlan(**saved)


@router.post("/day-plan/replan", response_model=MobileDayPlan)
def post_mobile_day_plan_replan(body: MobilePlanReplanBody) -> MobileDayPlan:
    d = _parse_day(body.day)
    ctx = mobile_store.store.load_dashboard_snapshot(d)
    drift = mobile_snapshot.get_drift_signals(d)
    plan = mobile_calendar_agent.replan_with_drift(day=d, context=ctx, drift_signals=drift, reason=body.reason)
    saved = mobile_store.store.save_day_plan(d, plan, source="replan")
    return MobileDayPlan(**saved)


@router.post("/day-plan/accept")
def post_mobile_day_plan_accept(body: MobilePlanAcceptBody) -> dict:
    d = _parse_day(body.day)
    return mobile_store.store.accept_day_plan(d, body.plan_id)


@router.get("/day-plan", response_model=MobileDayPlan)
def get_mobile_day_plan(day: Optional[date] = Query(None, description="Recon date (defaults to today)")) -> MobileDayPlan:
    d = day or date.today()
    plan = mobile_store.store.load_day_plan(d)
    if not plan:
        raise HTTPException(status_code=404, detail="No day plan for this date.")
    return MobileDayPlan(**plan)


@router.post("/day-plan/event")
def post_mobile_day_plan_event(body: MobileExecutionEventBody) -> dict:
    d = _parse_day(body.day)
    return mobile_store.store.record_execution_event(
        d,
        block_id=body.block_id,
        status=body.status,
        reason=body.reason,
    )


@router.get("/assistant-metrics")
def get_mobile_assistant_metrics(trailing_days: int = Query(14, ge=1, le=90)) -> dict:
    return mobile_store.store.assistant_metrics(trailing_days=trailing_days)
