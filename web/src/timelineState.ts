/**
 * Golden Path day timeline: past / current / future relative to recon day and wall clock.
 */

export type TimelinePhase = "past" | "current" | "future";

function parseIsoMs(iso: string): number | null {
  const t = Date.parse(iso);
  return Number.isFinite(t) ? t : null;
}

/** When end_iso is missing, match server _row_end_fallback: start + 1 hour. */
function endMsFallback(startMs: number): number {
  return startMs + 60 * 60 * 1000;
}

/**
 * @param reconDay Local calendar YYYY-MM-DD (cockpit recon day)
 * @param now Wall-clock "now"
 * @param startIso Event start ISO string from API
 * @param endIso Event end ISO string from API (optional; +1h from start if empty)
 */
export function classifyTimelineRow(
  now: Date,
  reconDay: string,
  startIso: string,
  endIso: string | undefined,
): TimelinePhase {
  const today = reconDay.trim().slice(0, 10);
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  if (today < todayStr) return "past";
  if (today > todayStr) return "future";

  const startMs = parseIsoMs(startIso);
  if (startMs === null) return "future";
  let endMs: number;
  if (endIso && endIso.trim()) {
    const parsed = parseIsoMs(endIso);
    endMs = parsed !== null ? parsed : endMsFallback(startMs);
  } else {
    endMs = endMsFallback(startMs);
  }

  const n = now.getTime();
  if (n < startMs) return "future";
  if (n >= endMs) return "past";
  return "current";
}
