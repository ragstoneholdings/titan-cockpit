import type { GeminiAssistResponse, PowerTrioView, TodoistStatus } from "../types/todoist";

export async function fetchTodoistStatus(): Promise<TodoistStatus> {
  const r = await fetch("/api/todoist/status");
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<TodoistStatus>;
}

export async function fetchPowerTrio(day?: string): Promise<PowerTrioView> {
  const q = day ? `?day=${encodeURIComponent(day)}` : "";
  const r = await fetch(`/api/todoist/power-trio${q}`);
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<PowerTrioView>;
}

export async function postTodoistSync(): Promise<{ task_count: number; merge_note: string }> {
  const r = await fetch("/api/todoist/sync", { method: "POST" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ task_count: number; merge_note: string }>;
}

export async function postTodoistRank(day?: string): Promise<{ rank_warning: string; trio: PowerTrioView }> {
  const q = day ? `?day=${encodeURIComponent(day)}` : "";
  const r = await fetch(`/api/todoist/rank${q}`, { method: "POST" });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ rank_warning: string; trio: PowerTrioView }>;
}

export async function postTodoistComplete(taskId: string, day?: string): Promise<{ trio: PowerTrioView }> {
  const r = await fetch("/api/todoist/complete", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, day: day ?? null }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<{ trio: PowerTrioView }>;
}

export async function postTodoistAssist(
  taskId: string,
  mode: "plan" | "strike",
): Promise<GeminiAssistResponse> {
  const r = await fetch("/api/todoist/assist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, mode }),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<GeminiAssistResponse>;
}
