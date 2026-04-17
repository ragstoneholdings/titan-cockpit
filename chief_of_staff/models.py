from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class IdentityProtocols(BaseModel):
    """Neck / Posture / Morning Ops durations before the first hard commitment."""

    posture: timedelta = Field(ge=timedelta(0))
    neck: timedelta = Field(ge=timedelta(0))
    morning_ops: timedelta = Field(ge=timedelta(0))

    def total_prep(self) -> timedelta:
        return self.posture + self.neck + self.morning_ops


class HardAnchor(BaseModel):
    """Timed calendar anchor; optional Google event id for revision hashing."""

    start: datetime
    title: str
    source: Literal["google", "personal"]
    calendar_event_id: Optional[str] = None


class ChiefOfStaffConfig(BaseModel):
    hard_title_markers: list[str] = Field(default_factory=list)
    prefer_google_first: bool = True

    @field_validator("hard_title_markers", mode="before")
    @classmethod
    def _strip_markers(cls, v: object) -> object:
        if not isinstance(v, list):
            return v
        return [str(x).strip() for x in v if str(x).strip()]


class DayReadiness(BaseModel):
    anchor: Optional[HardAnchor]
    protocols: IdentityProtocols
    integrity_wake: Optional[datetime]
    default_wake: datetime
    last_bedtime: Optional[datetime]
    recovery_target: timedelta
    runway_conflict: bool
    tactical_protocols: IdentityProtocols
    tactical_integrity_wake: Optional[datetime]
    notification_markdown: str
    operator_display: str = "You"
    conflict_summary: Optional[str] = None
