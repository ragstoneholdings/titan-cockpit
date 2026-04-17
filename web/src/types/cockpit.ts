export type TacticalBriefLines = {
  fragmentation?: string;
  kill_zone?: string;
  priority?: string;
};

export type TacticalBriefPeriods = {
  morning?: TacticalBriefLines;
  afternoon?: TacticalBriefLines;
  evening?: TacticalBriefLines;
};

export type TomorrowRunwayPreview = {
  date: string;
  integrity_wake_iso?: string | null;
  tactical_integrity_wake_iso?: string | null;
  default_wake_iso?: string;
  runway_conflict?: boolean;
  anchor_title?: string | null;
  anchor_start_iso?: string | null;
  anchor_source?: string | null;
  synthetic_default_anchor?: boolean;
  prep_shortfall_labels?: string[];
  conflict_summary?: string | null;
};

export type RunwayPayload = {
  integrity_wake_iso: string | null;
  tactical_integrity_wake_iso: string | null;
  default_wake_iso: string;
  runway_conflict: boolean;
  anchor_title: string | null;
  anchor_start_iso: string | null;
  anchor_source: string | null;
  synthetic_default_anchor: boolean;
  notification_markdown: string;
  prep_posture_minutes?: number;
  prep_neck_minutes?: number;
  prep_ops_minutes?: number;
  prep_total_minutes?: number;
  prep_expected_total_minutes?: number;
  prep_gap_minutes?: number;
  prep_expected_posture_minutes?: number;
  prep_expected_neck_minutes?: number;
  prep_expected_ops_minutes?: number;
  prep_shortfall_labels?: string[];
  operator_display?: string;
  conflict_summary?: string | null;
  tomorrow_preview?: TomorrowRunwayPreview | null;
};

export type LandscapeApiRow = {
  start_iso: string;
  title: string;
  source: string;
  /** Present when API returns extended snapshot; UI falls back from `source` if missing. */
  source_kind?: "personal_google" | "personal_ics" | "work_screenshot";
  /** Printed date on the calendar column (work screenshot / week view). */
  column_date_iso?: string;
  column_weekday?: string;
};

export type ScheduleOverlapItem = {
  start_iso: string;
  end_iso: string;
  title_a: string;
  title_b: string;
  source_a: string;
  source_b: string;
  id?: string;
  start_a_iso?: string;
  end_a_iso?: string;
  start_b_iso?: string;
  end_b_iso?: string;
};

export type ScheduleSourceFlag = {
  message: string;
  start_iso: string;
  work_title: string;
  personal_title: string;
  api_source: string;
};

export type SuggestionOption = { value: string; label: string };

export type SuggestionItem = {
  id: string;
  prompt: string;
  options: SuggestionOption[];
};

/** Intake-aligned schedule pressure (see docs/SCHEDULE_INTAKE_RYAN.md). */
export type ScheduleDaySignals = {
  overlap_count: number;
  overlaps: ScheduleOverlapItem[];
  source_flags: ScheduleSourceFlag[];
  meeting_load_minutes: number;
  meeting_load_hours_display: string;
  meeting_load_warning: boolean;
  meeting_load_warn_threshold_minutes: number;
  max_free_gap_minutes: number;
  deep_slot_60_available: boolean;
  fragmented_day: boolean;
  small_gap_count: number;
  immovable_title_hits: number;
  suggestion_questions: string[];
  suggestion_items?: SuggestionItem[];
  summary_line: string;
};

export type GoldenPathProposal = {
  id: string;
  headline: string;
  detail: string;
  deltas?: Record<string, unknown>;
  status: "pending" | "approved";
};

export type GoldenPathTimelineRow = {
  start_iso: string;
  end_iso?: string;
  title: string;
  source: string;
  source_kind: string;
  badges: string[];
  expand_hint: string;
};

export type IntegrityHabitSnapshot = {
  posture_sessions_7d: boolean[];
  notes: string;
};

export type SidebarIntegrity28d = {
  labels: string[];
  posture_days: boolean[];
  neck_days: boolean[];
};

