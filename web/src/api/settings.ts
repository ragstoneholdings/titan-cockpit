export type GoogleAuthStatus = {
  connected: boolean;
  credentials_file_present: boolean;
  message: string;
};

export async function fetchGoogleAuthStatus(): Promise<GoogleAuthStatus> {
  const r = await fetch("/api/auth/google/status");
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<GoogleAuthStatus>;
}

export type RunwayOverride = {
  start_iso: string;
  title: string;
  source: "google" | "personal";
};

export async function fetchRunwayDay(day: string): Promise<{ date: string; override: RunwayOverride | null }> {
  const r = await fetch(`/api/runway/${day}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ date: string; override: RunwayOverride | null }>;
}

export async function putRunwayDay(day: string, body: RunwayOverride): Promise<void> {
  const r = await fetch(`/api/runway/${day}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(await r.text());
}

export async function deleteRunwayDay(day: string): Promise<void> {
  const r = await fetch(`/api/runway/${day}`, { method: "DELETE" });
  if (!r.ok) throw new Error(await r.text());
}

export type ProtocolSettings = {
  chief_hard_markers: string | null;
  chief_posture_minutes: number | null;
  chief_neck_minutes: number | null;
  chief_ops_minutes: number | null;
  resolved_chief_hard_markers: string;
  resolved_posture_minutes: number;
  resolved_neck_minutes: number;
  resolved_ops_minutes: number;
};

export async function fetchProtocol(): Promise<ProtocolSettings> {
  const r = await fetch("/api/protocol");
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<ProtocolSettings>;
}

export type ProtocolPatch = {
  chief_hard_markers?: string | null;
  chief_posture_minutes?: number | null;
  chief_neck_minutes?: number | null;
  chief_ops_minutes?: number | null;
};

export async function putProtocol(patch: ProtocolPatch): Promise<ProtocolSettings> {
  const r = await fetch("/api/protocol", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<ProtocolSettings>;
}

export async function fetchPurpose(): Promise<{ purpose: string }> {
  const r = await fetch("/api/identity/purpose");
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ purpose: string }>;
}

export async function putPurpose(purpose: string): Promise<{ purpose: string }> {
  const r = await fetch("/api/identity/purpose", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ purpose }),
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<{ purpose: string }>;
}
