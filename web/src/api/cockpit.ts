import type { CockpitPayload } from "../types/cockpit";

/** Cockpit builds calendars + signals; slow Google/token paths should not hang the UI forever. */
const COCKPIT_FETCH_TIMEOUT_MS = 90_000;

export async function fetchCockpit(params: {
  day?: string;
  vanguardDeep?: number;
  vanguardMixed?: number;
  vanguardShallow?: number;
}): Promise<CockpitPayload> {
  if (typeof window !== "undefined" && window.location.protocol === "file:") {
    throw new Error(
      "Open the Cockpit at http://localhost:5173 (Vite dev server), not as a file:// URL — relative /api calls will not work.",
    );
  }
  const q = new URLSearchParams();
  if (params.day) q.set("day", params.day);
  if (params.vanguardDeep != null) q.set("vanguard_deep", String(params.vanguardDeep));
  if (params.vanguardMixed != null) q.set("vanguard_mixed", String(params.vanguardMixed));
  if (params.vanguardShallow != null)
    q.set("vanguard_shallow", String(params.vanguardShallow));
  const url = `/api/cockpit${q.toString() ? `?${q}` : ""}`;
  const ctrl = new AbortController();
  const tid = setTimeout(() => ctrl.abort(), COCKPIT_FETCH_TIMEOUT_MS);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    if (!r.ok) {
      const t = await r.text();
      throw new Error(t || r.statusText);
    }
    return r.json() as Promise<CockpitPayload>;
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new Error(
        `Cockpit timed out after ${COCKPIT_FETCH_TIMEOUT_MS / 1000}s. Is the API up on port 8000, or is Google Calendar hanging? Try ./scripts/start_titan_cockpit.sh from the repo root.`,
      );
    }
    if (e instanceof TypeError) {
      throw new Error(
        "Could not reach the API. Start FastAPI on http://127.0.0.1:8000 (e.g. ./scripts/start_titan_cockpit.sh) and load the UI from http://localhost:5173.",
      );
    }
    throw e;
  } finally {
    clearTimeout(tid);
  }
}

export async function postMorningBriefDismiss(day: string): Promise<{ ok: boolean; day: string }> {
  const q = new URLSearchParams();
  q.set("day", day);
  const r = await fetch(`/api/cockpit/morning-brief/dismiss?${q}`, { method: "POST" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ ok: boolean; day: string }>;
}
