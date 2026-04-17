import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { fetchCockpit, postMorningBriefDismiss } from "./api/cockpit";
import { analyzeCalendarScreenshots } from "./api/calendarAdvisory";
import {
  fetchGraveyard,
  postGraveyardReopenToTodoist,
  postJanitor,
  type GraveyardEntry,
} from "./api/archive";
import { fetchIntegrityStats, putIntegrityStats } from "./api/integrity";
import { fetchPostureProtocol, putPostureProtocol, type PostureItems } from "./api/postureProtocol";
import {
  fetchPowerTrio,
  fetchTodoistStatus,
  postTodoistAssist,
  postTodoistComplete,
  postTodoistRank,
  postTodoistSync,
} from "./api/todoist";
import { postGoldenPathClearSnooze, postGoldenPathProposalAction } from "./api/goldenPath";
import { fetchTitanPrep, postTitanPrepGenerate, type TitanPrepPayload } from "./api/titanPrep";
import {
  postCalendarLeanness,
  postFirewallAuditSummary,
  postOpportunityCost,
  postPastInPast,
  postWindshieldTriage,
  putVanguardDay,
} from "./api/vanguard";
import { putScheduleTradeoffs } from "./api/scheduleTradeoffs";
import {
  deleteRunwayDay,
  fetchGoogleAuthStatus,
  fetchProtocol,
  fetchPurpose,
  fetchRunwayDay,
  putProtocol,
  putPurpose,
  putRunwayDay,
  type GoogleAuthStatus,
  type ProtocolSettings,
} from "./api/settings";
import type {
  CockpitPayload,
  LandscapeRowMerged,
  MorningBriefPayload,
  ScheduleDaySignals,
  TacticalBriefLines,
  TacticalBriefPeriods,
} from "./types/cockpit";
import type { PowerTrioView, TodoistStatus } from "./types/todoist";
import { classifyTimelineRow } from "./timelineState";
import { activeTacticalBand, TACTICAL_BAND_LABEL, type TacticalBandKey } from "./tacticalBriefBands";
import "./app.css";

const EXECUTIVE_SCORE_TOOLTIP =
  "This score reflects Power Trio Executed counts for this browser session (deep / mixed / shallow), sent as query parameters when the cockpit loads. It resets when you change recon day or reload the page. It is not persisted server-side yet.";

const EMPTY_TRADEOFF_ANSWERS: Record<string, string> = {};

function isGraveyardReopenable(g: GraveyardEntry): boolean {
  return g.source === "janitor" || g.source === "janitor_auto";
}

