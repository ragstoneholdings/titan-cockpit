"""Mobile-first API schemas for Vanguard iOS."""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class MobileVanguardExecuted(BaseModel):
    deep: int = 0
    mixed: int = 0
    shallow: int = 0


class MobileRunway(BaseModel):
    notification_markdown: str = ""
    prep_gap_minutes: int = 0
    default_wake_iso: str = ""
    runway_conflict: bool = False
    operator_display: str = "You"
    conflict_summary: str | None = None


class MobileSovereignty(BaseModel):
    sovereignty_quotient_percent: float = 0.0
    sovereignty_quotient_blended_percent: float = 0.0
    deep_work_sessions_logged: int = 0
    execution_mix_total: int = 0
    utility_tagged_open_count: int = 0
    sovereignty_line: str = ""
    operational_authority_line: str = ""
    financial_sovereignty_line: str = ""
    physical_baseline_line: str = ""


class MobileDeadBugAlert(BaseModel):
    project_id: str = ""
    project_name: str = ""
    title_hint: str = ""


class MobileScheduleDaySignals(BaseModel):
    summary_line: str = ""
    meeting_load_warning: bool = False
    fragmented_day: bool = False


class MobileCalendarProviderSignal(BaseModel):
    connected: bool | None = None
    configured: bool | None = None
    mode: str = ""
    event_count: int = 0
    hours: float = 0.0
    error: str = ""


class MobileCalendarSignals(BaseModel):
    google: MobileCalendarProviderSignal = Field(default_factory=MobileCalendarProviderSignal)
    personal: MobileCalendarProviderSignal = Field(default_factory=MobileCalendarProviderSignal)


class MobileCockpit(BaseModel):
    date: str
    identity_purpose: str = ""
    google_calendar_connected: bool = False
    executive_score_percent: float = 0.0
    execution_day_summary: str = ""
    vanguard_executed: MobileVanguardExecuted = Field(default_factory=MobileVanguardExecuted)
    runway: MobileRunway = Field(default_factory=MobileRunway)
    sovereignty: MobileSovereignty = Field(default_factory=MobileSovereignty)
    air_gap_active: bool = False
    midday_shield_active: bool = False
    identity_alignment_window_active: bool = False
    todoist_inbox_open_count: int = 0
    inbox_slaughter_gate_ok: bool = False
    dead_bug_alerts: List[MobileDeadBugAlert] = Field(default_factory=list)
    firefighting_signals: List[str] = Field(default_factory=list)
    firewall_audit_summary: str = ""
    schedule_day_signals: MobileScheduleDaySignals = Field(default_factory=MobileScheduleDaySignals)
    integrity_sentry_state: str = "NOMINAL"
    calendar_signals: MobileCalendarSignals = Field(default_factory=MobileCalendarSignals)
    drift_signals: List[str] = Field(default_factory=list)


class MobileDashboardResponse(BaseModel):
    cockpit: MobileCockpit
    ragstone_line: str = ""
    qbo_line: str = ""


class MobilePowerTrioSlot(BaseModel):
    slot: int = 0
    label: str = ""
    task_id: str = ""
    title: str = ""
    description: str = ""
    project_name: str = ""
    priority: int = 1
    tactical_steps: List[str] = Field(default_factory=list)


class MobilePowerTrioView(BaseModel):
    slots: List[MobilePowerTrioSlot] = Field(default_factory=list)
    ranked_total: int = 0
    task_total: int = 0
    rank_warning: str = ""
    merge_note: str = ""
    last_sync_iso: str = ""
    last_rank_iso: str = ""
    recon_day: str = ""


class MobileReadinessResponse(BaseModel):
    ok: bool = True
    api_ready: bool = True
    mobile_routes_ready: bool = True
    api_key_required: bool = False
    gemini_configured: bool = False
    google_calendar_connected: bool = False
    personal_calendar_configured: bool = False
    personal_calendar_mode: str = "none"


class MobilePlanBlock(BaseModel):
    id: str
    title: str
    start_label: str = ""
    end_label: str = ""
    reason: str = ""
    status: str = "planned"


class MobileDayPlan(BaseModel):
    plan_id: str
    day: str
    summary: str = ""
    reason: str = ""
    generated_by: str = "fallback"
    blocks: List[MobilePlanBlock] = Field(default_factory=list)
    accepted: bool = False
    updated_at: str = ""


class MobilePlanGenerateBody(BaseModel):
    day: str | None = None
    objective: str = ""


class MobilePlanReplanBody(BaseModel):
    day: str | None = None
    reason: str = ""


class MobilePlanAcceptBody(BaseModel):
    day: str
    plan_id: str


class MobileExecutionEventBody(BaseModel):
    day: str
    block_id: str
    status: str = "completed"
    reason: str = ""
