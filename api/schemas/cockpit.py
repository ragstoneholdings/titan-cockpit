"""JSON models for the cockpit API."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class KillZone(BaseModel):
    start_iso: str
    end_iso: str


class ScheduleOverlapItem(BaseModel):
    start_iso: str
    end_iso: str
    title_a: str
    title_b: str
    source_a: str
    source_b: str
    id: Optional[str] = None
    start_a_iso: Optional[str] = None
    end_a_iso: Optional[str] = None
    start_b_iso: Optional[str] = None
    end_b_iso: Optional[str] = None


class ScheduleSourceFlag(BaseModel):
    message: str
    start_iso: str
    work_title: str
    personal_title: str
    api_source: str


class SuggestionOption(BaseModel):
    value: str
    label: str


class SuggestionItem(BaseModel):
    id: str
    prompt: str
    options: List[SuggestionOption] = Field(default_factory=list)


class ScheduleDaySignals(BaseModel):
    """Aligned with docs/SCHEDULE_INTAKE_RYAN.md (A1 / A5 / A2 + meeting load + work vs API flags)."""

    overlap_count: int = 0
    overlaps: List[ScheduleOverlapItem] = Field(default_factory=list)
    source_flags: List[ScheduleSourceFlag] = Field(default_factory=list)
    meeting_load_minutes: int = 0
    meeting_load_hours_display: str = "0h"
    meeting_load_warning: bool = False
    meeting_load_warn_threshold_minutes: int = 300
    max_free_gap_minutes: int = 0
    deep_slot_60_available: bool = True
    fragmented_day: bool = False
    small_gap_count: int = 0
    immovable_title_hits: int = 0
    suggestion_questions: List[str] = Field(default_factory=list)
    suggestion_items: List[SuggestionItem] = Field(default_factory=list)
    summary_line: str = ""


class TimedEventItem(BaseModel):
    start_iso: str
    title: str
    source: str  # "google" | "personal" (unchanged for overrides / logic)
    source_kind: Literal["personal_google", "personal_ics", "work_screenshot"] = Field(
        description="personal_* = API feeds; work_screenshot = last Gemini screenshot advisory for this day."
    )
    column_date_iso: Optional[str] = Field(
        default=None,
        description="Printed calendar date for this row's day column (work screenshot / week view).",
    )
    column_weekday: Optional[str] = Field(
        default=None,
        description="English weekday of that column, e.g. Sunday (optional; work screenshot).",
    )


class TacticalBriefLines(BaseModel):
    """Work-calendar Gemini output: three one-line fields (Rugged Executive tone)."""

    fragmentation: str = ""
    kill_zone: str = ""
    priority: str = ""


class TacticalBriefPeriods(BaseModel):
    """Tactical brief split by time-of-day band (screenshot analyze)."""

    morning: TacticalBriefLines = Field(default_factory=TacticalBriefLines)
    afternoon: TacticalBriefLines = Field(default_factory=TacticalBriefLines)
    evening: TacticalBriefLines = Field(default_factory=TacticalBriefLines)


class TomorrowRunwayPreview(BaseModel):
    """Next calendar day runway slice when viewing today's cockpit."""

    date: str = ""
    integrity_wake_iso: Optional[str] = None
    tactical_integrity_wake_iso: Optional[str] = None
    default_wake_iso: str = ""
    runway_conflict: bool = False
    anchor_title: Optional[str] = None
    anchor_start_iso: Optional[str] = None
    anchor_source: Optional[str] = None
    synthetic_default_anchor: bool = False
    prep_shortfall_labels: List[str] = Field(default_factory=list)
    conflict_summary: Optional[str] = None


class GoldenPathTimelineRow(BaseModel):
    start_iso: str
    end_iso: str = ""
    title: str
    source: str = ""
    source_kind: str = ""
    badges: List[str] = Field(default_factory=list)
    expand_hint: str = ""


class GoldenPathProposal(BaseModel):
    id: str
    headline: str
    detail: str
    deltas: Dict[str, Any] = Field(default_factory=dict)
    status: Literal["pending", "approved"] = "pending"


class IntegrityHabitSnapshot(BaseModel):
    posture_sessions_7d: List[bool] = Field(default_factory=list)
    notes: str = ""


class SidebarIntegrity28d(BaseModel):
    """Rolling 28 calendar days ending on recon `date` (posture from protocol history; neck from integrity_stats)."""

    labels: List[str] = Field(default_factory=list, description="Short day labels, oldest → newest.")
    posture_days: List[bool] = Field(default_factory=list)
    neck_days: List[bool] = Field(default_factory=list)


class GraveyardPreviewEntry(BaseModel):
    task_id: str = ""
    title: str = ""
    closed_at: str = ""
    source: str = ""


class WorkCalendarAdvisoryPanel(BaseModel):
    """Last saved work-calendar screenshot analysis for this recon day (if any)."""

    time_coaching: str = ""
    notes: str = ""
    visibility: str = ""
    saved_at: Optional[str] = None
    tactical_brief: Optional[TacticalBriefPeriods] = None


class MorningBriefPayload(BaseModel):
    """EA-style morning optimization scan (deterministic v1)."""

    visible: bool = False
    dismissed: bool = False
    briefing_window_active: bool = False
    anchors_summary: str = ""
    kill_zones_top3: List[KillZone] = Field(default_factory=list)
    trio_slot1_title: str = ""
    matched_zone_index: Optional[int] = None
    brief_markdown: str = ""
    generated_at: str = ""


