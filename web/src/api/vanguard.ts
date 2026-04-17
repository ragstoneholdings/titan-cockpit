/** Vanguard Cockpit LLM and day ledger API (proxied /api/vanguard/*). */

export async function postOpportunityCost(body: {
  title: string;
  notes?: string;
  estimated_minutes?: number | null;
}): Promise<{ ok: boolean; error?: string; narrative?: string; cuts?: string[] }> {
  const r = await fetch("/api/vanguard/opportunity-cost", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postWindshieldTriage(body: {
  text: string;
  mode?: "windshield" | "utility_alarm";
  append_bug_backlog?: boolean;
}): Promise<{ ok: boolean; error?: string; verdict?: string; one_line_reason?: string }> {
  const r = await fetch("/api/vanguard/windshield-triage", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postPastInPast(text: string): Promise<{
  ok: boolean;
  error?: string;
  rumination_score?: number;
  reframe?: string;
}> {
  const r = await fetch("/api/vanguard/past-in-past", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postCalendarLeanness(rows: Record<string, unknown>[]): Promise<{
  ok: boolean;
  error?: string;
  items?: { title: string; fat_score: number; extraction_plan_one_liner: string }[];
}> {
  const r = await fetch("/api/vanguard/calendar-leanness", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rows }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function postFirewallAuditSummary(signals: string[]): Promise<{ ok: boolean; summary: string }> {
  const r = await fetch("/api/vanguard/firewall-audit-summary", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ signals }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function putVanguardDay(
  day: string,
  patch: {
    inbox_cleared?: boolean;
    sleep_hours?: number;
    zero_utility_labor?: boolean;
    evening_wins?: string[];
    evening_leaks?: string[];
  },
): Promise<{ day: string; row: Record<string, unknown> }> {
  const q = new URLSearchParams();
  q.set("day", day);
  const r = await fetch(`/api/vanguard/day?${q}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
