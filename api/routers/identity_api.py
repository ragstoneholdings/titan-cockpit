"""Life purpose text (identity.json), shared with Streamlit Purpose Pillar."""

from __future__ import annotations

import identity_store
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/identity", tags=["identity"])


class PurposeBody(BaseModel):
    purpose: str = Field("", description="Titan / life purpose statement")


@router.get("/purpose")
def get_purpose() -> dict:
    return {"purpose": identity_store.load_identity_purpose()}


@router.put("/purpose")
def put_purpose(body: PurposeBody) -> dict:
    identity_store.save_identity_purpose(body.purpose)
    return {"purpose": identity_store.load_identity_purpose()}
