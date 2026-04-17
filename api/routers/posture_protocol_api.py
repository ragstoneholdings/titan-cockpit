"""GET/PUT posture protocol checkboxes (posture_protocol_state.json, Streamlit-compatible)."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.services.posture_protocol_read import (
    PROTOCOL_ITEM_IDS,
    load_protocol_history_bundle,
    merge_protocol_day_update,
)

router = APIRouter(prefix="/posture-protocol", tags=["posture-protocol"])


class PostureItemsBody(BaseModel):
    chin_tucks: Optional[bool] = Field(None)
    wall_slides: Optional[bool] = Field(None)
    diaphragmatic_breathing: Optional[bool] = Field(None)


def _items_for_day(d: date) -> dict[str, bool]:
    hist = load_protocol_history_bundle()
    snap = hist.get(d.isoformat(), {})
    return {pid: bool(snap.get(pid, False)) for pid in PROTOCOL_ITEM_IDS}


@router.get("")
def get_posture_protocol(day: Optional[date] = Query(None, description="Calendar day (defaults to today)")) -> dict[str, Any]:
    d = day or date.today()
    return {"date": d.isoformat(), "items": _items_for_day(d)}


@router.put("")
def put_posture_protocol(
    body: PostureItemsBody,
    day: Optional[date] = Query(None, description="Calendar day (defaults to today)"),
) -> dict[str, Any]:
    d = day or date.today()
    partial = body.model_dump(exclude_unset=True)
    if not partial:
        raise HTTPException(status_code=400, detail="Provide at least one checkbox field to update.")
    out = merge_protocol_day_update(d, partial)
    return {"date": d.isoformat(), "items": out}
