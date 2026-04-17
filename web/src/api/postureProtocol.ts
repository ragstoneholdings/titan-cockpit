export type PostureItems = {
  chin_tucks: boolean;
  wall_slides: boolean;
  diaphragmatic_breathing: boolean;
};

export async function fetchPostureProtocol(day?: string): Promise<{ date: string; items: PostureItems }> {
  const q = day ? `?day=${encodeURIComponent(day)}` : "";
  const r = await fetch(`/api/posture-protocol${q}`);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ date: string; items: PostureItems }>;
}

export async function putPostureProtocol(
  day: string | undefined,
  partial: Partial<PostureItems>,
): Promise<{ date: string; items: PostureItems }> {
  const q = day ? `?day=${encodeURIComponent(day)}` : "";
  const r = await fetch(`/api/posture-protocol${q}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(partial),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ date: string; items: PostureItems }>;
}
