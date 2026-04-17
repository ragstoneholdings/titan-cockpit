from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from api.schemas.cockpit import CockpitResponse
from api.services import morning_brief_store
from api.services.cockpit_assemble import assemble_cockpit_response

router = APIRouter(prefix="/cockpit", tags=["cockpit"])


@router.get("", response_model=CockpitResponse)
def get_cockpit(
    day: Optional[date] = Query(None, description="Recon date (defaults to today)"),
    calendar_id: str = Query("primary"),
    vanguard_deep: int = Query(0, ge=0),
    vanguard_mixed: int = Query(0, ge=0),
    vanguard_shallow: int = Query(0, ge=0),
) -> CockpitResponse:
    return assemble_cockpit_response(
        day,
        calendar_id=calendar_id,
        vanguard_deep=vanguard_deep,
        vanguard_mixed=vanguard_mixed,
        vanguard_shallow=vanguard_shallow,
    )


@router.post("/morning-brief/dismiss")
def dismiss_morning_brief(day: Optional[date] = Query(None, description="Recon date (defaults to today)")) -> dict:
    d = day or date.today()
    morning_brief_store.dismiss_morning_brief(d)
    return {"ok": True, "day": d.isoformat()}