/** Local calendar YYYY-MM-DD (avoid UTC drift from `toISOString().slice(0, 10)`). */
function localDateISO(d: Date = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Monday=0 … Sunday=6 (matches Python `date.weekday()`). */
function pyWeekday(d: Date): number {
  return (d.getDay() + 6) % 7;
}

/** Next calendar week’s Monday (local), matching `api.services.titan_sartorial_store.next_week_monday`. */
function nextWeekMondayISO(base: Date = new Date()): string {
  const t = new Date(base.getFullYear(), base.getMonth(), base.getDate());
  let delta = (7 - pyWeekday(t)) % 7;
  if (delta === 0) delta = 7;
  t.setDate(t.getDate() + delta);
  return localDateISO(t);
}

/** Monday of the ISO week containing the given calendar day. */
function mondayOfCalendarWeekContaining(iso: string): string {
  const d = new Date(iso + "T12:00:00");
  d.setDate(d.getDate() - pyWeekday(d));
  return localDateISO(d);
}

function formatDayHeader(iso: string) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatClock(iso: string) {
  return new Date(iso).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

function normalizeTacticalBriefPeriods(
  t: TacticalBriefPeriods | Record<string, unknown> | null | undefined,
): Record<TacticalBandKey, TacticalBriefLines> {
  const z = (): TacticalBriefLines => ({ fragmentation: "", kill_zone: "", priority: "" });
  if (!t || typeof t !== "object") return { morning: z(), afternoon: z(), evening: z() };
  const o = t as Record<string, unknown>;
  if (o.morning || o.afternoon || o.evening) {
    return {
      morning: { ...z(), ...(o.morning as TacticalBriefLines) },
      afternoon: { ...z(), ...(o.afternoon as TacticalBriefLines) },
      evening: { ...z(), ...(o.evening as TacticalBriefLines) },
    };
  }
  return {
    morning: {
      fragmentation: String(o.fragmentation || ""),
      kill_zone: String(o.kill_zone || ""),
      priority: String(o.priority || ""),
    },
    afternoon: z(),
    evening: z(),
  };
}

function tacticalBandHasLines(block: TacticalBriefLines | undefined): boolean {
  if (!block) return false;
  return Boolean(
    (block.fragmentation || "").trim() || (block.kill_zone || "").trim() || (block.priority || "").trim(),
  );
}

function tacticalBriefRowsFromBlock(block: TacticalBriefLines | undefined) {
  const defs = [
    { label: "Fragmentation", value: (block?.fragmentation || "").trim() },
    { label: "Kill zone", value: (block?.kill_zone || "").trim() },
    { label: "Priority", value: (block?.priority || "").trim() },
  ];
  return defs.filter((r) => r.value);
}

function isPostMorningRunway(
  now: Date,
  reconDay: string,
  anchorStartIso: string | null | undefined,
): boolean {
  if (reconDay !== localDateISO(now)) return false;
  if (anchorStartIso) {
    const t = Date.parse(anchorStartIso);
    if (Number.isFinite(t)) return now.getTime() >= t;
  }
  return now.getHours() >= 12;
}

function renderBriefInline(text: string): ReactNode {
  const parts = text.split(/\*\*/);
  if (parts.length === 1) return text;
  const out: ReactNode[] = [];
  parts.forEach((p, i) => {
    if (!p && i === 0) return;
    if (i % 2 === 1) {
      out.push(<strong key={i}>{p}</strong>);
    } else {
      out.push(<span key={i}>{p}</span>);
    }
  });
  return out;
}

function MorningBriefBody({ mb }: { mb: MorningBriefPayload }) {
  const lines = (mb.brief_markdown || "").split("\n");
  return (
    <div className="morning-brief-body">
      {lines.map((line, j) => {
        const t = line.trim();
        if (!t) return <br key={j} />;
        if (t.startsWith("### ")) {
          return (
            <h4 key={j} className="morning-brief-subhead">
              {t.slice(4)}
            </h4>
          );
        }
        return (
          <p key={j} className="morning-brief-line">
            {renderBriefInline(line)}
          </p>
        );
      })}
    </div>
  );
}

function IntegrityRailIcon({ kind }: { kind: "protocol" | "conflict" }) {
  const svgProps = {
    className: "integrity-rail-svg",
    width: 14,
    height: 14,
    viewBox: "0 0 24 24",
    fill: "none" as const,
    stroke: "currentColor",
    strokeWidth: 1.35,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };
  if (kind === "protocol") {
    return (
      <svg {...svgProps}>
        <circle cx="12" cy="12" r="7.5" />
        <path d="M12 9v6M9 12h6" />
      </svg>
    );
  }
  return (
    <svg {...svgProps}>
      <path d="M12 4v4M12 16v4M4 12h4M16 12h4" />
      <circle cx="12" cy="12" r="8" />
    </svg>
  );
}

function TrioSlotGlyph({ slot }: { slot: number }) {
  const svgProps = {
    className: "trio-slot-glyph",
    width: 22,
    height: 22,
    viewBox: "0 0 24 24",
    fill: "none" as const,
    stroke: "currentColor",
    strokeWidth: 1.25,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };
  if (slot === 0) {
    return (
      <svg {...svgProps}>
        <circle cx="12" cy="12" r="3.5" />
        <path d="M12 4v3M12 17v3M4 12h3M17 12h3" />
      </svg>
    );
  }
  if (slot === 1) {
    return (
      <svg {...svgProps}>
        <rect x="5" y="6" width="14" height="5" rx="1" />
        <rect x="5" y="13" width="14" height="5" rx="1" />
      </svg>
    );
  }
  return (
    <svg {...svgProps}>
      <path d="M6 8h12M6 12h12M6 16h9" />
    </svg>
  );
}

function landscapeRowMeta(ev: LandscapeRowMerged): {
  primary: string;
  secondary: string | null;
  badgeClass: string;
} {
  if (ev.source_kind === "work_screenshot") {
    return { primary: "Work (screenshot)", secondary: null, badgeClass: "tag-work-screenshot" };
  }
  const kind =
    ev.source_kind ?? (ev.source === "google" ? "personal_google" : "personal_ics");
  return {
    primary: "Personal",
    secondary: kind === "personal_google" ? "Google Calendar" : "Apple / ICS",
    badgeClass: "tag-personal-soft",
  };
}

function landscapeRowHint(ev: LandscapeRowMerged): string {
  if (ev.source_kind === "work_screenshot") return "screenshot";
  const k = ev.source_kind ?? (ev.source === "google" ? "personal_google" : "personal_ics");
  return k === "personal_google" ? "Google Calendar" : "Apple / ICS";
}

function overlapSourceLabel(tag: string): string {
  if (tag === "work_screenshot") return "Work (screenshot)";
  if (tag === "google") return "Google Calendar";
  if (tag === "personal") return "Apple / ICS";
  return tag;
}

function goldenPathTimelineChannel(row: { source_kind: string; source: string }): string {
  if (row.source_kind === "work_screenshot") return "Work (screenshot)";
  const k =
    row.source_kind === "personal_google" || row.source_kind === "personal_ics"
      ? row.source_kind
      : row.source === "google"
        ? "personal_google"
        : "personal_ics";
  return k === "personal_google" ? "Google Calendar" : "Apple / ICS";
}

function operatorBadgeText(display: string | undefined | null): string {
  const s = String(display || "").trim();
  if (!s) return "?";
  const parts = s.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    const a = parts[0][0] || "";
    const b = parts[parts.length - 1][0] || "";
    return (a + b).toUpperCase().slice(0, 2);
  }
  const alnum = s.replace(/[^a-zA-Z0-9]/g, "");
  if (alnum.length >= 2) return alnum.slice(0, 2).toUpperCase();
  return s.slice(0, 2).toUpperCase();
}

function SidebarIntegrityPreview({
  sidebarIntegrity,
  graveyardPreview,
  reconDay,
  sacredIntegrityDebtCount,
  onOpenIntegrity,
  onOpenArchive,
}: {
  sidebarIntegrity?: CockpitPayload["sidebar_integrity"];
  graveyardPreview?: CockpitPayload["graveyard_preview"];
  reconDay: string;
  sacredIntegrityDebtCount?: number;
  onOpenIntegrity: () => void;
  onOpenArchive: () => void;
}) {
  const si = sidebarIntegrity ?? { labels: [], posture_days: [], neck_days: [] };
  const labels = si.labels ?? [];
  const postureDays = si.posture_days ?? [];
  const neckDays = si.neck_days ?? [];
  const gy = graveyardPreview ?? [];

  return (
    <div className="sidebar-panels">
      <div className="sidebar-panel">
        <div className="sidebar-panel-kicker">Physical integrity</div>
        <p className="sidebar-panel-meta muted small">
          28d window → <strong>{reconDay}</strong> · posture from protocol history; neck from{" "}
          <code>integrity_stats.json</code>
        </p>
        <div className="integrity-heatmap-wrap" aria-label="Posture and neck consistency heatmap">
          <div className="integrity-heatmap-row integrity-heatmap-row--days">
            <span className="integrity-heatmap-protocol" aria-hidden />
            <div className="integrity-heatmap-cells">
              {labels.map((lb, i) => (
                <span key={`d-${i}`} className="integrity-heatmap-daylabel" title={`Day ${i + 1}`}>
                  {lb}
                </span>
              ))}
            </div>
          </div>
          <div className="integrity-heatmap-row">
            <span className="integrity-heatmap-protocol">Posture</span>
            <div className="integrity-heatmap-cells">
              {postureDays.map((on, i) => (
                <span
                  key={`p-${i}`}
                  className={`integrity-heatmap-cell${on ? " integrity-heatmap-cell--on" : ""}`}
                  title={labels[i] ? `${labels[i]}: ${on ? "done" : "—"}` : undefined}
                />
              ))}
            </div>
          </div>
          <div className="integrity-heatmap-row">
            <span className="integrity-heatmap-protocol">Neck</span>
            <div className="integrity-heatmap-cells">
              {neckDays.map((on, i) => (
                <span
                  key={`n-${i}`}
                  className={`integrity-heatmap-cell${on ? " integrity-heatmap-cell--neck" : ""}`}
                  title={labels[i] ? `${labels[i]}: ${on ? "logged" : "—"}` : undefined}
                />
              ))}
            </div>
          </div>
        </div>
        <button type="button" className="btn-trio sm sidebar-panel-link" onClick={onOpenIntegrity}>
          Open Physical Integrity
        </button>
      </div>
      {typeof sacredIntegrityDebtCount === "number" && sacredIntegrityDebtCount > 0 ? (
        <div className="sidebar-panel sidebar-panel--debt">
          <div className="sidebar-panel-kicker">Sacred integrity debt</div>
          <p className="sidebar-panel-meta muted small">
            <strong>{sacredIntegrityDebtCount}</strong> open sacred-tagged task(s) past due vs recon day. Clear or
            reschedule in Todoist.
          </p>
        </div>
      ) : null}
      <div className="sidebar-panel">
        <div className="sidebar-panel-kicker">System archive</div>
        <p className="sidebar-panel-meta muted small">Latest Janitor closes (graveyard).</p>
        <ul className="sidebar-graveyard-list">
          {gy.slice(0, 6).map((g) => (
            <li key={g.task_id + g.closed_at} className="sidebar-graveyard-item">
              <span className="sidebar-graveyard-time">
                {g.closed_at ? new Date(g.closed_at).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "—"}
              </span>
              <span className="sidebar-graveyard-title">{g.title || g.task_id}</span>
            </li>
          ))}
        </ul>
        {!gy.length ? <p className="muted small">No graveyard entries yet.</p> : null}
        <button type="button" className="btn-trio sm sidebar-panel-link" onClick={onOpenArchive}>
          Open System Archive
        </button>
      </div>
    </div>
  );
}

function defaultScheduleSignals(): ScheduleDaySignals {
  return {
    overlap_count: 0,
    overlaps: [],
    source_flags: [],
    meeting_load_minutes: 0,
    meeting_load_hours_display: "0h",
    meeting_load_warning: false,
    meeting_load_warn_threshold_minutes: 300,
    max_free_gap_minutes: 0,
    deep_slot_60_available: true,
    fragmented_day: false,
    small_gap_count: 0,
    immovable_title_hits: 0,
    suggestion_questions: [],
    suggestion_items: [],
    summary_line: "",
  };
}

function hasWorkCalendarIntel(
  wca: CockpitPayload["work_calendar_advisory"] | null | undefined,
): boolean {
  if (!wca) return false;
  const t = wca.tactical_brief;
  if (t && typeof t === "object") {
    const per = normalizeTacticalBriefPeriods(t);
    if (tacticalBandHasLines(per.morning) || tacticalBandHasLines(per.afternoon) || tacticalBandHasLines(per.evening)) {
      return true;
    }
  }
  if ((wca.time_coaching || "").trim()) return true;
  if ((wca.notes || "").trim()) return true;
  return false;
}

function TacticalBriefCard({
  wca,
  clockNow,
}: {
  wca: NonNullable<CockpitPayload["work_calendar_advisory"]>;
  clockNow: Date;
}) {
  const periods = normalizeTacticalBriefPeriods(wca.tactical_brief);
  const active = activeTacticalBand(clockNow);
  const bands: TacticalBandKey[] = ["morning", "afternoon", "evening"];
  const hasTactical = bands.some((b) => tacticalBriefRowsFromBlock(periods[b]).length > 0);
  const legacyCoaching = (wca.time_coaching || "").trim();
  const [legacyOpen, setLegacyOpen] = useState(false);
  return (
    <div className="cockpit-card tactical-brief-card" style={{ marginBottom: "0.75rem" }}>
      <div className="card-kicker">Tactical brief</div>
      {hasTactical ? (
        <div className="tactical-brief-periods">
          {bands.map((band) => {
            const rows = tacticalBriefRowsFromBlock(periods[band]);
            if (!rows.length) return null;
            return (
              <details key={band} className="tactical-brief-period-details" open={band === active}>
                <summary className="tactical-brief-period-summary">{TACTICAL_BAND_LABEL[band]}</summary>
                <ul className="tactical-brief-list tactical-brief-list--nested">
                  {rows.map((r) => (
                    <li key={r.label} className="tactical-brief-row">
                      <span className="tactical-brief-label">{r.label}</span>
                      <span className="tactical-brief-value">{r.value}</span>
                    </li>
                  ))}
                </ul>
              </details>
            );
          })}
        </div>
      ) : (
        <div className="tactical-brief-legacy-wrap">
          <p className="muted small">
            No structured tactical brief for this save — re-run screenshot analyze to upgrade.
          </p>
          {legacyCoaching ? (
            <details
              className="tactical-brief-legacy-details"
              open={legacyOpen}
              onToggle={(e) => setLegacyOpen((e.target as HTMLDetailsElement).open)}
            >
              <summary>Legacy coaching prose</summary>
              <pre className="tactical-brief-legacy">{wca.time_coaching}</pre>
            </details>
          ) : null}
        </div>
      )}
      {wca.notes?.trim() ? (
        <p className="muted small tactical-brief-notes" style={{ marginTop: "0.4rem" }}>
          <span className="tactical-brief-notes-label">Visibility: </span>
          {wca.notes}
        </p>
      ) : null}
    </div>
  );
}

function MonolithRunwayCard({
  kicker,
  slice,
  monolithPrepBarPct,
}: {
  kicker: string;
  slice: {
    integrity_wake_iso?: string | null;
    tactical_integrity_wake_iso?: string | null;
    anchor_start_iso?: string | null;
    anchor_title?: string | null;
  };
  monolithPrepBarPct: number;
}) {
  return (
    <div className="cockpit-card cockpit-card--wake cockpit-card--monolith">
      <div className="monolith-integrity-top">
        <span className="monolith-integrity-kicker">{kicker}</span>
        <div className="monolith-integrity-bar-wrap" title="Protocol minutes vs daily target">
          <div className="monolith-integrity-bar" style={{ width: `${monolithPrepBarPct}%` }} />
        </div>
      </div>
      <p className="wake-hero-line monolith-integrity-hero">
        <span className="wake-by-text">Wake by</span>
        <span className="wake-hero-time">
          {slice.integrity_wake_iso ? formatClock(slice.integrity_wake_iso) : "—"}
        </span>
      </p>
      {slice.anchor_start_iso ? (
        <p className="wake-subtext muted small">
          To complete posture, neck, and morning ops before{" "}
          <strong>{formatClock(slice.anchor_start_iso)}</strong>
          {slice.anchor_title ? ` — ${slice.anchor_title}` : ""}.
        </p>
      ) : (
        slice.integrity_wake_iso && (
          <p className="wake-subtext muted small">
            Includes full posture, neck, and morning ops before your first timed commitment.
          </p>
        )
      )}
      {slice.tactical_integrity_wake_iso ? (
        <div className="wake-tactical-footer">
          <p className="muted small">
            Fallback if short on time: {formatClock(slice.tactical_integrity_wake_iso)}
          </p>
          <details className="glossary glossary--compact">
            <summary>What is the fallback time?</summary>
            <p>
              Reduced prep (half posture/neck, no morning ops block) if you cannot hit the full-protocol wake time — use
              only when necessary.
            </p>
          </details>
        </div>
      ) : null}
    </div>
  );
}

function IntegrityHabitSparkline({ sessions }: { sessions: boolean[] }) {
  const seq = [...sessions.slice(0, 7)];
  while (seq.length < 7) seq.push(false);
  return (
    <div
      className="habit-spark-row"
      title="Posture protocol confirmations — last 7 entries in integrity_stats.json"
    >
      <span className="habit-spark-label">Posture 7d</span>
      <div className="habit-spark-dots" role="img" aria-label="Posture habit last seven days">
        {seq.map((ok, i) => (
          <span key={i} className={`habit-spark-dot${ok ? " habit-spark-dot--on" : ""}`} title={`Day ${i + 1}`} />
        ))}
      </div>
    </div>
  );
}

function formatThresholdHm(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h > 0 && m === 0) return `${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function ScheduleSignalsKillHint({
  sig,
  onOpenLandscape,
}: {
  sig: ScheduleDaySignals;
  onOpenLandscape: () => void;
}) {
  const q0 = sig.suggestion_questions[0];
  const thr = formatThresholdHm(sig.meeting_load_warn_threshold_minutes);
  const quiet =
    sig.overlap_count === 0 &&
    !sig.meeting_load_warning &&
    sig.deep_slot_60_available &&
    !sig.fragmented_day &&
    sig.source_flags.length === 0;

  if (quiet) {
    return (
      <div className="cockpit-card cockpit-card--compact schedule-signals">
        <div className="card-kicker">Schedule read</div>
        <p className="small" style={{ marginTop: "0.35rem" }}>
          {sig.summary_line}
        </p>
        <button type="button" className="btn-trio sm" style={{ marginTop: "0.5rem" }} onClick={onOpenLandscape}>
          {sig.overlap_count > 0 ? "Resolve overlapping meetings → Daily landscape" : "Open daily landscape"}
        </button>
      </div>
    );
  }

  const blockedLine = `~${sig.meeting_load_hours_display} on calendar (heavy flag at ≥${thr}).`;
  const gapLine = `Longest free gap in awake hours: ${sig.max_free_gap_minutes}m · 60m+ open slot: ${
    sig.deep_slot_60_available ? "yes" : "no"
  }${sig.fragmented_day ? " · short gaps" : ""}.`;

  return (
    <div className="cockpit-card cockpit-card--compact schedule-signals">
      <div className="card-kicker">Schedule read</div>
      <p className="small" style={{ marginTop: "0.35rem" }}>
        {sig.summary_line}
      </p>
      <p className="muted small" style={{ marginTop: "0.35rem" }}>
        {blockedLine} {gapLine}
      </p>
      {!sig.deep_slot_60_available ? (
        <p className="muted small">No single 60-minute free window in the default awake band.</p>
      ) : null}
      {q0 ? (
        <p className="small" style={{ marginTop: "0.5rem" }}>
          <strong>Ask yourself:</strong> {q0}
        </p>
      ) : null}
      <button type="button" className="btn-trio sm" style={{ marginTop: "0.5rem" }} onClick={onOpenLandscape}>
        {sig.overlap_count > 0 ? "Resolve overlapping meetings → Daily landscape" : "Open daily landscape"}
      </button>
    </div>
  );
}

function ScheduleSignalsLandscapePanel({
  day,
  sig,
  tradeoffAnswers,
  onTradeoffsSaved,
}: {
  day: string;
  sig: ScheduleDaySignals;
  tradeoffAnswers: Record<string, string>;
  onTradeoffsSaved: () => void;
}) {
  const thr = formatThresholdHm(sig.meeting_load_warn_threshold_minutes);
  const items = sig.suggestion_items ?? [];
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pressureCardOpen, setPressureCardOpen] = useState(true);

  useEffect(() => {
    setDraft({ ...tradeoffAnswers });
  }, [day, tradeoffAnswers]);

  async function handleSaveTradeoffs() {
    setBusy(true);
    setErr(null);
    try {
      const patch: Record<string, string> = {};
      for (const it of items) {
        const v = draft[it.id];
        if (v) patch[it.id] = v;
      }
      for (const o of sig.overlaps) {
        const oid = o.id;
        if (!oid) continue;
        const k = `overlap:${oid}`;
        const v = draft[k];
        if (v) patch[k] = v;
      }
      await putScheduleTradeoffs(day, patch);
      onTradeoffsSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const overlapCards = sig.overlaps.filter((o) => o.id);
  const canSaveTradeoffs = items.length > 0 || overlapCards.length > 0;

  const intakeComplete = useMemo(() => {
    if (!overlapCards.length && !items.length) return false;
    for (const o of overlapCards) {
      const k = `overlap:${o.id}`;
      const v = draft[k];
      if (v !== "a" && v !== "b") return false;
    }
    for (const it of items) {
      const v = draft[it.id];
      if (!v || !it.options.some((opt) => opt.value === v)) return false;
    }
    return true;
  }, [draft, overlapCards, items]);

  return (
    <details
      className="cockpit-card cockpit-card--compact schedule-signals schedule-signals-landscape-collapsible"
      style={{ marginBottom: "0.75rem" }}
      open={pressureCardOpen}
      onToggle={(e) => setPressureCardOpen(e.currentTarget.open)}
    >
      <summary className="schedule-signals-landscape-summary">
        <span className="card-kicker">Day pressure (intake rules)</span>
        <span className="small schedule-signals-landscape-summary-line">{sig.summary_line}</span>
      </summary>
      <div className="schedule-signals-landscape-body">
        <ul className="muted small schedule-signals-meta">
          <li>Calendar blocked ~{sig.meeting_load_hours_display} (heavy flag ≥{thr})</li>
          <li>Overlaps: {sig.overlap_count}</li>
          <li>Work vs calendar flags: {sig.source_flags.length}</li>
          <li>Immovable-pattern title hits: {sig.immovable_title_hits}</li>
        </ul>
        {overlapCards.length > 0 || items.length > 0 ? (
        <details className="schedule-intake-details" open={!intakeComplete}>
          <summary className="schedule-intake-summary muted small">
            {intakeComplete ? "Intake choices (saved draft — expand to edit)" : "Intake choices"}
          </summary>
          <div className="schedule-intake-details-body">
            {overlapCards.length > 0 ? (
              <div className="schedule-overlap-cards" style={{ marginTop: "0.65rem" }}>
                <div className="card-kicker">Overlapping meetings</div>
                <p className="muted small" style={{ marginTop: "0.25rem" }}>
                  Choose your planning truth for each clash (in-app merge only — calendars are not rewritten).
                </p>
                {overlapCards.map((o) => {
                  const k = `overlap:${o.id}`;
                  return (
                    <fieldset key={k} className="schedule-mcq-fieldset schedule-overlap-fieldset">
                      <legend className="schedule-mcq-legend">
                        {new Date(o.start_iso).toLocaleTimeString(undefined, {
                          hour: "numeric",
                          minute: "2-digit",
                        })}{" "}
                        –{" "}
                        {new Date(o.end_iso).toLocaleTimeString(undefined, {
                          hour: "numeric",
                          minute: "2-digit",
                        })}
                        : <em>{o.title_a}</em> ({overlapSourceLabel(o.source_a)}) vs <em>{o.title_b}</em> (
                        {overlapSourceLabel(o.source_b)})
                      </legend>
                      <div className="schedule-mcq-options">
                        <label className="schedule-mcq-label">
                          <input
                            type="radio"
                            name={`overlap-${o.id}`}
                            value="a"
                            checked={(draft[k] || "") === "a"}
                            onChange={() => setDraft((d) => ({ ...d, [k]: "a" }))}
                          />
                          <span>
                            Keep: {o.title_a} ({overlapSourceLabel(o.source_a)})
                          </span>
                        </label>
                        <label className="schedule-mcq-label">
                          <input
                            type="radio"
                            name={`overlap-${o.id}`}
                            value="b"
                            checked={(draft[k] || "") === "b"}
                            onChange={() => setDraft((d) => ({ ...d, [k]: "b" }))}
                          />
                          <span>
                            Keep: {o.title_b} ({overlapSourceLabel(o.source_b)})
                          </span>
                        </label>
                        <label className="schedule-mcq-label">
                          <input
                            type="radio"
                            name={`overlap-${o.id}`}
                            value="undecided"
                            checked={(draft[k] || "") === "undecided" || !(draft[k] || "").length}
                            onChange={() => setDraft((d) => ({ ...d, [k]: "undecided" }))}
                          />
                          <span>Not sure yet</span>
                        </label>
                      </div>
                    </fieldset>
                  );
                })}
              </div>
            ) : null}
            {items.length > 0 ? (
              <div className="schedule-tradeoff-mcq" style={{ marginTop: "0.75rem" }}>
                <div className="card-kicker">More intake questions</div>
                {items.map((it) => (
                  <fieldset key={it.id} className="schedule-mcq-fieldset">
                    <legend className="schedule-mcq-legend">{it.prompt}</legend>
                    <div className="schedule-mcq-options">
                      {it.options.map((opt) => (
                        <label key={opt.value} className="schedule-mcq-label">
                          <input
                            type="radio"
                            name={it.id}
                            value={opt.value}
                            checked={(draft[it.id] || "") === opt.value}
                            onChange={() => setDraft((d) => ({ ...d, [it.id]: opt.value }))}
                          />
                          <span>{opt.label}</span>
                        </label>
                      ))}
                    </div>
                  </fieldset>
                ))}
              </div>
            ) : null}
            {canSaveTradeoffs ? (
              <div className="schedule-tradeoff-save" style={{ marginTop: "0.75rem" }}>
                {err ? <p className="panel warn subtle" style={{ marginTop: "0.35rem" }}>{err}</p> : null}
                <button
                  type="button"
                  className="btn-trio sm primary"
                  disabled={busy}
                  onClick={() => void handleSaveTradeoffs()}
                >
                  {busy ? "Saving…" : "Save answers"}
                </button>
              </div>
            ) : null}
          </div>
        </details>
        ) : null}
        {sig.source_flags.length > 0 ? (
          <div style={{ marginTop: "0.5rem" }}>
            <div className="card-kicker">Work screenshot vs personal/API</div>
            <ul className="small schedule-signals-list">
              {sig.source_flags.map((f, i) => (
                <li key={`${f.start_iso}-${i}`}>
                  {f.message}{" "}
                  <span className="muted">
                    ({f.work_title} vs {f.personal_title} · {f.api_source})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </details>
  );
}

export default function App() {
  const [day, setDay] = useState(() => localDateISO());
  /** Wall clock for Golden Path day timeline past/current/future (ticks when recon day is today). */
  const [timelineNow, setTimelineNow] = useState(() => new Date());
  const [datePickerOpen, setDatePickerOpen] = useState(false);
  const headerDateRef = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);
  const [vanguard, setVanguard] = useState({ deep: 0, mixed: 0, shallow: 0 });
  const queryClient = useQueryClient();
  const cockpitQuery = useQuery({
    queryKey: ["cockpit", day, vanguard.deep, vanguard.mixed, vanguard.shallow],
    queryFn: () =>
      fetchCockpit({
        day,
        vanguardDeep: vanguard.deep,
        vanguardMixed: vanguard.mixed,
        vanguardShallow: vanguard.shallow,
      }),
    placeholderData: (previousData) => previousData,
  });
  const data = cockpitQuery.data ?? null;
  const loading = cockpitQuery.isLoading;
  const cockpitFetchErr =
    cockpitQuery.error == null
      ? null
      : cockpitQuery.error instanceof Error
        ? cockpitQuery.error.message
        : String(cockpitQuery.error);

  const [tdStatus, setTdStatus] = useState<TodoistStatus | null>(null);
  const [trio, setTrio] = useState<PowerTrioView | null>(null);
  const [trioErr, setTrioErr] = useState<string | null>(null);
  const [trioBusy, setTrioBusy] = useState(false);
  const [aiOps, setAiOps] = useState<{ id: string; label: string }[]>([]);
  const [goldenActionBusy, setGoldenActionBusy] = useState<string | null>(null);
  const [assist, setAssist] = useState<Record<string, { plan?: string; strike?: string }>>({});

  const [gAuth, setGAuth] = useState<GoogleAuthStatus | null>(null);
  const [calBanner, setCalBanner] = useState<string | null>(null);
  const [runwayStart, setRunwayStart] = useState("");
  const [runwayTitle, setRunwayTitle] = useState("");
  const [runwaySource, setRunwaySource] = useState<"google" | "personal">("google");
  const [runwayFillKey, setRunwayFillKey] = useState("");
  const [protocol, setProtocol] = useState<ProtocolSettings | null>(null);
  const [purposeText, setPurposeText] = useState("");
  const [purposeEditing, setPurposeEditing] = useState(false);
  const [purposeDraft, setPurposeDraft] = useState("");
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [settingsErr, setSettingsErr] = useState<string | null>(null);

  const [activeSection, setActiveSection] = useState<
    "cockpit" | "landscape" | "tools" | "integrity" | "archive"
  >("cockpit");
  const [integrityStats, setIntegrityStats] = useState<Record<string, unknown> | null>(null);
  const [integrityErr, setIntegrityErr] = useState<string | null>(null);
  const [integrityBusy, setIntegrityBusy] = useState(false);
  const [postureItems, setPostureItems] = useState<PostureItems | null>(null);
  const [postureProtoErr, setPostureProtoErr] = useState<string | null>(null);
  const [postureProtoBusy, setPostureProtoBusy] = useState(false);
  const [graveyard, setGraveyard] = useState<GraveyardEntry[]>([]);
  const [graveyardReopenSelected, setGraveyardReopenSelected] = useState<string[]>([]);
  const [graveyardNote, setGraveyardNote] = useState<string | null>(null);
  const [archiveErr, setArchiveErr] = useState<string | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [advisoryFiles, setAdvisoryFiles] = useState<FileList | null>(null);
  const [advisoryResult, setAdvisoryResult] = useState<Record<string, unknown> | null>(null);
  const [advisoryWarning, setAdvisoryWarning] = useState<string | null>(null);
  const [advisoryBusy, setAdvisoryBusy] = useState(false);
  const [advisoryErr, setAdvisoryErr] = useState<string | null>(null);
  const [focusShellOn, setFocusShellOn] = useState(false);
  const [opsNudgeDismissed, setOpsNudgeDismissed] = useState(false);
  const [titanPrep, setTitanPrep] = useState<TitanPrepPayload | null>(null);
  const [titanPrepBusy, setTitanPrepBusy] = useState(false);
  const [titanPrepErr, setTitanPrepErr] = useState<string | null>(null);
  const [titanWeekStart, setTitanWeekStart] = useState(nextWeekMondayISO);

  const [vanguardPaste, setVanguardPaste] = useState("");
  const [vanguardTriageResult, setVanguardTriageResult] = useState<string | null>(null);
  const [vanguardTriageBusy, setVanguardTriageBusy] = useState(false);
  const [vanguardTriageMode, setVanguardTriageMode] = useState<"windshield" | "utility_alarm">("windshield");
  const [vanguardOppTitle, setVanguardOppTitle] = useState("");
  const [vanguardOppNotes, setVanguardOppNotes] = useState("");
  const [vanguardOppResult, setVanguardOppResult] = useState<string | null>(null);
  const [vanguardOppBusy, setVanguardOppBusy] = useState(false);
  const [vanguardPipText, setVanguardPipText] = useState("");
  const [vanguardPipResult, setVanguardPipResult] = useState<string | null>(null);
  const [vanguardPipBusy, setVanguardPipBusy] = useState(false);
  const [vanguardLeanBusy, setVanguardLeanBusy] = useState(false);
  const [vanguardLeanResult, setVanguardLeanResult] = useState<string | null>(null);
  const [vanguardFwBusy, setVanguardFwBusy] = useState(false);
  const [vanguardFwResult, setVanguardFwResult] = useState<string | null>(null);
  const [vanguardDayBusy, setVanguardDayBusy] = useState(false);

  const mergedLandscape = useMemo((): LandscapeRowMerged[] => {
    if (!data) return [];
    return data.daily_landscape as LandscapeRowMerged[];
  }, [data]);

  const graveyardReopenableIds = useMemo(
    () => graveyard.filter(isGraveyardReopenable).map((g) => g.task_id),
    [graveyard],
  );

  const monolithPrepBarPct = useMemo(() => {
    if (!data) return 12;
    const exp = data.runway.prep_expected_total_minutes ?? 120;
    const tot = data.runway.prep_total_minutes ?? 0;
    return Math.min(100, Math.max(10, Math.round((tot / Math.max(1, exp)) * 100)));
  }, [data]);

  const withAi = useCallback(async <T,>(label: string, fn: () => Promise<T>): Promise<T> => {
    const id = `${Date.now()}-${Math.random()}`;
    setAiOps((o) => [...o, { id, label }]);
    try {
      return await fn();
    } finally {
      setAiOps((o) => o.filter((x) => x.id !== id));
    }
  }, []);

  const handleGoldenPathProposal = useCallback(
    async (proposalId: string, action: "approve" | "dismiss" | "snooze") => {
      setGoldenActionBusy(`${proposalId}:${action}`);
      try {
        await postGoldenPathProposalAction(day, proposalId, action);
        await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setGoldenActionBusy(null);
      }
    },
    [day, queryClient],
  );

  const handleClearGoldenSnooze = useCallback(async () => {
    setGoldenActionBusy("clear-snooze");
    try {
      await postGoldenPathClearSnooze(day);
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setGoldenActionBusy(null);
    }
  }, [day, queryClient]);

  const loadTrio = useCallback(async () => {
    setTrioErr(null);
    const d = day;
    const readOnly = d > localDateISO();
    try {
      const [st, view] = await Promise.all([fetchTodoistStatus(), fetchPowerTrio(d)]);
      setTdStatus(st);
      let next = view;
      if (!readOnly && view.task_total > 0 && !view.last_rank_iso) {
        const r = await withAi("Power Trio rank", () => postTodoistRank(d));
        next = r.trio;
      }
      setTrio(next);
    } catch (e) {
      setTrioErr(e instanceof Error ? e.message : String(e));
    }
  }, [day, withAi]);

  useEffect(() => {
    setOpsNudgeDismissed(sessionStorage.getItem(`opsPostureNudgeDismissed:${day}`) === "1");
  }, [day]);

  useEffect(() => {
    void loadTrio();
  }, [loadTrio]);

  useEffect(() => {
    if (activeSection !== "tools") return;
    let cancelled = false;
    setTitanPrepErr(null);
    void fetchTitanPrep(titanWeekStart)
      .then((r) => {
        if (!cancelled) setTitanPrep(r);
      })
      .catch((e) => {
        if (!cancelled) setTitanPrepErr(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [activeSection, titanWeekStart]);

  useEffect(() => {
    if (activeSection === "integrity") {
      setIntegrityErr(null);
      setPostureProtoErr(null);
      setPostureItems(null);
      let cancelled = false;
      void fetchPostureProtocol(day)
        .then((r) => {
          if (!cancelled) setPostureItems(r.items);
        })
        .catch((e) => {
          if (!cancelled) setPostureProtoErr(e instanceof Error ? e.message : String(e));
        });
      void fetchIntegrityStats()
        .then(setIntegrityStats)
        .catch((e) => setIntegrityErr(e instanceof Error ? e.message : String(e)));
      return () => {
        cancelled = true;
      };
    }
    if (activeSection === "archive") {
      setArchiveErr(null);
      setGraveyardNote(null);
      void fetchGraveyard()
        .then((r) => setGraveyard(r.entries))
        .catch((e) => setArchiveErr(e instanceof Error ? e.message : String(e)));
    }
  }, [activeSection, day]);

  useEffect(() => {
    setVanguard({ deep: 0, mixed: 0, shallow: 0 });
  }, [day]);

  useEffect(() => {
    setTimelineNow(new Date());
  }, [day]);

  useEffect(() => {
    const id = window.setInterval(() => setTimelineNow(new Date()), 60_000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    if (!datePickerOpen) return;
    function onDocMouseDown(ev: MouseEvent) {
      const el = headerDateRef.current;
      if (el && !el.contains(ev.target as Node)) setDatePickerOpen(false);
    }
    function onKey(ev: KeyboardEvent) {
      if (ev.key === "Escape") setDatePickerOpen(false);
    }
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [datePickerOpen]);

  useEffect(() => {
    void fetchGoogleAuthStatus().then(setGAuth).catch(() => {
      setGAuth(null);
    });
    void fetchProtocol()
      .then(setProtocol)
      .catch(() => setProtocol(null));
    void fetchPurpose()
      .then((r) => setPurposeText(r.purpose))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const ok = q.get("calendar") === "connected";
    const ce = q.get("calendar_error");
    if (ok) {
      setCalBanner("Google Calendar authorized. Cockpit will use work calendar events.");
    }
    if (ce) {
      setCalBanner(`Calendar OAuth error: ${decodeURIComponent(ce)}`);
    }
    if (ok || ce) {
      window.history.replaceState({}, "", window.location.pathname);
    }
    if (ok) {
      void queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    }
    if (ok) {
      void fetchGoogleAuthStatus().then(setGAuth).catch(() => setGAuth(null));
    }
  }, [queryClient]);

  useEffect(() => {
    void fetchRunwayDay(day)
      .then((r) => {
        if (r.override) {
          setRunwayStart(r.override.start_iso);
          setRunwayTitle(r.override.title);
          setRunwaySource(r.override.source);
        } else {
          setRunwayStart("");
          setRunwayTitle("");
          setRunwaySource("google");
        }
        setRunwayFillKey("");
      })
      .catch(() => {});
  }, [day]);

  function shiftDay(delta: number) {
    const d = new Date(day + "T12:00:00");
    d.setDate(d.getDate() + delta);
    setDay(localDateISO(d));
  }

  const forwardReadonly = (() => {
    const today = localDateISO();
    return day > today;
  })();

  async function handleSync() {
    setTrioBusy(true);
    setTrioErr(null);
    try {
      await withAi("Todoist sync", () => postTodoistSync());
      await loadTrio();
    } catch (e) {
      setTrioErr(e instanceof Error ? e.message : String(e));
    } finally {
      setTrioBusy(false);
    }
  }

  async function handleRank() {
    setTrioBusy(true);
    setTrioErr(null);
    try {
      const r = await withAi("Power Trio rank", () => postTodoistRank(day));
      setTrio(r.trio);
    } catch (e) {
      setTrioErr(e instanceof Error ? e.message : String(e));
    } finally {
      setTrioBusy(false);
    }
  }

  async function handleComplete(taskId: string, slot: number) {
    setTrioBusy(true);
    setTrioErr(null);
    try {
      const r = await postTodoistComplete(taskId, day);
      setTrio(r.trio);
      setVanguard((v) => ({
        deep: v.deep + (slot === 0 ? 1 : 0),
        mixed: v.mixed + (slot === 1 ? 1 : 0),
        shallow: v.shallow + (slot === 2 ? 1 : 0),
      }));
    } catch (e) {
      setTrioErr(e instanceof Error ? e.message : String(e));
    } finally {
      setTrioBusy(false);
    }
  }

  async function handleSaveRunway() {
    setSettingsBusy(true);
    setSettingsErr(null);
    try {
      await putRunwayDay(day, {
        start_iso: runwayStart.trim(),
        title: runwayTitle.trim(),
        source: runwaySource,
      });
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setSettingsErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSettingsBusy(false);
    }
  }

  async function handleClearRunway() {
    setSettingsBusy(true);
    setSettingsErr(null);
    try {
      await deleteRunwayDay(day);
      setRunwayStart("");
      setRunwayTitle("");
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setSettingsErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSettingsBusy(false);
    }
  }

  async function handleSaveProtocol() {
    if (!protocol) return;
    setSettingsBusy(true);
    setSettingsErr(null);
    try {
      const p = await putProtocol({
        chief_hard_markers: protocol.chief_hard_markers,
        chief_posture_minutes: protocol.chief_posture_minutes,
        chief_neck_minutes: protocol.chief_neck_minutes,
        chief_ops_minutes: protocol.chief_ops_minutes,
      });
      setProtocol(p);
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setSettingsErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSettingsBusy(false);
    }
  }

  async function handleSavePurpose() {
    setSettingsBusy(true);
    setSettingsErr(null);
    try {
      const r = await putPurpose(purposeText);
      setPurposeText(r.purpose);
    } catch (e) {
      setSettingsErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSettingsBusy(false);
    }
  }

  async function handleSavePurposePillar() {
    setSettingsBusy(true);
    setSettingsErr(null);
    try {
      const r = await putPurpose(purposeDraft);
      setPurposeText(r.purpose);
      setPurposeEditing(false);
    } catch (e) {
      setSettingsErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSettingsBusy(false);
    }
  }

  async function handleSaveIntegrity() {
    if (!integrityStats) return;
    setIntegrityBusy(true);
    setIntegrityErr(null);
    setPostureProtoErr(null);
    try {
      const r = await putIntegrityStats(integrityStats);
      setIntegrityStats(r);
    } catch (e) {
      setIntegrityErr(e instanceof Error ? e.message : String(e));
    } finally {
      setIntegrityBusy(false);
    }
    if (postureItems) {
      setPostureProtoBusy(true);
      try {
        const pr = await putPostureProtocol(day, postureItems);
        setPostureItems(pr.items);
      } catch (e) {
        setPostureProtoErr(e instanceof Error ? e.message : String(e));
      } finally {
        setPostureProtoBusy(false);
      }
    }
    void queryClient.invalidateQueries({ queryKey: ["cockpit"] }).catch(() => {});
  }

  async function handlePostureToggle(key: keyof PostureItems, checked: boolean) {
    setPostureProtoBusy(true);
    setPostureProtoErr(null);
    setPostureItems((prev) => (prev ? { ...prev, [key]: checked } : prev));
    try {
      const r = await putPostureProtocol(day, { [key]: checked });
      setPostureItems(r.items);
    } catch (e) {
      setPostureProtoErr(e instanceof Error ? e.message : String(e));
      try {
        const ref = await fetchPostureProtocol(day);
        setPostureItems(ref.items);
      } catch {
        setPostureItems(null);
      }
    } finally {
      setPostureProtoBusy(false);
    }
    void queryClient.invalidateQueries({ queryKey: ["cockpit"] }).catch(() => {});
  }

  async function handleRunJanitor() {
    setArchiveBusy(true);
    setArchiveErr(null);
    setGraveyardNote(null);
    try {
      await postJanitor();
      const r = await fetchGraveyard();
      setGraveyard(r.entries);
      setGraveyardReopenSelected([]);
    } catch (e) {
      setArchiveErr(e instanceof Error ? e.message : String(e));
    } finally {
      setArchiveBusy(false);
    }
  }

  async function handleReopenGraveyardInTodoist() {
    if (!graveyardReopenSelected.length) return;
    setArchiveBusy(true);
    setArchiveErr(null);
    setGraveyardNote(null);
    try {
      const res = await postGraveyardReopenToTodoist(graveyardReopenSelected);
      const bits: string[] = [];
      if (res.reopened > 0) bits.push(`Reopened ${res.reopened} in Todoist`);
      if (res.skipped_not_in_janitor_graveyard.length) {
        bits.push(`Skipped ${res.skipped_not_in_janitor_graveyard.length} (not janitor graveyard)`);
      }
      if (res.errors.length) bits.push(`Errors: ${res.errors.join("; ")}`);
      setGraveyardNote(bits.length ? `${bits.join(". ")}.` : null);
      const r = await fetchGraveyard();
      setGraveyard(r.entries);
      setGraveyardReopenSelected([]);
    } catch (e) {
      setArchiveErr(e instanceof Error ? e.message : String(e));
    } finally {
      setArchiveBusy(false);
    }
  }

  async function handleAdvisoryAnalyze() {
    if (!advisoryFiles?.length) return;
    setAdvisoryBusy(true);
    setAdvisoryErr(null);
    try {
      const r = await withAi("Calendar screenshot analyze", () =>
        analyzeCalendarScreenshots(day, Array.from(advisoryFiles)),
      );
      const adv = r.advisory as Record<string, unknown>;
      setAdvisoryResult(adv);
      setAdvisoryWarning((r.warning || "").trim() || null);
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setAdvisoryErr(e instanceof Error ? e.message : String(e));
    } finally {
      setAdvisoryBusy(false);
    }
  }

  async function handleDismissMorningBrief() {
    try {
      await postMorningBriefDismiss(day);
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleAssist(taskId: string, mode: "plan" | "strike") {
    setTrioBusy(true);
    setTrioErr(null);
    try {
      const r = await withAi(
        mode === "plan" ? "Gemini plan" : "Gemini strike",
        () => postTodoistAssist(taskId, mode),
      );
      setAssist((prev) => ({
        ...prev,
        [taskId]: { ...prev[taskId], [mode === "plan" ? "plan" : "strike"]: r.text },
      }));
    } catch (e) {
      setTrioErr(e instanceof Error ? e.message : String(e));
    } finally {
      setTrioBusy(false);
    }
  }

  const identityAlert = Boolean(data?.identity_alert);
  const integrityProtocolConfirmed = Boolean(data?.integrity_protocol_confirmed);
  const sentryState = data?.integrity_sentry_state ?? "NOMINAL";
  const consistencyPct = data?.integrity_consistency_percent ?? 100;
  const sentryCritical = sentryState === "CRITICAL";
  /** CRITICAL can mean low 28d consistency alone; do not treat like "today's checkboxes incomplete" once protocol is confirmed. */
  const redIntegrityShell =
    identityAlert || (sentryCritical && !integrityProtocolConfirmed);
  const hideAuxNav = Boolean(focusShellOn && data?.focus_shell_window_active);
  const cockpitShellClass = [
    "cockpit",
    redIntegrityShell ? " identity-alert cockpit--red-shift" : "",
    sentryState === "WARNING" ? " cockpit--sentry-warning" : "",
    consistencyPct >= 90 ? " cockpit-theme-sharp" : "",
    consistencyPct < 80 ? " cockpit-theme-muted" : "",
    hideAuxNav ? " cockpit--focus-shell" : "",
  ]
    .filter(Boolean)
    .join("");

  async function handleTitanPrepGenerate() {
    setTitanPrepBusy(true);
    setTitanPrepErr(null);
    try {
      const r = await withAi("Week-ahead wardrobe pass", () => postTitanPrepGenerate(titanWeekStart));
      setTitanPrep(r);
    } catch (e) {
      setTitanPrepErr(e instanceof Error ? e.message : String(e));
    } finally {
      setTitanPrepBusy(false);
    }
  }

  async function handleInboxGate(checked: boolean) {
    setVanguardDayBusy(true);
    try {
      await putVanguardDay(day, { inbox_cleared: checked });
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setVanguardDayBusy(false);
    }
  }

  async function handleZeroUtilityLabor(checked: boolean) {
    setVanguardDayBusy(true);
    try {
      await putVanguardDay(day, { zero_utility_labor: checked });
      await queryClient.invalidateQueries({ queryKey: ["cockpit"] });
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setVanguardDayBusy(false);
    }
  }

  async function handleVanguardTriage() {
    if (!vanguardPaste.trim()) return;
    setVanguardTriageBusy(true);
    setVanguardTriageResult(null);
    try {
      const r = await withAi("Windshield triage", () =>
        postWindshieldTriage({
          text: vanguardPaste,
          mode: vanguardTriageMode,
          append_bug_backlog: false,
        }),
      );
      setVanguardTriageResult(
        r.ok
          ? `${r.verdict}: ${r.one_line_reason || ""}`
          : r.error || "Error",
      );
    } catch (e) {
      setVanguardTriageResult(e instanceof Error ? e.message : String(e));
    } finally {
      setVanguardTriageBusy(false);
    }
  }

  async function handleVanguardOpp() {
    if (!vanguardOppTitle.trim()) return;
    setVanguardOppBusy(true);
    setVanguardOppResult(null);
    try {
      const r = await withAi("Opportunity cost", () =>
        postOpportunityCost({ title: vanguardOppTitle, notes: vanguardOppNotes }),
      );
      const cuts = (r.cuts || []).join(" · ");
      setVanguardOppResult(r.ok ? `${r.narrative || ""}${cuts ? ` · ${cuts}` : ""}` : r.error || "");
    } catch (e) {
      setVanguardOppResult(e instanceof Error ? e.message : String(e));
    } finally {
      setVanguardOppBusy(false);
    }
  }

  async function handleVanguardPip() {
    if (!vanguardPipText.trim()) return;
    setVanguardPipBusy(true);
    setVanguardPipResult(null);
    try {
      const r = await withAi("Past-in-the-past", () => postPastInPast(vanguardPipText));
      const rs = typeof r.rumination_score === "number" ? r.rumination_score : 0;
      setVanguardPipResult(r.ok ? `${rs.toFixed(2)} · ${r.reframe || ""}` : r.error || "");
    } catch (e) {
      setVanguardPipResult(e instanceof Error ? e.message : String(e));
    } finally {
      setVanguardPipBusy(false);
    }
  }

  async function handleVanguardLean() {
    if (!mergedLandscape.length) return;
    setVanguardLeanBusy(true);
    setVanguardLeanResult(null);
    try {
      const rows = mergedLandscape.map((r) => {
        const row: Record<string, unknown> = { start_iso: r.start_iso, title: r.title };
        if ("end_iso" in r && typeof (r as { end_iso?: string }).end_iso === "string") {
          row.end_iso = (r as { end_iso: string }).end_iso;
        }
        return row;
      });
      const r = await withAi("Calendar leanness", () => postCalendarLeanness(rows));
      if (r.ok && r.items?.length) {
        setVanguardLeanResult(
          r.items.map((it) => `${it.title}: ${it.extraction_plan_one_liner}`).join(" · "),
        );
      } else {
        setVanguardLeanResult(r.error || "No items.");
      }
    } catch (e) {
      setVanguardLeanResult(e instanceof Error ? e.message : String(e));
    } finally {
      setVanguardLeanBusy(false);
    }
  }

  async function handleVanguardFirewall() {
    const sigs = data?.firefighting_signals || [];
    if (!sigs.length) {
      setVanguardFwResult("No firefighting signals on snapshot.");
      return;
    }
    setVanguardFwBusy(true);
    setVanguardFwResult(null);
    try {
      const r = await withAi("Firewall audit", () => postFirewallAuditSummary(sigs));
      setVanguardFwResult(r.summary || "(empty)");
    } catch (e) {
      setVanguardFwResult(e instanceof Error ? e.message : String(e));
    } finally {
      setVanguardFwBusy(false);
    }
  }

  return (
    <div className={cockpitShellClass}>
      <aside className="cockpit-sidebar">
        <div className="sidebar-brand">Titan Cockpit</div>
        {data?.cockpit_operator_name?.trim() ? (
          <div className="sidebar-operator muted small">{data.cockpit_operator_name}</div>
        ) : null}
        <div className="sidebar-muted">Monolith V4 · API preview</div>
        <nav className="sidebar-nav">
          <button
            type="button"
            className={`sidebar-nav-item${activeSection === "cockpit" ? " active" : ""}`}
            onClick={() => setActiveSection("cockpit")}
          >
            Cockpit
          </button>
          {!hideAuxNav ? (
            <button
              type="button"
              className={`sidebar-nav-item${activeSection === "landscape" ? " active" : ""}`}
              onClick={() => setActiveSection("landscape")}
            >
              Daily landscape
            </button>
          ) : null}
          {!hideAuxNav ? (
            <button
              type="button"
              className={`sidebar-nav-item${activeSection === "tools" ? " active" : ""}`}
              onClick={() => setActiveSection("tools")}
            >
              Tools
            </button>
          ) : null}
          <button
            type="button"
            className={`sidebar-nav-item${activeSection === "integrity" ? " active" : ""}`}
            onClick={() => setActiveSection("integrity")}
          >
            Physical Integrity
          </button>
          {!hideAuxNav ? (
            <button
              type="button"
              className={`sidebar-nav-item${activeSection === "archive" ? " active" : ""}`}
              onClick={() => setActiveSection("archive")}
            >
              System Archive
            </button>
          ) : null}
        </nav>
        {data ? (
          <SidebarIntegrityPreview
            sidebarIntegrity={data.sidebar_integrity}
            graveyardPreview={data.graveyard_preview}
            reconDay={day}
            sacredIntegrityDebtCount={data.sacred_integrity_debt_count}
            onOpenIntegrity={() => setActiveSection("integrity")}
            onOpenArchive={() => setActiveSection("archive")}
          />
        ) : null}
      </aside>

      <main className="cockpit-main">
        <header className="cockpit-header">
          <div className="header-date" ref={headerDateRef}>
            <button type="button" className="chev" onClick={() => shiftDay(-1)} aria-label="Previous day">
              ‹
            </button>
            <div className="header-date-picker-anchor">
              <button
                type="button"
                className="header-date-label-btn"
                aria-expanded={datePickerOpen}
                aria-haspopup="dialog"
                aria-label="Choose recon date"
                onClick={() => setDatePickerOpen((o) => !o)}
              >
                {formatDayHeader(day).toUpperCase()}
              </button>
              {datePickerOpen ? (
                <div className="header-date-popover" role="dialog" aria-label="Select recon date">
                  <label className="header-date-popover-label">
                    <span className="muted small">Jump to date</span>
                    <input
                      type="date"
                      className="header-date-input"
                      value={day}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v) setDay(v);
                        setDatePickerOpen(false);
                      }}
                    />
                  </label>
                </div>
              ) : null}
            </div>
            <button type="button" className="chev" onClick={() => shiftDay(1)} aria-label="Next day">
              ›
            </button>
          </div>
          {aiOps.length > 0 ? (
            <div className="header-ai-pill" title={aiOps.map((o) => o.label).join(" · ")}>
              AI · {aiOps.length}
            </div>
          ) : null}
          {data?.focus_shell_window_active ? (
            <button
              type="button"
              className={`btn-trio sm header-focus-btn${focusShellOn ? " primary" : ""}`}
              title="Deep work shell: hide auxiliary nav and emphasize Combat"
              onClick={() => setFocusShellOn((v) => !v)}
            >
              {focusShellOn ? "Exit focus" : "Focus shell"}
            </button>
          ) : null}
          <div className="header-toolbar-spacer" aria-hidden />
          <div className="header-score" title={EXECUTIVE_SCORE_TOOLTIP}>
            <span className="header-score-label">Executive score</span>
            <span className="header-score-value">
              {loading ? "—" : data ? `${Math.round(data.executive_score_percent)}%` : "—"}
            </span>
            {!loading && data ? (
              <span className="header-score-discipline muted small" style={{ display: "block", marginTop: "0.15rem" }}>
                Discipline {Math.round(data.integrity_consistency_percent ?? 100)}%
              </span>
            ) : null}
          </div>
          <div
            className="header-badge"
            title={data?.runway?.operator_display?.trim() ? data.runway.operator_display : "Operator"}
          >
            {loading || !data ? "—" : operatorBadgeText(data.runway.operator_display)}
          </div>
        </header>

        {data?.ops_posture_nudge_visible && !opsNudgeDismissed ? (
          <div className="panel ops-posture-nudge">
            <span>{data.ops_posture_nudge_message || "Posture: hold the frame."}</span>
            <button
              type="button"
              className="btn-trio sm"
              onClick={() => {
                sessionStorage.setItem(`opsPostureNudgeDismissed:${day}`, "1");
                setOpsNudgeDismissed(true);
              }}
            >
              Dismiss
            </button>
          </div>
        ) : null}
        {redIntegrityShell && (
          <div className="panel identity-alert-banner identity-alert-banner--strip">
            <span className="identity-alert-banner-text">
              {identityAlert
                ? "System: integrity protocol not confirmed after wake + 15m — check in required."
                : "OPERATOR OUT OF ALIGNMENT. Discipline consistency is in CRITICAL band — execute morning ops and physical protocol to reclaim the frame."}
            </span>
            <button
              type="button"
              className="btn-trio sm primary identity-alert-banner-action"
              onClick={() => setActiveSection("integrity")}
            >
              Open Physical Integrity
            </button>
          </div>
        )}
        <div
          className={
            redIntegrityShell ? "cockpit-main-body cockpit-main-body--red-dim" : "cockpit-main-body"
          }
        >
        {(err ?? cockpitFetchErr) && (
          <div className="panel error">{err ?? cockpitFetchErr}</div>
        )}
        {settingsErr && <div className="panel error">{settingsErr}</div>}
        {calBanner && <div className="panel warn subtle">{calBanner}</div>}
        {activeSection === "cockpit" && data?.work_calendar_week_gap_hint?.trim() ? (
          <div className="panel warn subtle">{data.work_calendar_week_gap_hint}</div>
        ) : null}
        {loading && <div className="panel muted">Loading cockpit…</div>}

        {activeSection === "integrity" && (
          <section className="panel">
            <div className="panel-head">
              <h2>Physical Integrity</h2>
            </div>
            {integrityErr && <div className="panel warn subtle">{integrityErr}</div>}
            {postureProtoErr && <div className="panel warn subtle">{postureProtoErr}</div>}
            <h3 className="subhead">Posture protocol</h3>
            <p className="muted small">
              Check off items for <strong>{day}</strong> in <code>posture_protocol_state.json</code> (same file as
              Streamlit). Each toggle saves immediately; <strong>Save</strong> below also rewrites these checkboxes if
              you prefer one confirmation for notes + posture.
            </p>
            {postureItems ? (
              <div className="posture-protocol-checks" style={{ marginBottom: "1rem" }}>
                {(
                  [
                    ["chin_tucks", "Chin tucks"],
                    ["wall_slides", "Wall slides"],
                    ["diaphragmatic_breathing", "Diaphragmatic breathing"],
                  ] as const
                ).map(([id, label]) => (
                  <label key={id} className="settings-field block" style={{ marginTop: "0.35rem" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <input
                        type="checkbox"
                        checked={postureItems[id]}
                        disabled={postureProtoBusy}
                        onChange={(e) => void handlePostureToggle(id, e.target.checked)}
                      />
                      <span>{label}</span>
                    </span>
                  </label>
                ))}
              </div>
            ) : (
              <p className="muted small" style={{ marginBottom: "1rem" }}>
                Loading posture checkoffs…
              </p>
            )}
            {integrityStats && (
              <>
                <h3 className="subhead">Integrity notes</h3>
                <label className="settings-field block">
                  Notes
                  <textarea
                    className="settings-input tall"
                    value={String(integrityStats.notes ?? "")}
                    disabled={integrityBusy}
                    onChange={(e) => setIntegrityStats({ ...integrityStats, notes: e.target.value })}
                    rows={3}
                  />
                </label>
                <p className="muted small">
                  Backed by <code>integrity_stats.json</code>. Expand this schema as your protocol tracking
                  grows.
                </p>
                <button
                  type="button"
                  className="btn-trio primary"
                  disabled={integrityBusy || postureProtoBusy}
                  onClick={() => void handleSaveIntegrity()}
                >
                  Save notes &amp; posture
                </button>
              </>
            )}
            {!integrityStats && !integrityErr && <p className="muted">Loading…</p>}
          </section>
        )}

        {activeSection === "archive" && (
          <section className="panel">
            <div className="panel-head">
              <h2>System Archive</h2>
            </div>
            {archiveErr && <div className="panel warn subtle">{archiveErr}</div>}
            {graveyardNote && <div className="panel muted">{graveyardNote}</div>}
            <p className="muted small">
              Janitor closes stale open tasks (14d) except <code>@Titan_Core</code>. With{" "}
              <code>JANITOR_AUTO_ARCHIVE_FLUFF=1</code>, matching fluff tasks are auto-closed and logged as{" "}
              <code>janitor_auto</code> in the graveyard. Closed tasks append to the graveyard log. Select janitor
              rows and use Reopen in Todoist to restore them as active tasks (same task ids).
            </p>
            <div className="trio-actions">
              <button type="button" className="btn-trio primary" disabled={archiveBusy} onClick={() => void handleRunJanitor()}>
                Run janitor
              </button>
            </div>
            <h3 className="subhead">Graveyard</h3>
            <div className="trio-actions graveyard-reopen-actions">
              <button
                type="button"
                className="btn-trio sm"
                disabled={archiveBusy || !graveyardReopenableIds.length}
                onClick={() => setGraveyardReopenSelected([...graveyardReopenableIds])}
              >
                Select all reopenable
              </button>
              <button
                type="button"
                className="btn-trio sm"
                disabled={archiveBusy || !graveyardReopenSelected.length}
                onClick={() => setGraveyardReopenSelected([])}
              >
                Clear selection
              </button>
              <button
                type="button"
                className="btn-trio primary"
                disabled={archiveBusy || !graveyardReopenSelected.length}
                onClick={() => void handleReopenGraveyardInTodoist()}
              >
                Reopen in Todoist
              </button>
            </div>
            <ul className="graveyard-list">
              {graveyard.map((g) => {
                const reopenable = isGraveyardReopenable(g);
                const checked = graveyardReopenSelected.includes(g.task_id);
                return (
                  <li key={g.task_id + g.closed_at}>
                    <span className="graveyard-reopen-slot" title={reopenable ? "Reopenable in Todoist" : ""}>
                      {reopenable ? (
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={archiveBusy}
                          onChange={(e) => {
                            const on = e.target.checked;
                            setGraveyardReopenSelected((prev) =>
                              on ? [...new Set([...prev, g.task_id])] : prev.filter((id) => id !== g.task_id),
                            );
                          }}
                          aria-label={`Select ${g.title || g.task_id} for reopen`}
                        />
                      ) : null}
                    </span>
                    <span className="landscape-time">{new Date(g.closed_at).toLocaleString()}</span>
                    <span className="landscape-title">{g.title}</span>
                    <span className="muted small">
                      {g.task_id} · {g.source}
                    </span>
                  </li>
                );
              })}
            </ul>
            {!graveyard.length && <p className="muted small">No graveyard entries yet.</p>}
          </section>
        )}

        {!loading && data && activeSection === "cockpit" && (
          <>
            {data.morning_brief?.visible ? (
              <div className="cockpit-card morning-brief-card">
                <div className="morning-brief-card__head">
                  <div>
                    <div className="card-kicker morning-brief-kicker">Morning brief</div>
                    <p className="muted small" style={{ marginTop: "0.25rem", marginBottom: 0 }}>
                      Optimization scan — anchors, kill zones, Combat task alignment.
                    </p>
                  </div>
                  <button type="button" className="btn-trio sm" onClick={() => void handleDismissMorningBrief()}>
                    Dismiss
                  </button>
                </div>
                <MorningBriefBody mb={data.morning_brief} />
              </div>
            ) : null}
            {data.sovereignty ? (
              <div className="cockpit-card cockpit-card--compact vanguard-sovereignty-card">
                <div className="card-kicker">Sovereignty</div>
                <p className="muted small" style={{ margin: 0 }} title={data.sovereignty.sovereignty_line}>
                  SQ {data.sovereignty.sovereignty_quotient_blended_percent ?? data.sovereignty.sovereignty_quotient_percent ?? 0}% ·{" "}
                  {data.sovereignty.sovereignty_line || "—"}
                </p>
                <p className="muted small" style={{ margin: "0.35rem 0 0" }} title="Operational authority inputs">
                  L6 / ops: {data.sovereignty.operational_authority_line || "—"}
                </p>
                <p className="muted small" style={{ margin: "0.25rem 0 0" }} title="Ragstone ledger">
                  Ragstone: {data.sovereignty.financial_sovereignty_line || "—"}
                </p>
                <p className="muted small" style={{ margin: "0.25rem 0 0" }} title="Physical baseline">
                  Titan: {data.sovereignty.physical_baseline_line || "—"}
                </p>
              </div>
            ) : null}
            {day === localDateISO() && (
              <div className="cockpit-card cockpit-card--compact vanguard-signals-card">
                {data.air_gap_active ? (
                  <p className="muted small" style={{ margin: 0 }} title="Advisory only — no OS lockout">
                    Air gap (deep work): active
                    {data.air_gap_extension_suggested ? " · extend suggested (sleep short)" : ""}
                  </p>
                ) : null}
                {data.midday_shield_active ? (
                  <p className="muted small" style={{ margin: "0.25rem 0 0" }}>
                    Midday shield: active
                  </p>
                ) : null}
                {data.identity_alignment_window_active ? (
                  <p className="muted small" style={{ margin: "0.25rem 0 0" }}>
                    Identity alignment window: reconcile Today with purpose
                  </p>
                ) : null}
                <p className="muted small" style={{ margin: "0.35rem 0 0" }} title="Todoist Inbox">
                  Inbox open: {data.todoist_inbox_open_count ?? 0}
                  <label style={{ marginLeft: "0.75rem", display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                    <input
                      type="checkbox"
                      checked={Boolean(data.inbox_slaughter_gate_ok)}
                      disabled={vanguardDayBusy}
                      onChange={(e) => void handleInboxGate(e.target.checked)}
                    />
                    Inbox clear (gate)
                  </label>
                </p>
                {data.dead_bug_alerts && data.dead_bug_alerts.length > 0 ? (
                  <p className="muted small" style={{ margin: "0.35rem 0 0" }} title="Vanguard Priority stale">
                    Dead bug:{" "}
                    {data.dead_bug_alerts
                      .map((a) => `${a.project_name || "?"} (${a.hours_since_activity}h)`)
                      .join(" · ")}
                  </p>
                ) : null}
                {data.firefighting_signals && data.firefighting_signals.length > 0 ? (
                  <p className="muted small" style={{ margin: "0.35rem 0 0" }}>
                    Firefighting signals: {data.firefighting_signals.length} (Tools → Firewall audit)
                  </p>
                ) : null}
                <p className="muted small" style={{ margin: "0.35rem 0 0" }}>
                  Favor strike: {data.favor_strike_days_clean_7d ?? 0}/7 days clean · streak {data.favor_strike_streak_7d ?? 0}
                  {data.commitments_partner_overdue ? " · partner overdue" : ""}
                </p>
                <label className="muted small" style={{ margin: "0.35rem 0 0", display: "flex", alignItems: "center", gap: "0.35rem" }}>
                  <input
                    type="checkbox"
                    checked={Boolean(data.zero_utility_labor_today)}
                    disabled={vanguardDayBusy}
                    onChange={(e) => void handleZeroUtilityLabor(e.target.checked)}
                  />
                  Zero utility labor (today)
                </label>
                {(data.evening_wins_count || data.evening_leaks_count) ? (
                  <p className="muted small" style={{ margin: "0.25rem 0 0" }} title="Evening ops ledger">
                    Evening: {data.evening_wins_count ?? 0} wins · {data.evening_leaks_count ?? 0} leaks
                  </p>
                ) : null}
              </div>
            )}
            <div className="execution-band">
            <header className="execution-band-head execution-band-head--split">
              <div>
                <div className="kicker">Today</div>
                <h1 className="runway-title">Execution</h1>
              </div>
              {data.integrity_habit_snapshot ? (
                <IntegrityHabitSparkline sessions={data.integrity_habit_snapshot.posture_sessions_7d} />
              ) : null}
            </header>

            <div className="purpose-pillar-wrap" style={{ marginBottom: "0.85rem" }}>
              <div className={`purpose-pillar${purposeEditing ? " purpose-pillar--editing" : ""}`}>
                <div className="purpose-pillar__head">
                  <div className="card-kicker">Life purpose</div>
                  {!purposeEditing ? (
                    <button
                      type="button"
                      className="purpose-pillar__edit"
                      onClick={() => {
                        setPurposeDraft(purposeText);
                        setPurposeEditing(true);
                      }}
                    >
                      Edit
                    </button>
                  ) : null}
                </div>
                {!purposeEditing ? (
                  <p className="purpose-pillar__inscription">{purposeText.trim() || "No purpose set."}</p>
                ) : (
                  <>
                    <textarea
                      className="purpose-pillar__textarea settings-input tall"
                      value={purposeDraft}
                      onChange={(e) => setPurposeDraft(e.target.value)}
                      rows={5}
                      disabled={settingsBusy}
                    />
                    <div className="purpose-pillar__actions">
                      <button
                        type="button"
                        className="btn-trio sm"
                        disabled={settingsBusy}
                        onClick={() => setPurposeEditing(false)}
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        className="btn-trio sm primary"
                        disabled={settingsBusy}
                        onClick={() => void handleSavePurposePillar()}
                      >
                        Save
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>

            {data.work_calendar_advisory && hasWorkCalendarIntel(data.work_calendar_advisory) ? (
              <TacticalBriefCard wca={data.work_calendar_advisory} clockNow={timelineNow} />
            ) : null}

            <section className="panel runway-panel">
              <div className="panel-head runway-panel-head">
                <div>
                  <div className="kicker">Runway</div>
                  <h2 className="type-playfair-section">Golden path</h2>
                </div>
              </div>
              {data.golden_path_timeline && data.golden_path_timeline.length > 0 ? (
                <div className="cockpit-card cockpit-card--compact golden-path-timeline-card">
                  <div className="card-kicker">Day timeline</div>
                  <p className="muted small" style={{ marginTop: "0.25rem" }}>
                    Full-day runway from merged landscape (after overlap choices). Expand a row for channel, badges, and
                    nudges.
                  </p>
                  <ul className="golden-path-timeline">
                    {data.golden_path_timeline.map((row) => {
                      const phase = classifyTimelineRow(timelineNow, day, row.start_iso, row.end_iso);
                      const itemClass = `golden-path-timeline-item golden-path-timeline-item--${phase}`;
                      const summaryAria =
                        phase === "current"
                          ? `${row.title}, current event`
                          : phase === "past"
                            ? `${row.title}, completed`
                            : `${row.title}, upcoming`;
                      return (
                      <li key={row.start_iso + "\t" + row.title} className={itemClass}>
                        <details className="golden-path-timeline-details">
                          <summary className="golden-path-timeline-summary" aria-label={summaryAria}>
                            <span className="golden-path-timeline-gutter" aria-hidden />
                            <span className="golden-path-timeline-main">
                              {phase === "current" ? (
                                <span className="sr-only">Now · </span>
                              ) : null}
                              <span className="golden-path-timeline-time">
                                {new Date(row.start_iso).toLocaleTimeString(undefined, {
                                  hour: "numeric",
                                  minute: "2-digit",
                                })}
                              </span>
                              <span className="golden-path-timeline-title">{row.title}</span>
                              {row.badges?.length ? (
                                <span className="golden-path-timeline-badges">
                                  {row.badges.map((b) => (
                                    <span key={b} className="golden-path-badge">
                                      {b.replace(/_/g, " ")}
                                    </span>
                                  ))}
                                </span>
                              ) : null}
                            </span>
                          </summary>
                          <div className="golden-path-timeline-body">
                            <p className="small muted" style={{ margin: 0 }}>
                              {goldenPathTimelineChannel(row)}
                            </p>
                            {row.expand_hint ? (
                              <p className="small" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                                {row.expand_hint}
                              </p>
                            ) : null}
                          </div>
                        </details>
                      </li>
                      );
                    })}
                  </ul>
                </div>
              ) : (
                <div className="cockpit-card cockpit-card--compact golden-path-timeline-card">
                  <div className="card-kicker">Day timeline</div>
                  <p className="muted small" style={{ marginTop: "0.25rem" }}>
                    No timed rows in the merged landscape for this day yet.
                  </p>
                </div>
              )}
              {data.golden_path_snoozed ? (
                <div className="cockpit-card cockpit-card--compact golden-path-snooze-banner">
                  <p className="small">Golden path suggestions snoozed.</p>
                  <button
                    type="button"
                    className="btn-trio sm"
                    disabled={goldenActionBusy !== null}
                    onClick={() => void handleClearGoldenSnooze()}
                  >
                    Clear snooze
                  </button>
                </div>
              ) : null}
              {(data.golden_path_proposals || []).some((p) => p.status === "pending") ? (
                <details
                  className="golden-path-proposals-details"
                  open={(data.golden_path_proposals || []).filter((p) => p.status === "pending").length > 0}
                >
                  <summary className="golden-path-proposals-summary">
                    Pending suggestions (
                    {(data.golden_path_proposals || []).filter((p) => p.status === "pending").length})
                  </summary>
                  <div className="cockpit-card golden-path-proposals">
                    <p className="muted small" style={{ marginTop: "0.25rem" }}>
                      Rule-based v1 — calendar data is unchanged. <strong>Approve</strong> / <strong>Dismiss</strong> /{" "}
                      <strong>Snooze</strong> only control this reminder list (acknowledge, hide, or pause nags).
                      Overlap truth is under <strong>Daily landscape</strong> → <strong>Overlapping meetings</strong>.
                    </p>
                    <ul className="golden-path-proposal-list">
                      {(data.golden_path_proposals || [])
                        .filter((p) => p.status === "pending")
                        .map((p) => (
                          <li key={p.id} className="golden-path-proposal-item">
                            <div className="golden-path-proposal-head">{p.headline}</div>
                            <p className="muted small">{p.detail}</p>
                            {p.id === "calendar_overlaps" ? (
                              <button
                                type="button"
                                className="btn-trio sm"
                                style={{ marginTop: "0.35rem" }}
                                onClick={() => setActiveSection("landscape")}
                              >
                                Resolve overlapping meetings → Daily landscape
                              </button>
                            ) : null}
                            <div className="golden-path-proposal-actions">
                              <button
                                type="button"
                                className="btn-trio sm primary"
                                disabled={goldenActionBusy !== null}
                                title="Log that you accept this nudge for your own tracking"
                                onClick={() => void handleGoldenPathProposal(p.id, "approve")}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="btn-trio sm"
                                disabled={goldenActionBusy !== null}
                                title="Hide this suggestion until conditions change"
                                onClick={() => void handleGoldenPathProposal(p.id, "dismiss")}
                              >
                                Dismiss
                              </button>
                              <button
                                type="button"
                                className="btn-trio sm"
                                disabled={goldenActionBusy !== null}
                                title="Pause all pending suggestions for 24 hours"
                                onClick={() => void handleGoldenPathProposal(p.id, "snooze")}
                              >
                                Snooze
                              </button>
                            </div>
                          </li>
                        ))}
                    </ul>
                  </div>
                </details>
              ) : null}
              {data.personal_calendar_status === "not_configured" && (
                <div className="cockpit-card cockpit-card--warn setup-card">
                  <div className="card-kicker">Personal calendar</div>
                  <p className="card-body">
                    Not connected. Add one of these to the API environment (e.g. project <code>.env</code>), then
                    restart the server:
                  </p>
                  <ul className="setup-list">
                    <li>
                      <code>APPLE_CALENDAR_ICS_URL</code> — iCloud/Apple public or secret ICS URL
                    </li>
                    <li>
                      <code>ICLOUD_APPLE_ID</code> + <code>ICLOUD_APP_PASSWORD</code> — app-specific password; optional{" "}
                      <code>ICLOUD_CALENDAR_NAME</code>
                    </li>
                  </ul>
                  <p className="muted small">
                    Same variables as Streamlit; load via project <code>.env</code> (see <code>docs/COCKPIT_DEV.md</code>
                    ).
                  </p>
                </div>
              )}
              {data.personal_calendar_status === "error" && data.personal_calendar_note && (
                <div className="cockpit-card cockpit-card--warn">
                  <div className="card-kicker">Personal calendar</div>
                  <p className="card-body small">{data.personal_calendar_note}</p>
                </div>
              )}

              <div className="integrity-timeline">
                {(() => {
                  const tp = data.runway.tomorrow_preview;
                  const postMorning = isPostMorningRunway(timelineNow, day, data.runway.anchor_start_iso);
                  const todayRecon = day === localDateISO();
                  const showPmLayout = todayRecon && postMorning;
                  const todaySlice = {
                    integrity_wake_iso: data.runway.integrity_wake_iso,
                    tactical_integrity_wake_iso: data.runway.tactical_integrity_wake_iso,
                    anchor_start_iso: data.runway.anchor_start_iso,
                    anchor_title: data.runway.anchor_title,
                  };
                  const tomorrowSlice = tp
                    ? {
                        integrity_wake_iso: tp.integrity_wake_iso,
                        tactical_integrity_wake_iso: tp.tactical_integrity_wake_iso,
                        anchor_start_iso: tp.anchor_start_iso,
                        anchor_title: tp.anchor_title,
                      }
                    : {
                        integrity_wake_iso: null,
                        tactical_integrity_wake_iso: null,
                        anchor_start_iso: null,
                        anchor_title: null,
                      };
                  return (
                    <>
                      {showPmLayout ? (
                        <div className="integrity-timeline-row">
                          <div className="integrity-timeline-gutter">
                            <span className="integrity-timeline-icon">
                              <IntegrityRailIcon kind="protocol" />
                            </span>
                          </div>
                          <div className="integrity-timeline-body">
                            <div className="cockpit-card cockpit-card--compact tomorrow-runway-strip">
                              <div className="card-kicker">Tomorrow at a glance</div>
                              {tp ? (
                                <>
                                  <p className="small" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                                    <strong>{tp.date}</strong> · Wake{" "}
                                    {tp.integrity_wake_iso ? formatClock(tp.integrity_wake_iso) : "—"}
                                    {tp.anchor_start_iso
                                      ? ` · First anchor ${formatClock(tp.anchor_start_iso)}${
                                          tp.anchor_title ? ` (${tp.anchor_title})` : ""
                                        }`
                                      : ""}
                                  </p>
                                  {(tp.prep_shortfall_labels || []).length ? (
                                    <p className="muted small" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                                      {(tp.prep_shortfall_labels || []).join(" · ")}
                                    </p>
                                  ) : null}
                                </>
                              ) : (
                                <p className="muted small" style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                                  Tomorrow preview unavailable (calendars or server). Monolith below uses best-effort
                                  placeholders.
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      ) : null}
                      {!showPmLayout ? (
                        <div className="integrity-timeline-row">
                          <div className="integrity-timeline-gutter">
                            <span className="integrity-timeline-icon">
                              <IntegrityRailIcon kind="protocol" />
                            </span>
                          </div>
                          <div className="integrity-timeline-body">
                            <MonolithRunwayCard
                              kicker="Prep + first anchor"
                              slice={todaySlice}
                              monolithPrepBarPct={monolithPrepBarPct}
                            />
                          </div>
                        </div>
                      ) : null}

                      {data.runway.runway_conflict && data.runway.conflict_summary ? (
                        <div className="integrity-timeline-row integrity-timeline-row--conflict">
                          <div className="integrity-timeline-gutter">
                            <span className="integrity-timeline-icon">
                              <IntegrityRailIcon kind="conflict" />
                            </span>
                          </div>
                          <div className="integrity-timeline-body">
                            <div className="cockpit-card cockpit-card--accent">
                              <div className="card-kicker kicker--signal">Conflict</div>
                              <p className="card-body">{data.runway.conflict_summary}</p>
                              <p className="muted small">
                                Fix: <strong>Tools</strong> → Runway override, or adjust default wake where you set it
                                (Streamlit / settings).
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : null}

                      {showPmLayout ? (
                        <div className="integrity-timeline-row">
                          <div className="integrity-timeline-gutter">
                            <span className="integrity-timeline-icon">
                              <IntegrityRailIcon kind="protocol" />
                            </span>
                          </div>
                          <div className="integrity-timeline-body">
                            <MonolithRunwayCard
                              kicker={
                                tp ? "Tomorrow · prep + first anchor" : "Tomorrow runway (preview unavailable)"
                              }
                              slice={tomorrowSlice}
                              monolithPrepBarPct={monolithPrepBarPct}
                            />
                          </div>
                        </div>
                      ) : null}
                    </>
                  );
                })()}
              </div>
            </section>

            <section className={`panel trio-panel${hideAuxNav ? " trio-panel--focus-shell" : ""}`}>
              <div className="panel-head">
                <div>
                  <div className="kicker">Todoist</div>
                  <h2 className="trio-panel-title-row">
                    Power Trio
                    {trio?.recon_day ? (
                      <span className="muted small trio-recon-pill">Recon · {trio.recon_day}</span>
                    ) : null}
                  </h2>
                </div>
                <div className="trio-actions">
                  <button
                    type="button"
                    className="btn-trio"
                    disabled={trioBusy || (tdStatus ? !tdStatus.todoist_configured : false)}
                    onClick={() => void handleSync()}
                  >
                    Pull tasks
                  </button>
                  <button
                    type="button"
                    className="btn-trio primary"
                    disabled={trioBusy}
                    onClick={() => void handleRank()}
                  >
                    Refocus (rank)
                  </button>
                </div>
              </div>
              {tdStatus && !tdStatus.todoist_configured && (
                <p className="muted small">Todoist not configured.</p>
              )}
              {trioErr && <div className="panel warn subtle">{trioErr}</div>}
              {trio && trio.merge_note && <p className="muted small">{trio.merge_note}</p>}
              {trio && trio.rank_warning && !trioErr && <p className="muted small">{trio.rank_warning}</p>}
              {!trio?.slots?.length && (
                <p className="muted small">Pull tasks, then Refocus.</p>
              )}
              <div className="trio-stack">
                {(trio?.slots || []).map((s) => (
                  <div
                    key={s.task_id}
                    className={`trio-card trio-card--stacked${s.slot === 0 ? " trio-card--combat-emphasis" : ""}`}
                  >
                    <div className="trio-card-head">
                      <TrioSlotGlyph slot={s.slot} />
                      <div className="trio-card-head-text">
                        <div className="trio-slot-label">{s.label}</div>
                        <div className="trio-title">{s.title}</div>
                        {s.project_name ? <div className="trio-proj">{s.project_name}</div> : null}
                      </div>
                    </div>
                    {s.slot === 0 &&
                    (s.tactical_steps || []).some((x) => String(x || "").trim()) &&
                    tdStatus?.gemini_configured ? (
                      <details className="combat-tactical-subview">
                        <summary>Immediate actions (Combat)</summary>
                        <p className="muted small" style={{ marginTop: "0.35rem" }}>
                          Stricter EA-style first moves for slot #1. Refresh on <strong>Refocus (rank)</strong>.
                        </p>
                      </details>
                    ) : null}
                    {(s.tactical_steps || []).some((x) => String(x || "").trim()) ? (
                      <div className="trio-tactical-steps">
                        <div className="trio-tactical-steps__label">Tactical steps</div>
                        <ul className="trio-tactical-steps__list">
                          {(s.tactical_steps || [])
                            .map((step) => String(step || "").trim())
                            .filter(Boolean)
                            .slice(0, 3)
                            .map((step, i) => (
                              <li key={`${s.task_id}-step-${i}`}>{step}</li>
                            ))}
                        </ul>
                      </div>
                    ) : tdStatus && !tdStatus.gemini_configured ? (
                      <p className="muted small trio-tactical-steps__hint">Configure Gemini, then Refocus to generate tactical steps.</p>
                    ) : trio?.last_rank_iso ? (
                      <p className="muted small trio-tactical-steps__hint">Tactical steps refresh on Refocus (rank).</p>
                    ) : (
                      <p className="muted small trio-tactical-steps__hint">Pull tasks, then Refocus to generate tactical steps.</p>
                    )}
                    <div className="trio-btns">
                      {s.slot === 0 ? (
                        <button
                          type="button"
                          className="btn-trio sm"
                          disabled={trioBusy || forwardReadonly}
                          title={forwardReadonly ? "Available when this day is today." : undefined}
                          onClick={() => void handleAssist(s.task_id, "plan")}
                        >
                          Break it down
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="btn-trio sm"
                          disabled={trioBusy || forwardReadonly}
                          title={forwardReadonly ? "Available when this day is today." : undefined}
                          onClick={() => void handleAssist(s.task_id, "strike")}
                        >
                          Strike
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn-trio sm primary"
                        disabled={trioBusy || forwardReadonly}
                        title={forwardReadonly ? "Available when this day is today." : undefined}
                        onClick={() => void handleComplete(s.task_id, s.slot)}
                      >
                        Executed
                      </button>
                    </div>
                    {assist[s.task_id]?.plan && (
                      <pre className="trio-assist">{assist[s.task_id].plan}</pre>
                    )}
                    {assist[s.task_id]?.strike && (
                      <pre className="trio-assist">{assist[s.task_id].strike}</pre>
                    )}
                  </div>
                ))}
              </div>
            </section>
            </div>

            <section className="panel kill-panel">
              <div className="panel-head">
                <div>
                  <div className="kicker">Focus</div>
                  <h2>Deep work kill zones</h2>
                </div>
                <span className="muted">{data.kill_zones.length} windows</span>
              </div>
              <ScheduleSignalsKillHint
                sig={data.schedule_day_signals ?? defaultScheduleSignals()}
                onOpenLandscape={() => setActiveSection("landscape")}
              />
              <ul className="kill-list kill-stack">
                {data.kill_zones.map((z) => (
                  <li key={z.start_iso} className="cockpit-card cockpit-card--compact">
                    {new Date(z.start_iso).toLocaleTimeString(undefined, {
                      hour: "numeric",
                      minute: "2-digit",
                    })}{" "}
                    –{" "}
                    {new Date(z.end_iso).toLocaleTimeString(undefined, {
                      hour: "numeric",
                      minute: "2-digit",
                    })}
                  </li>
                ))}
              </ul>
              {!data.kill_zones.length && <p className="muted small">No qualifying gaps today.</p>}
            </section>
          </>
        )}

        {!loading && data && activeSection === "landscape" && (
          <section className="panel">
            <div className="panel-head">
              <h2 className="type-playfair-section">Daily landscape</h2>
              <span className="muted">{mergedLandscape.length} events</span>
            </div>
            <ScheduleSignalsLandscapePanel
              key={day}
              day={day}
              sig={data.schedule_day_signals ?? defaultScheduleSignals()}
              tradeoffAnswers={data.schedule_tradeoff_answers ?? EMPTY_TRADEOFF_ANSWERS}
              onTradeoffsSaved={() => void queryClient.invalidateQueries({ queryKey: ["cockpit"] })}
            />
            {(data.golden_path_proposals || []).some((p) => p.status === "approved") ? (
              <div className="cockpit-card cockpit-card--compact golden-path-approved" style={{ marginBottom: "0.75rem" }}>
                <div className="card-kicker">Accepted moves</div>
                <ul className="small">
                  {(data.golden_path_proposals || [])
                    .filter((p) => p.status === "approved")
                    .map((p) => (
                      <li key={p.id}>{p.headline}</li>
                    ))}
                </ul>
              </div>
            ) : null}
            <ul className="landscape-list">
              {mergedLandscape.map((ev) => {
                const meta = landscapeRowMeta(ev);
                return (
                  <li key={`${ev.start_iso}\t${ev.title}\t${ev.source_kind ?? ev.source}`}>
                    <span className="landscape-time">
                      {new Date(ev.start_iso).toLocaleTimeString(undefined, {
                        hour: "numeric",
                        minute: "2-digit",
                      })}
                    </span>
                    <div className="landscape-tag-col">
                      <span className={`tag ${meta.badgeClass}`}>{meta.primary}</span>
                      {meta.secondary ? (
                        <span className="landscape-channel">{meta.secondary}</span>
                      ) : null}
                    </div>
                    <span className="landscape-title">{ev.title}</span>
                  </li>
                );
              })}
            </ul>
            {!mergedLandscape.length && (
              <p className="muted small">No timed events merged for this day (connect calendars or add events).</p>
            )}
          </section>
        )}

        {!loading && data && activeSection === "tools" && (
          <>
            <section className="panel tools-google-panel">
              <div className="panel-head">
                <div>
                  <div className="kicker">Wardrobe</div>
                  <h2>Week-ahead wardrobe pass</h2>
                </div>
              </div>
              <p className="muted small">
                Suit vs sharp-casual for one week from Mon–Sun calendar rows when connected. Setup:{" "}
                <code>docs/COCKPIT_DEV.md</code>
              </p>
              <div className="meta-row meta-row-wrap" style={{ marginTop: "0.45rem", alignItems: "center" }}>
                <label className="muted small" style={{ display: "flex", flexWrap: "wrap", gap: "0.35rem", alignItems: "center" }}>
                  Week (Monday)
                  <input
                    type="date"
                    className="btn-trio sm"
                    style={{ padding: "0.25rem 0.4rem", fontSize: "0.78rem" }}
                    value={titanWeekStart}
                    onChange={(e) => setTitanWeekStart(mondayOfCalendarWeekContaining(e.target.value))}
                    title="Pick any day in the week; snaps to that week’s Monday."
                  />
                </label>
              </div>
              {titanPrepErr ? <div className="panel warn subtle">{titanPrepErr}</div> : null}
              <div className="trio-actions" style={{ marginTop: "0.35rem" }}>
                <button
                  type="button"
                  className="btn-trio primary"
                  disabled={titanPrepBusy}
                  onClick={() => void handleTitanPrepGenerate()}
                >
                  {titanPrepBusy ? "Generating…" : "Generate / refresh"}
                </button>
              </div>
              {titanPrep?.text ? (
                <div className="cockpit-card cockpit-card--compact" style={{ marginTop: "0.75rem" }}>
                  <div className="card-kicker">Week of {titanPrep.week_start}</div>
                  {titanPrep.grounding_event_count != null ? (
                    <p className="muted small" style={{ marginTop: "0.25rem" }}>
                      {titanPrep.grounding_event_count > 0
                        ? `Grounded from ${titanPrep.grounding_event_count} calendar rows (Mon–Sun).`
                        : "No calendar rows for that week when this was generated."}
                    </p>
                  ) : null}
                  <pre className="titan-prep-body">{titanPrep.text}</pre>
                  {titanPrep.generated_at ? (
                    <p className="muted small" style={{ marginTop: "0.35rem" }}>
                      Saved {new Date(titanPrep.generated_at).toLocaleString()}
                    </p>
                  ) : null}
                </div>
              ) : (
                <p className="muted small" style={{ marginTop: "0.5rem" }}>
                  No saved prep for this week yet — generate when ready.
                </p>
              )}
            </section>

            <section className="panel tools-google-panel">
              <div className="panel-head">
                <div>
                  <div className="kicker">Integrations</div>
                  <h2>Google Calendar</h2>
                </div>
              </div>
              <div className="meta-row meta-row-wrap tools-google-meta">
                <span className={data.google_calendar_connected ? "ok" : "warn"}>
                  Google: {data.google_calendar_connected ? "connected" : "not connected"}
                </span>
                {gAuth && !gAuth.credentials_file_present && (
                  <span className="muted small">{gAuth.message}</span>
                )}
                {!data.google_calendar_connected && (
                  <a className="btn-trio sm linkish" href="/api/auth/google/start">
                    Connect Google Calendar
                  </a>
                )}
              </div>
            </section>

            <section className="panel tools-google-panel">
              <div className="panel-head">
                <div>
                  <div className="kicker">Vanguard</div>
                  <h2>LLM triage & audits</h2>
                </div>
              </div>
              <p className="muted small">On-demand Gemini. Requires API key on server. Setup: docs/COCKPIT_DEV.md</p>
              <label className="settings-field" style={{ marginTop: "0.5rem" }}>
                Paste (Windshield / Utility alarm)
                <textarea
                  className="settings-input tall"
                  rows={3}
                  value={vanguardPaste}
                  onChange={(e) => setVanguardPaste(e.target.value)}
                  placeholder="Slack or email snippet…"
                />
              </label>
              <div className="meta-row meta-row-wrap" style={{ marginTop: "0.35rem" }}>
                <label className="muted small">
                  <input
                    type="radio"
                    name="vanguardMode"
                    checked={vanguardTriageMode === "windshield"}
                    onChange={() => setVanguardTriageMode("windshield")}
                  />{" "}
                  Windshield
                </label>
                <label className="muted small">
                  <input
                    type="radio"
                    name="vanguardMode"
                    checked={vanguardTriageMode === "utility_alarm"}
                    onChange={() => setVanguardTriageMode("utility_alarm")}
                  />{" "}
                  Utility alarm
                </label>
                <button
                  type="button"
                  className="btn-trio sm primary"
                  disabled={vanguardTriageBusy || !vanguardPaste.trim()}
                  onClick={() => void handleVanguardTriage()}
                >
                  {vanguardTriageBusy ? "…" : "Classify"}
                </button>
              </div>
              {vanguardTriageResult ? <p className="muted small" style={{ marginTop: "0.35rem" }}>{vanguardTriageResult}</p> : null}

              <div style={{ marginTop: "0.75rem" }}>
                <div className="card-kicker">Opportunity cost</div>
                <input
                  className="settings-input"
                  style={{ marginTop: "0.25rem" }}
                  value={vanguardOppTitle}
                  onChange={(e) => setVanguardOppTitle(e.target.value)}
                  placeholder="Proposed task title"
                />
                <textarea
                  className="settings-input tall"
                  style={{ marginTop: "0.35rem" }}
                  rows={2}
                  value={vanguardOppNotes}
                  onChange={(e) => setVanguardOppNotes(e.target.value)}
                  placeholder="Notes (optional)"
                />
                <button
                  type="button"
                  className="btn-trio sm primary"
                  style={{ marginTop: "0.35rem" }}
                  disabled={vanguardOppBusy || !vanguardOppTitle.trim()}
                  onClick={() => void handleVanguardOpp()}
                >
                  {vanguardOppBusy ? "…" : "Challenge"}
                </button>
                {vanguardOppResult ? <p className="muted small" style={{ marginTop: "0.35rem" }}>{vanguardOppResult}</p> : null}
              </div>

              <div style={{ marginTop: "0.75rem" }}>
                <div className="card-kicker">Past-in-the-past</div>
                <textarea
                  className="settings-input tall"
                  style={{ marginTop: "0.25rem" }}
                  rows={3}
                  value={vanguardPipText}
                  onChange={(e) => setVanguardPipText(e.target.value)}
                />
                <button
                  type="button"
                  className="btn-trio sm primary"
                  style={{ marginTop: "0.35rem" }}
                  disabled={vanguardPipBusy || !vanguardPipText.trim()}
                  onClick={() => void handleVanguardPip()}
                >
                  {vanguardPipBusy ? "…" : "Reframe"}
                </button>
                {vanguardPipResult ? <p className="muted small" style={{ marginTop: "0.35rem" }}>{vanguardPipResult}</p> : null}
              </div>

              <div style={{ marginTop: "0.75rem" }}>
                <div className="card-kicker">13% calendar leanness</div>
                <button
                  type="button"
                  className="btn-trio sm primary"
                  disabled={vanguardLeanBusy || !mergedLandscape.length}
                  title={!mergedLandscape.length ? "No landscape rows for this recon day" : undefined}
                  onClick={() => void handleVanguardLean()}
                >
                  {vanguardLeanBusy ? "…" : "Analyze merged landscape"}
                </button>
                {vanguardLeanResult ? <p className="muted small" style={{ marginTop: "0.35rem" }}>{vanguardLeanResult}</p> : null}
              </div>

              <div style={{ marginTop: "0.75rem" }}>
                <div className="card-kicker">Firewall audit (from cockpit signals)</div>
                <button
                  type="button"
                  className="btn-trio sm primary"
                  disabled={vanguardFwBusy || !(data.firefighting_signals && data.firefighting_signals.length)}
                  onClick={() => void handleVanguardFirewall()}
                >
                  {vanguardFwBusy ? "…" : "Summarize"}
                </button>
                {vanguardFwResult ? <p className="muted small" style={{ marginTop: "0.35rem" }}>{vanguardFwResult}</p> : null}
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <div className="kicker">Advisory</div>
                  <h2>Calendar screenshot (Gemini)</h2>
                </div>
              </div>
              <p className="muted small">
                Upload a screenshot of your <strong>work</strong> calendar for the selected day. Gemini extracts
                meetings, saves them into <strong>Daily landscape</strong> (merged with Google/Apple API rows), and
                adds time-use coaching below. Requires <code>GEMINI_API_KEY</code>.
              </p>
              {data.work_calendar_advisory && hasWorkCalendarIntel(data.work_calendar_advisory) ? (
                <div style={{ marginTop: "0.5rem" }}>
                  <TacticalBriefCard wca={data.work_calendar_advisory} clockNow={timelineNow} />
                </div>
              ) : null}
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setAdvisoryFiles(e.target.files)}
              />
              <div className="trio-actions" style={{ marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="btn-trio primary"
                  disabled={advisoryBusy || !advisoryFiles?.length}
                  onClick={() => void handleAdvisoryAnalyze()}
                >
                  Analyze
                </button>
              </div>
              {advisoryErr && <div className="panel warn subtle">{advisoryErr}</div>}
              {advisoryWarning && (
                <div className="panel warn subtle" style={{ marginTop: "0.5rem" }}>
                  {advisoryWarning}
                </div>
              )}
              {advisoryResult && (
                <pre className="runway-md" style={{ marginTop: "0.5rem" }}>
                  {JSON.stringify(advisoryResult, null, 2)}
                </pre>
              )}
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <div className="kicker">Manual</div>
                  <h2>Runway hard anchor override</h2>
                </div>
              </div>
              <p className="muted small">
                Optional: force the integrity anchor for this recon day (stored in{" "}
                <code>runway_overrides.json</code>). Pick a landscape row or enter ISO start time + title.
              </p>
              <details className="glossary">
                <summary>What is a runway override?</summary>
                <p>
                  A manual lock so a specific start time and title wins when the system picks the wrong meeting as the
                  hard anchor. Use it when automation disagrees with what you consider the day&apos;s binding
                  commitment.
                </p>
              </details>
              <div className="settings-grid">
                <label className="settings-field">
                  Fill from landscape
                  <select
                    className="settings-input"
                    value={runwayFillKey}
                    disabled={settingsBusy}
                    onChange={(e) => {
                      const v = e.target.value;
                      setRunwayFillKey(v);
                      const ev = mergedLandscape.find(
                        (x) => `${x.start_iso}\t${x.title}` === v,
                      );
                      if (ev) {
                        setRunwayStart(ev.start_iso);
                        setRunwayTitle(ev.title);
                        setRunwaySource(ev.source === "personal" ? "personal" : "google");
                      }
                    }}
                  >
                    <option value="">— select —</option>
                    {mergedLandscape.map((ev) => {
                      const hint = landscapeRowHint(ev);
                      return (
                        <option key={`${ev.start_iso}\t${ev.title}\t${ev.source_kind ?? ev.source}`} value={`${ev.start_iso}\t${ev.title}`}>
                          {new Date(ev.start_iso).toLocaleTimeString(undefined, {
                            hour: "numeric",
                            minute: "2-digit",
                          })}{" "}
                          · {ev.title} ({hint})
                        </option>
                      );
                    })}
                  </select>
                </label>
                <label className="settings-field">
                  Start (ISO)
                  <input
                    className="settings-input"
                    value={runwayStart}
                    disabled={settingsBusy}
                    onChange={(e) => setRunwayStart(e.target.value)}
                    placeholder="2026-04-11T08:00:00-05:00"
                  />
                </label>
                <label className="settings-field">
                  Title
                  <input
                    className="settings-input"
                    value={runwayTitle}
                    disabled={settingsBusy}
                    onChange={(e) => setRunwayTitle(e.target.value)}
                  />
                </label>
                <label className="settings-field">
                  Source
                  <select
                    className="settings-input"
                    value={runwaySource}
                    disabled={settingsBusy}
                    onChange={(e) => setRunwaySource(e.target.value as "google" | "personal")}
                  >
                    <option value="google">google</option>
                    <option value="personal">personal</option>
                  </select>
                </label>
              </div>
              <div className="trio-actions" style={{ marginTop: "0.65rem" }}>
                <button
                  type="button"
                  className="btn-trio primary"
                  disabled={settingsBusy || !runwayStart.trim() || !runwayTitle.trim()}
                  onClick={() => void handleSaveRunway()}
                >
                  Save override
                </button>
                <button
                  type="button"
                  className="btn-trio"
                  disabled={settingsBusy}
                  onClick={() => void handleClearRunway()}
                >
                  Clear
                </button>
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <div>
                  <div className="kicker">Identity</div>
                  <h2>Purpose &amp; protocol</h2>
                </div>
              </div>
              <p className="muted small">
                Purpose feeds Todoist ranking; CHIEF_* overrides merge with environment (file:{" "}
                <code>cockpit_protocol_settings.json</code>).
              </p>
              <label className="settings-field block">
                Life purpose / Titan identity
                <textarea
                  className="settings-input tall"
                  value={purposeText}
                  disabled={settingsBusy}
                  onChange={(e) => setPurposeText(e.target.value)}
                  rows={4}
                />
              </label>
              <div className="trio-actions" style={{ marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="btn-trio primary"
                  disabled={settingsBusy}
                  onClick={() => void handleSavePurpose()}
                >
                  Save purpose
                </button>
              </div>
              {protocol && (
                <>
                  <div className="protocol-resolved muted small" style={{ marginTop: "0.75rem" }}>
                    Resolved: markers &quot;{protocol.resolved_chief_hard_markers}&quot; · posture{" "}
                    {protocol.resolved_posture_minutes}m · neck {protocol.resolved_neck_minutes}m · ops{" "}
                    {protocol.resolved_ops_minutes}m
                  </div>
                  <label className="settings-field block">
                    CHIEF_HARD_MARKERS (comma substrings, optional override)
                    <input
                      className="settings-input"
                      value={protocol.chief_hard_markers ?? ""}
                      disabled={settingsBusy}
                      onChange={(e) =>
                        setProtocol({ ...protocol, chief_hard_markers: e.target.value || null })
                      }
                      placeholder="(use env if empty)"
                    />
                  </label>
                  <div className="settings-grid trio-cols">
                    <label className="settings-field">
                      Posture min
                      <input
                        type="number"
                        className="settings-input"
                        value={protocol.chief_posture_minutes ?? ""}
                        disabled={settingsBusy}
                        onChange={(e) => {
                          const v = e.target.value;
                          setProtocol({
                            ...protocol,
                            chief_posture_minutes: v === "" ? null : Number(v),
                          });
                        }}
                      />
                    </label>
                    <label className="settings-field">
                      Neck min
                      <input
                        type="number"
                        className="settings-input"
                        value={protocol.chief_neck_minutes ?? ""}
                        disabled={settingsBusy}
                        onChange={(e) => {
                          const v = e.target.value;
                          setProtocol({
                            ...protocol,
                            chief_neck_minutes: v === "" ? null : Number(v),
                          });
                        }}
                      />
                    </label>
                    <label className="settings-field">
                      Ops min
                      <input
                        type="number"
                        className="settings-input"
                        value={protocol.chief_ops_minutes ?? ""}
                        disabled={settingsBusy}
                        onChange={(e) => {
                          const v = e.target.value;
                          setProtocol({
                            ...protocol,
                            chief_ops_minutes: v === "" ? null : Number(v),
                          });
                        }}
                      />
                    </label>
                  </div>
                  <div className="trio-actions" style={{ marginTop: "0.5rem" }}>
                    <button
                      type="button"
                      className="btn-trio primary"
                      disabled={settingsBusy}
                      onClick={() => void handleSaveProtocol()}
                    >
                      Save protocol overrides
                    </button>
                  </div>
                </>
              )}
            </section>
          </>
        )}

        {!loading &&
          data &&
          data.personal_calendar_status === "ok" &&
          Boolean(data.personal_calendar_note?.trim()) && (
            <p className="muted small cal-footnote">{data.personal_calendar_note}</p>
          )}
        </div>
      </main>
    </div>
  );
}
