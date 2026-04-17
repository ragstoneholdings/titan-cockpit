"""Todoist / Power Trio API models."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class TodoistStatusResponse(BaseModel):
    todoist_configured: bool
    gemini_configured: bool
    state_path: str = Field(description="Disk file backing Power Trio for the API")


class PowerTrioSlot(BaseModel):
    slot: int
    label: str
    task_id: str
    title: str
    description: str = ""
    project_name: str = ""
    priority: int = 1
    tactical_steps: List[str] = Field(
        default_factory=list,
        description="Three verb-first micro-actions (Gemini); may be empty strings if unconfigured.",
    )


class PowerTrioView(BaseModel):
    slots: List[PowerTrioSlot] = Field(default_factory=list)
    ranked_total: int = 0
    task_total: int = 0
    rank_warning: str = ""
    merge_note: str = ""
    last_sync_iso: str = ""
    last_rank_iso: str = ""
    recon_day: str = Field(default="", description="ISO date this trio snapshot applies to")


class SyncResponse(BaseModel):
    ok: bool = True
    task_count: int
    merge_note: str = ""


class RankResponse(BaseModel):
    ok: bool = True
    rank_warning: str = ""
    trio: PowerTrioView


class CompleteBody(BaseModel):
    task_id: str
    day: Optional[str] = Field(None, description="Recon date YYYY-MM-DD (defaults to today)")


class CompleteResponse(BaseModel):
    ok: bool = True
    trio: PowerTrioView


class GeminiAssistBody(BaseModel):
    task_id: str
    mode: str = Field(description="'plan' (3 steps) or 'strike' (quick execution)")


class GeminiAssistResponse(BaseModel):
    text: str


class GraveyardReopenBody(BaseModel):
    """Reopen completed Todoist tasks that appear in the janitor graveyard (by original task id)."""

    task_ids: List[str] = Field(
        default_factory=list,
        description="Todoist task ids to reopen; max 50 per request.",
    )

    @field_validator("task_ids", mode="before")
    @classmethod
    def _cap_task_ids(cls, v: object) -> List[str]:
        if not isinstance(v, list):
            return []
        out = [str(x).strip() for x in v if str(x).strip()]
        return list(dict.fromkeys(out))[:50]


class GraveyardReopenResponse(BaseModel):
    ok: bool = True
    reopened: int = 0
    errors: List[str] = Field(default_factory=list)
    skipped_not_in_janitor_graveyard: List[str] = Field(
        default_factory=list,
        description="Ids that were not in graveyard with source janitor / janitor_auto.",
    )
    reopened_task_ids: List[str] = Field(default_factory=list)
