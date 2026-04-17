export type PowerTrioSlot = {
  slot: number;
  label: string;
  task_id: string;
  title: string;
  description: string;
  project_name: string;
  priority: number;
  /** Three verb-first micro-actions from Gemini (may be empty strings). */
  tactical_steps?: string[];
};

export type PowerTrioView = {
  slots: PowerTrioSlot[];
  ranked_total: number;
  task_total: number;
  rank_warning: string;
  merge_note: string;
  last_sync_iso: string;
  last_rank_iso: string;
  recon_day?: string;
};

export type TodoistStatus = {
  todoist_configured: boolean;
  gemini_configured: boolean;
  state_path: string;
};

export type GeminiAssistResponse = {
  text: string;
};
