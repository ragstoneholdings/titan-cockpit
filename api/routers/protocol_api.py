"""Cockpit protocol overrides (CHIEF_*), merged with env in cockpit snapshot."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.services.cockpit_protocol_file import (
    load_protocol_bundle,
    protocol_settings_response,
    save_protocol_bundle,
)

router = APIRouter(prefix="/protocol", tags=["protocol"])


class ProtocolPut(BaseModel):
    chief_hard_markers: Optional[str] = Field(None, description="Comma markers; null or empty clears file override")
    chief_posture_minutes: Optional[int] = None
    chief_neck_minutes: Optional[int] = None
    chief_ops_minutes: Optional[int] = None


@router.get("")
def get_protocol() -> dict[str, Any]:
    return protocol_settings_response()


@router.put("")
def put_protocol(body: ProtocolPut) -> dict[str, Any]:
    cur = load_protocol_bundle()
    patch = body.model_dump(exclude_unset=True)
    for k, v in patch.items():
        if k == "version":
            continue
        if k == "chief_hard_markers" and v == "":
            cur["chief_hard_markers"] = None
        else:
            cur[k] = v
    save_protocol_bundle(cur)
    return protocol_settings_response()
