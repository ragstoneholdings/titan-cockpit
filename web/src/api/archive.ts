export type GraveyardEntry = {
  task_id: string;
  title: string;
  closed_at: string;
  source: string;
};

export async function postJanitor(): Promise<{
  ok: boolean;
  closed_count: number;
  auto_fluff_closed_count?: number;
  hint: string;
  graveyard_appended: number;
}> {
  const r = await fetch("/api/todoist/janitor", { method: "POST" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{
    ok: boolean;
    closed_count: number;
    auto_fluff_closed_count?: number;
    hint: string;
    graveyard_appended: number;
  }>;
}

export async function fetchGraveyard(limit = 200): Promise<{ entries: GraveyardEntry[] }> {
  const r = await fetch(`/api/todoist/graveyard?limit=${limit}`);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ entries: GraveyardEntry[] }>;
}

export type GraveyardReopenResult = {
  ok: boolean;
  reopened: number;
  errors: string[];
  skipped_not_in_janitor_graveyard: string[];
  reopened_task_ids: string[];
};

export async function postGraveyardReopenToTodoist(taskIds: string[]): Promise<GraveyardReopenResult> {
  const r = await fetch("/api/todoist/graveyard/reopen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_ids: taskIds }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<GraveyardReopenResult>;
}
