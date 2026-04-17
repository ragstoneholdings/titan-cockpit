# Schedule & conflict intake — Ryan

Persistent reference for cockpit / daily landscape / kill zones / optimization work.  
**Last updated:** intake capture + meeting-load correction (5+ h threshold).

---

## Context

- **Time zone:** CST (America/Chicago).
- **Locations:** Work from **home Monday and Friday** (Georgetown, TX area). **Tuesday–Thursday** at **company office** (downtown Austin, TX).
- **Optimization exception:** Default is office Tue–Thu and home Mon/Fri; **as an exception**, swapping a Monday or Friday to office (or an office day to home) is allowed if it clearly improves the schedule.
- **Calendars:**
  - **Primary personal — Apple / CalDAV** (`srragsdale@me.com`): chores, personal appointments, gym, long-standing routines, shared events with husband, bills/finance.
  - **Secondary personal — Google** (`ryanragsdale513513@google.com`): houses habits/routines; Gemini has directed adds toward the primary personal calendar in the past — treat as **secondary** to Apple for truth, but **do not ignore**.
  - **Work:** No direct calendar link (corp firewall). **Work day shape** comes from **screenshot upload / advisory** pipeline.
- **Semantics:** **Commute holds** Tue–Thu for ideal leave / in-car time. **RDW** = “Ryan Doing Work” — blocks for time at work **not** in meetings, usable for execution.

---

## A. Conflict taxonomy (priority)

| Code | Meaning | Applies? |
|------|---------|------------|
| **A1** | Hard overlap (double-book) | Yes — **#1 priority** |
| **A2** | Density / no recovery (too many meetings or too little space between) | Yes — **#3 priority** |
| **A3** | Identity / channel clash | **No** |
| **A4** | Runway / first-commitment tension | Yes |
| **A5** | Kill-zone starvation (not enough contiguous free time for deep work) | Yes — **#2 priority** |
| **A6** | Other | _(none specified)_ |

**Ranked top 3:** **A1** → **A5** → **A2**.

---

## B. Definitions

- **Deep work:** A **60+ minute** block, uninterrupted, full immersion in the work.
- **Leadership time:** Recurring time through the week for overall performance, team health and wellbeing, GM responsibilities — setting and communicating priorities, coaching and developing, unblocking and advancing the right targets (**not** only through 1:1s with Ryan or team meetings).
- **Shallow / admin:** Email, low-cognitive admin tasks.

---

## C. Never move vs flexible

**Almost never move (titles/patterns):** 1:1s with **boss** or **directs**; **GXO Manager Biweekly**; **Hiring Delivery Team Meeting**.

**Willing to compress / shorten / move first:** Open — **use judgment** on what is best to move or shorten.

---

## D. Weekday shape

| Day | Shape | Notes |
|-----|--------|--------|
| Monday | **M2** Mixed | |
| Tuesday | **M1** Meeting-heavy | |
| Wednesday | **M1** Meeting-heavy | |
| Thursday | **M1** Meeting-heavy | |
| Friday | **M3** Deep-first | |
| Saturday | **M4** Light / personal | |
| Sunday | **M4** Light / personal | |

**Shape key:** M1 meeting-heavy · M2 mixed · M3 deep-first · M4 light/personal.

**Protected focus windows:** **Monday morning** and **Friday morning**; sometimes **Friday afternoon**.

---

## E. Numbers & thresholds

- **Minimum contiguous deep-work block to plan for:** **60 minutes**.
- **Minimum gap between back-to-back meetings before feeling “broken”:** **0** (selected — density is still captured via fragmentation / A2 / A5, not a hard minimum gap).
- **“Bad” meeting load:** Roughly **5 hours or more** of meeting-ish time starts to feel bad.

---

## F. Calendar sources & trust

- When **work (screenshot)** and **personal API** disagree for the same slice of time: **show both and flag**; Ryan decides.
- **Personal:** **Apple** is primary personal calendar; **Google** account is secondary (habits / AI-directed adds that relate to personal).

---

## G. Specimen days

### G1 — Broken day (typical Tuesday)

- **Calendar:** Too many meetings early; couldn’t get into a groove. Free time **fragmented** (e.g. ~30 minutes here and there) — only enough for email, pings, restroom — not substance. Often many action items; may work until **~8pm** to catch up.
- **Felt:** Out of control — “cog in the machine” vs leading the machine.

### G2 — Good day (Monday archetype)

- **Calendar:** Deep **strategy / planning** work → communicate to **Pod Leads** in **Monday morning meeting** → **1:1s with pod leads** through the day for message + follow-ups → **personal training ~3pm** → home, shower → a bit more work for comms/email/action items.
- **Felt:** Leading, in control, effective — accomplished at end of day.

### G3 — Acceptable but heavy

- Some **free morning** for morning ops and context for the day → long string of **team meetings / 1:1s** → **commute home ~3pm** → **later meetings ~4–6pm** (e.g. from home).

---

## H. Edge cases

- **Personal appointments during the workday** happen (e.g. medical). Prefer scheduling these **Monday or Friday** (already home, typically slower). May be **away from desk** but **still available on chat/ping** for part of that window (example pattern: ~1:30–3pm away from computer).

---

## I. Kill zones & suggestion framing

**Preference order for suggestions** (reorder / kill to open deep work):

1. **Questions** (“Which of these is least important?”)
2. **Tradeoffs** (“drop or shorten one of: A, B, C”)
3. **Concrete time moves** (“move X to 15:00”)
4. **Minimal nudge** (one line + expand on click)

**Hard no for the product:** _(none listed.)_

---

## J. Product mapping notes (for implementers)

1. **Detect first:** A1 overlaps → A5 contiguous deep-work starvation (vs **60 min** minimum) → A2 fragmentation / density; include **A4** runway tension where runway data exists.
2. **Respect immovable** meetings before proposing kills/moves.
3. **Source disagreement:** dual display + flag; Apple-first for personal merge **policy** but show Google layer when relevant.
4. **Office vs home:** Default Tue–Thu office / Mon–Fri home; optional future “swap day” optimization when it recovers meaningful deep work.
5. **Meeting-ish load:** Flag or score days approaching **≥ 5 h** meeting-ish time as high risk per this intake.
6. **RDW + commute:** Treat as real busy for gap math unless later tagged “soft.”
7. **Implemented (cockpit):** `GET /api/cockpit` returns `schedule_day_signals` from `api/services/schedule_day_signals.py` (overlaps, work-vs-API flags, meeting-ish **union** load excluding RDW/commute-style titles, fragmentation heuristics, 60m deep-slot check, suggestion questions). Kill-zone math includes **work screenshot** busy spans via `extra_busy_spans` on `compute_deep_work_kill_zones`. Optional env: `SCHEDULE_MEETING_LOAD_WARN_MINUTES` (default **300**) or `SCHEDULE_MEETING_LOAD_WARN_HOURS` (default **5**).

---

## References in repo

- Cockpit payload / landscape / signals: `api/services/cockpit_snapshot.py`, `api/services/schedule_day_signals.py`, `api/schemas/cockpit.py`, `web/src/App.tsx`
- Kill zones: `chief_of_staff/planning.py` → `compute_deep_work_kill_zones`

When changing landscape, conflicts, or kill-zone UX, **read this file** and align behavior with the priorities and thresholds above.
