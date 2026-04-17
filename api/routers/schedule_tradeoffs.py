"""Persisted MCQ answers for schedule intake (per day)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Body, HTTPException, Query

from api.services.schedule_tradeoff_store import get_answers_for_day, put_answers_for_day

router = APIRouter(prefix="/schedule-tradeoffs", tags=["schedule-tradeoffs"])


@router.get("")
def get_schedule_tradeoffs(day: date = Query(..., description="Calendar day")) -> dict:
    return {"date": day.isoformat(), "answers": get_answers_for_day(day)}


@router.put("")
def put_schedule_tradeoffs(
    day: date = Query(..., description="Calendar day"),
    body: dict = Body(...),
) -> dict:
    try:
        merged = put_answers_for_day(day, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"date": day.isoformat(), "answers": merged}
