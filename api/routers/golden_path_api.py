"""Golden path proposal actions (approve / dismiss / snooze) — never auto-applies without user action."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.services.golden_path_proposal_store import clear_snooze, set_action

router = APIRouter(prefix="/golden-path", tags=["golden-path"])


class ProposalActionBody(BaseModel):
    proposal_id: str = Field(..., min_length=1)
    action: Literal["approve", "dismiss", "snooze"]


@router.post("/proposal-action")
def golden_path_proposal_action(
    day: date = Query(..., description="Calendar day"),
    body: ProposalActionBody = ...,
) -> dict:
    try:
        bucket = set_action(day, body.proposal_id, body.action)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"date": day.isoformat(), "bucket": bucket}


@router.post("/clear-snooze")
def golden_path_clear_snooze(day: date = Query(..., description="Calendar day")) -> dict:
    clear_snooze(day)
    return {"date": day.isoformat(), "ok": True}
