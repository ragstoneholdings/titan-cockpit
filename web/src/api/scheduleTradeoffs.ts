export async function getScheduleTradeoffs(day: string): Promise<{ date: string; answers: Record<string, string> }> {
  const r = await fetch(`/api/schedule-tradeoffs?day=${encodeURIComponent(day)}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ date: string; answers: Record<string, string> }>;
}

export async function putScheduleTradeoffs(
  day: string,
  body: Record<string, string>,
): Promise<{ date: string; answers: Record<string, string> }> {
  const r = await fetch(`/api/schedule-tradeoffs?day=${encodeURIComponent(day)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ date: string; answers: Record<string, string> }>;
}
