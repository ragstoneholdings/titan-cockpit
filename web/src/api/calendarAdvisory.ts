export async function analyzeCalendarScreenshots(
  day: string,
  files: File[],
): Promise<{ ok: boolean; warning: string; advisory: Record<string, unknown> }> {
  const fd = new FormData();
  for (const f of files) {
    fd.append("files", f);
  }
  const r = await fetch(`/api/calendar/screenshots/analyze?day=${encodeURIComponent(day)}`, {
    method: "POST",
    body: fd,
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ ok: boolean; warning: string; advisory: Record<string, unknown> }>;
}
