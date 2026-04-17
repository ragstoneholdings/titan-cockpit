export async function postGoldenPathProposalAction(
  day: string,
  proposalId: string,
  action: "approve" | "dismiss" | "snooze",
): Promise<{ date: string; bucket: unknown }> {
  const r = await fetch(`/api/golden-path/proposal-action?day=${encodeURIComponent(day)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ proposal_id: proposalId, action }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ date: string; bucket: unknown }>;
}

export async function postGoldenPathClearSnooze(day: string): Promise<void> {
  const r = await fetch(`/api/golden-path/clear-snooze?day=${encodeURIComponent(day)}`, {
    method: "POST",
  });
  if (!r.ok) throw new Error(await r.text());
}
