"""Runway hard-anchor overrides (wraps runway_store)."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from runway_store import (
    RunwayDayOverride,
    clear_runway_override_for_day,
    load_runway_override_for_day,
    save_runway_override_for_day,
)

router = APIRouter(prefix="/runway", tags=["runway"])


class RunwayOverridePayload(BaseModel):
    start_iso: str = Field(..., description="Anchor start as ISO datetime string")
    title: str
    source: Literal["google", "personal"]


class RunwayDayResponse(BaseModel):
    date: str
    override: Optional[dict] = None


@router.get("/{day}", response_model=RunwayDayResponse)
def get_runway_day(day: date) -> RunwayDayResponse:
    o = load_runway_override_for_day(day)
    if not o:
        return RunwayDayResponse(date=day.isoformat(), override=None)
    return RunwayDayResponse(
        date=day.isoformat(),
        override={"start_iso": o.start_iso, "title": o.title, "source": o.source},
    )


@router.put("/{day}")
def put_runway_day(day: date, body: RunwayOverridePayload) -> RunwayDayResponse:
    if not body.start_iso.strip() or not body.title.strip():
        raise HTTPException(status_code=400, detail="start_iso and title required")
    save_runway_override_for_day(
        day,
        RunwayDayOverride(start_iso=body.start_iso.strip(), title=body.title.strip(), source=body.source),
    )
    return get_runway_day(day)


@router.delete("/{day}")
def delete_runway_day(day: date) -> dict:
    clear_runway_override_for_day(day)
    return {"ok": True, "date": day.isoformat()}