class SovereigntyPayload(BaseModel):
    """Vanguard Sovereignty Engine headline KPIs."""

    sovereignty_quotient_percent: float = 0.0
    sovereignty_quotient_blended_percent: float = 0.0
    deep_work_sessions_logged: int = 0
    execution_mix_total: int = 0
    utility_tagged_open_count: int = 0
    sovereignty_line: str = ""
    operational_authority_line: str = ""
    financial_sovereignty_line: str = ""
    physical_baseline_line: str = ""


class DeadBugAlert(BaseModel):
    project_id: str = ""
    project_name: str = ""
    hours_since_activity: float = 0.0
    task_id: str = ""
    title_hint: str = ""


class RunwayPayload(BaseModel):
    integrity_wake_iso: Optional[str] = None
    tactical_integrity_wake_iso: Optional[str] = None
    default_wake_iso: str
    runway_conflict: bool
    anchor_title: Optional[str] = None
    anchor_start_iso: Optional[str] = None
    anchor_source: Optional[str] = None
    synthetic_default_anchor: bool = False
    notification_markdown: str
    prep_posture_minutes: int = 0
    prep_neck_minutes: int = 0
    prep_ops_minutes: int = 0
    prep_total_minutes: int = 0
    prep_expected_total_minutes: int = 120
    prep_gap_minutes: int = 0
    prep_expected_posture_minutes: int = 30
    prep_expected_neck_minutes: int = 60
    prep_expected_ops_minutes: int = 30
    prep_shortfall_labels: List[str] = Field(default_factory=list)
    operator_display: str = "You"
    conflict_summary: Optional[str] = None
    tomorrow_preview: Optional[TomorrowRunwayPreview] = Field(
        default=None,
        description="Populated when recon day is today: next-day prep/anchor snapshot.",
    )


class CockpitResponse(BaseModel):
    date: str
    google_calendar_connected: bool = False
    executive_score_percent: float = Field(description="Focus-style score from trio execution counts")
    vanguard_executed: dict = Field(default_factory=dict)
    runway: RunwayPayload
    kill_zones: List[KillZone] = Field(default_factory=list)
    schedule_day_signals: ScheduleDaySignals = Field(default_factory=ScheduleDaySignals)
    daily_landscape: List[TimedEventItem] = Field(default_factory=list)
    personal_calendar_note: str = ""
    personal_calendar_status: Literal["ok", "not_configured", "error"] = "ok"
    identity_alert: bool = False
    integrity_protocol_confirmed: bool = Field(
        default=False,
        description="Physical protocol fully confirmed for calendar *today* when recon day differs, so urgency/red shell matches the real clock; equals recon day when recon is today.",
    )
    work_calendar_advisory: Optional[WorkCalendarAdvisoryPanel] = None
    work_calendar_week_gap_hint: str = Field(
        default="",
        description="Non-empty when a week-style work snapshot exists but no rows match this recon day (usually wrong column_date_iso).",
    )
    execution_day_summary: str = Field(
        default="",
        description="Plain-language merged day summary (landscape + runway + work advisory + schedule read).",
    )
    golden_path_resolution_summary: str = Field(
        default="",
        description="One line built from saved schedule tradeoff MCQs.",
    )
    schedule_tradeoff_answers: Dict[str, str] = Field(default_factory=dict)
    golden_path_proposals: List[GoldenPathProposal] = Field(default_factory=list)
    golden_path_timeline: List[GoldenPathTimelineRow] = Field(default_factory=list)
    golden_path_snoozed: bool = False
    integrity_habit_snapshot: Optional[IntegrityHabitSnapshot] = None
    identity_purpose: str = Field(
        default="",
        description="Life purpose text (identity) for Golden path context; same source as Purpose Pillar.",
    )
    sidebar_integrity: SidebarIntegrity28d = Field(default_factory=SidebarIntegrity28d)
    graveyard_preview: List[GraveyardPreviewEntry] = Field(default_factory=list)
    morning_brief: Optional[MorningBriefPayload] = None
    integrity_consistency_percent: float = Field(
        default=100.0,
        description="Trailing 7d posture/neck + today's protocol blend (discipline visibility).",
    )
    integrity_sentry_state: Literal["NOMINAL", "WARNING", "CRITICAL"] = "NOMINAL"
    ops_posture_nudge_visible: bool = False
    ops_posture_nudge_message: str = ""
    focus_shell_window_active: bool = False
    sacred_integrity_debt_count: int = 0
    cockpit_operator_name: str = Field(
        default="",
        description="COCKPIT_OPERATOR_NAME when set, else runway operator_display.",
    )
    sovereignty: SovereigntyPayload = Field(default_factory=SovereigntyPayload)
    air_gap_active: bool = False
    midday_shield_active: bool = False
    identity_alignment_window_active: bool = False
    air_gap_extension_suggested: bool = Field(
        default=False,
        description="True when prior night sleep below target — advisory longer morning protection.",
    )
    todoist_inbox_open_count: int = 0
    inbox_slaughter_gate_ok: bool = False
    dead_bug_alerts: List[DeadBugAlert] = Field(default_factory=list)
    firefighting_signals: List[str] = Field(default_factory=list)
    firewall_audit_summary: str = ""
    favor_strike_days_clean_7d: int = 0
    favor_strike_streak_7d: int = 0
    commitments_partner_overdue: bool = False
    ragstone_ledger: Dict[str, Any] = Field(default_factory=dict)
    zero_utility_labor_today: bool = False
    evening_wins_count: int = 0
    evening_leaks_count: int = 0