export type GraveyardPreviewEntry = {
  task_id: string;
  title: string;
  closed_at: string;
  source: string;
};

export type MorningBriefPayload = {
  visible: boolean;
  dismissed: boolean;
  briefing_window_active: boolean;
  anchors_summary: string;
  kill_zones_top3: { start_iso: string; end_iso: string }[];
  trio_slot1_title: string;
  matched_zone_index: number | null;
  brief_markdown: string;
  generated_at: string;
};

export type SovereigntyPayload = {
  sovereignty_quotient_percent?: number;
  sovereignty_quotient_blended_percent?: number;
  deep_work_sessions_logged?: number;
  execution_mix_total?: number;
  utility_tagged_open_count?: number;
  sovereignty_line?: string;
  operational_authority_line?: string;
  financial_sovereignty_line?: string;
  physical_baseline_line?: string;
};

export type DeadBugAlert = {
  project_id?: string;
  project_name?: string;
  hours_since_activity?: number;
  task_id?: string;
  title_hint?: string;
};

export type CockpitPayload = {
  date: string;
  google_calendar_connected: boolean;
  executive_score_percent: number;
  vanguard_executed: { deep: number; mixed: number; shallow: number };
  runway: RunwayPayload;
  kill_zones: { start_iso: string; end_iso: string }[];
  schedule_day_signals?: ScheduleDaySignals;
  daily_landscape: LandscapeApiRow[];
  personal_calendar_note: string;
  identity_alert?: boolean;
  integrity_protocol_confirmed?: boolean;
  personal_calendar_status?: "ok" | "not_configured" | "error";
  /** Last Gemini work-calendar screenshot analysis for this day (server-persisted). */
  work_calendar_advisory?: {
    time_coaching?: string;
    notes?: string;
    visibility?: string;
    saved_at?: string;
    tactical_brief?: TacticalBriefPeriods | null;
  } | null;
  /** Set when week-style work snapshot rows do not match this recon day (re-run analyze). */
  work_calendar_week_gap_hint?: string;
  /** Server-built plain summary: merged landscape + runway + work advisory + schedule read. */
  execution_day_summary?: string;
  golden_path_resolution_summary?: string;
  schedule_tradeoff_answers?: Record<string, string>;
  golden_path_proposals?: GoldenPathProposal[];
  golden_path_timeline?: GoldenPathTimelineRow[];
  golden_path_snoozed?: boolean;
  integrity_habit_snapshot?: IntegrityHabitSnapshot | null;
  identity_purpose?: string;
  sidebar_integrity?: SidebarIntegrity28d;
  graveyard_preview?: GraveyardPreviewEntry[];
  morning_brief?: MorningBriefPayload | null;
  integrity_consistency_percent?: number;
  integrity_sentry_state?: "NOMINAL" | "WARNING" | "CRITICAL";
  ops_posture_nudge_visible?: boolean;
  ops_posture_nudge_message?: string;
  focus_shell_window_active?: boolean;
  sacred_integrity_debt_count?: number;
  cockpit_operator_name?: string;
  sovereignty?: SovereigntyPayload;
  air_gap_active?: boolean;
  midday_shield_active?: boolean;
  identity_alignment_window_active?: boolean;
  air_gap_extension_suggested?: boolean;
  todoist_inbox_open_count?: number;
  inbox_slaughter_gate_ok?: boolean;
  dead_bug_alerts?: DeadBugAlert[];
  firefighting_signals?: string[];
  firewall_audit_summary?: string;
  favor_strike_days_clean_7d?: number;
  favor_strike_streak_7d?: number;
  commitments_partner_overdue?: boolean;
  ragstone_ledger?: Record<string, unknown>;
  zero_utility_labor_today?: boolean;
  evening_wins_count?: number;
  evening_leaks_count?: number;
};

/** Merged Daily landscape row (API + optional session screenshot advisory). */
export type LandscapeRowMerged =
  | LandscapeApiRow
  | {
      start_iso: string;
      title: string;
      source: string;
      source_kind: "work_screenshot";
    };
