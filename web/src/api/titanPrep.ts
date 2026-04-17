export type TitanPrepPayload = {
  week_start: string;
  text: string;
  generated_at: string | null;
  model: string;
  grounding_event_count?: number | null;
};

function titanPrepQuery(weekStart?: string, calendarId?: string): string {
  const p = new URLSearchParams();
  if (weekStart) p.set("week_start", weekStart);
  if (calendarId) p.set("calendar_id", calendarId);
  const s = p.toString();
  return s ? `?${s}` : "";
}

export async function fetchTitanPrep(weekStart?: string): Promise<TitanPrepPayload> {
  const r = await fetch(`/api/titan-prep${titanPrepQuery(weekStart)}`);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<TitanPrepPayload>;
}

export async function postTitanPrepGenerate(weekStart?: string, calendarId?: string): Promise<TitanPrepPayload> {
  const r = await fetch(`/api/titan-prep/generate${titanPrepQuery(weekStart, calendarId)}`, { method: "POST" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<TitanPrepPayload>;
}
