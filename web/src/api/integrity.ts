export async function fetchIntegrityStats(): Promise<Record<string, unknown>> {
  const r = await fetch("/api/integrity/stats");
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<Record<string, unknown>>;
}

export async function putIntegrityStats(body: Record<string, unknown>): Promise<Record<string, unknown>> {
  const r = await fetch("/api/integrity/stats", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<Record<string, unknown>>;
}
