# Titan Cockpit (Option B) — local development

Hosted API, TLS, and **`COCKPIT_API_KEY`**: see [DEPLOY.md](DEPLOY.md).

## Two processes (or one script)

### Option A — One Terminal (recommended on your Mac)

From **Terminal.app** or iTerm (not `pytest` — that only runs tests):

```bash
cd "/Users/ryanragsdale/Projects/Ragstone_Holdings/Command Center Ops"
./scripts/start_titan_cockpit.sh
```

Requires **Node.js** (`npm` on your PATH — install with Homebrew: `brew install node`, or use [nvm](https://github.com/nvm-sh/nvm)). Then open **http://localhost:5173**.

**If “nothing happens” when you run the script:**

- Run it from **Terminal** (not by double‑clicking the file). You should see `>>> Titan Cockpit launcher` and then `Starting API` / `Starting Vite`.
- The first `npm install` can take **1–2 minutes** with no extra output — wait for it.
- If you see `ERROR: Missing .venv`, create the venv: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
- If you see `npm not found`, install Node (see above).
- Paths with spaces are fine **if** you `cd` into the repo with quotes, e.g. `cd "/path/to/Command Center Ops"`.

### Option B — Two terminals

From the repo root (with `.venv` activated or using `.venv/bin/`):

**Terminal 1 — API**

```bash
./scripts/dev_cockpit.sh api
# or: .venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 — Vite**

```bash
./scripts/dev_cockpit.sh web
```

Vite proxies `/api` to `http://127.0.0.1:8000` (see `web/vite.config.ts`).

Alternatively: `make dev-api` and `make dev-web` from the repo root (see [Makefile](Makefile)).

### Option C — Docker (API)

Run the FastAPI app in a container with the repo bind-mounted (same JSON state files on disk as non-Docker). Copy [`.env.example`](../.env.example) to `.env` if you use secrets.

```bash
docker compose up --build
```

Details, port override, and iOS Simulator notes: [docs/DOCKER.md](DOCKER.md).

### Why “nothing happens” with pytest

`python -m pytest tests/` **only runs automated tests**. It does **not** start the web UI. Use the script or two terminals above to launch the app.

## Titan Cockpit architecture (single source of truth)

This replaces scattered “mission” docs with one structural description of **Option B** (FastAPI + React/Vite).

### Brain vs Cockpit

| Layer | Role | Key entrypoints |
|-------|------|-----------------|
| **Backend (Python / FastAPI)** | API orchestration, calendar merge, runway math, Todoist Power Trio, Gemini calls, JSON stores | [`api/main.py`](api/main.py), [`api/services/cockpit_snapshot.py`](api/services/cockpit_snapshot.py), [`api/routers/cockpit.py`](api/routers/cockpit.py), [`api/routers/todoist.py`](api/routers/todoist.py) |
| **Frontend (React / Vite)** | High-contrast execution UI; all reads keyed by **recon `day`** (`?day=YYYY-MM-DD`) | [`web/src/App.tsx`](web/src/App.tsx), [`web/src/api/cockpit.ts`](web/src/api/cockpit.ts) |

**Forward recon:** changing the date in the UI must refresh the whole board (cockpit, landscape, trio, integrity). The API already scopes Power Trio buckets and posture protocol by `day`.

### Core engines (reference only — do not duplicate as separate “build” plans)

1. **Integrity runway** — First hard anchor from calendars (+ optional override); backward-chained wake and prep; **Identity alert** when past integrity wake + 15m without full protocol confirmation (today only). Implemented in [`chief_of_staff/planning.py`](chief_of_staff/planning.py) and [`api/services/cockpit_snapshot.py`](api/services/cockpit_snapshot.py).
2. **Power Trio** — Todoist sync/rank/complete; three slots; tactical steps after rank. [`api/services/power_trio_state.py`](api/services/power_trio_state.py), [`todoist_service.py`](todoist_service.py).
3. **Janitor** — Web: manual `POST /api/todoist/janitor`. Streamlit may run an opportunistic pass ([`command_center_v2.py`](command_center_v2.py)). For **every 4 hours** automation, prefer **cron** or a process manager calling the same HTTP endpoint (keeps one code path); avoid a second hidden janitor unless you accept drift from the API rules.

### Consolidated missions (product phases)

| Theme | What shipped in API/UI | Where to extend |
|-------|-------------------------|-----------------|
| **Integrity visibility + Sentry** | `integrity_consistency_percent` = round(100 × (0.4×7d posture rate + 0.4×7d neck rate + 0.2×(1 if today’s protocol fully confirmed else 0))) from sidebar tail; `integrity_sentry_state`: **CRITICAL** if legacy `identity_alert` or consistency below 50; **WARNING** if 50–79; else **NOMINAL**. UI applies `cockpit-theme-sharp` / `cockpit-theme-muted` and Sentry bands. | [`api/services/cockpit_integrity_coherence.py`](api/services/cockpit_integrity_coherence.py), [`web/src/app.css`](web/src/app.css) |
| **Focus shell + posture nudge** | `focus_shell_window_active` (env `FOCUS_SHELL_*` or briefing defaults); `ops_posture_nudge_*` during Google / work screenshot blocks | [`web/src/App.tsx`](web/src/App.tsx) |
| **Sacred tasks + integrity debt** | `JANITOR_SACRED_SUBSTRINGS`; `sacred_integrity_debt_count` on cockpit (open sacred tasks overdue vs recon day) | [`todoist_service.py`](todoist_service.py), cockpit snapshot |
| **Week-ahead wardrobe pass** | `GET/POST /api/titan-prep` — Gemini reads **Mon–Sun** Google + personal calendar digest for the target week (query `week_start` Monday, default next week; `calendar_id` on POST defaults to `primary`). Needs `GEMINI_API_KEY` / configured Gemini. Cached in `titan_sartorial_prep.json` with `grounding_event_count`. | [`api/routers/titan_prep.py`](api/routers/titan_prep.py), [`api/services/titan_prep_week_digest.py`](api/services/titan_prep_week_digest.py) |

## Google Calendar OAuth (browser)

1. In [Google Cloud Console](https://console.cloud.google.com/), use an OAuth **Web application** client (or ensure your `credentials.json` is a web client whose authorized redirect URIs include the callback below).

2. Set the redirect URI to match the API (default):

   `http://127.0.0.1:8000/api/auth/google/callback`

   You can override with env var `GOOGLE_OAUTH_REDIRECT_URI` (must match the Console exactly).

3. Place the client JSON at the repo root as `credentials.json`, or set `GOOGLE_CALENDAR_CREDENTIALS` to its path (see `integrations/paths.py`).

4. In the Cockpit UI, use **Connect Google Calendar**. Google redirects back to the API, which writes `token.json` at the repo root (same file Streamlit’s calendar flow uses). OAuth `state` is validated in server memory (fine for a single local `uvicorn` worker; use a shared store if you run multiple workers).

5. After success, the browser returns to `COCKPIT_FRONTEND_URL` (default `http://localhost:5173`) with `?calendar=connected`.

## CORS and deployment

- **Local:** defaults allow `http://localhost:5173` and `http://127.0.0.1:5173`.
- **Production:** set `ALLOW_ORIGINS` to a comma-separated list of web origins, e.g.  
  `ALLOW_ORIGINS=https://cockpit.example.com,http://localhost:5173`

Register the production OAuth redirect URI (HTTPS) on the same Google OAuth client, and set `GOOGLE_OAUTH_REDIRECT_URI` and `COCKPIT_FRONTEND_URL` accordingly.

## State files (gitignored)

| File | Purpose |
|------|---------|
| `token.json` | Google Calendar OAuth tokens |
| `runway_overrides.json` | Manual hard-anchor overrides by date |
| `cockpit_protocol_settings.json` | Optional CHIEF_* overrides for the API cockpit |
| `identity.json` | Life purpose text (shared with Streamlit) |
| `cockpit_power_trio_state.json` | Todoist Power Trio cache (see **Power Trio state shape** below) |
| `posture_protocol_state.json` | Daily posture checkoffs (`chin_tucks`, `wall_slides`, `diaphragmatic_breathing`); shared with Streamlit. The Cockpit exposes **GET/PUT** `/api/posture-protocol?day=YYYY-MM-DD` for the web UI. |
| `morning_brief_state.json` | Dismissed Morning Brief cards per `YYYY-MM-DD` (cockpit dismiss endpoint). |
| `titan_sartorial_prep.json` | Cached week-ahead wardrobe pass (Gemini), keyed by target week Monday; rows may include `grounding_event_count` (calendar rows fed into the prompt). |

### Power Trio state shape (`cockpit_power_trio_state.json`)

The API uses **version 2** (`"version": 2`). Ranked slots and tactical steps are **per recon calendar day**, not global:

- **`tasks_by_id`**: map of Todoist task id → normalized task object (shared across days).
- **`days`**: keys are `YYYY-MM-DD`. Each value is a bucket with:
  - **`ranked_ids`**: ordered ids for that day’s Power Trio / refocus.
  - **`rank_warning`**, **`last_rank_iso`**, **`tactical_steps_by_task_id`** (per-day Gemini micro-steps).
- **Legacy v1** files with top-level `ranked_ids` are migrated on load: that list moves into `days[<today>]`.

The web cockpit passes `?day=` on sync/rank/complete reads so **Forward Recon** does not show another day’s ranked board. Streamlit should pass the same recon date into `save_ranked_cache(..., day=...)` when writing `ranked_cache.json` debug snapshots.

## EA Recon intelligence layer

### Morning brief (optimization scan)

- Payload: `GET /api/cockpit` includes `morning_brief` (anchors, top 3 kill zones, Combat #1 vs first kill zone). Deterministic **v1** (no Gemini).
- Shown only when **recon day is today**, local hour is in the morning window, and the card was not dismissed. Window defaults: **08:00–11:00** local, overridable with `BRIEFING_ACTIVE_START_HOUR` and `BRIEFING_ACTIVE_END_HOUR` (end is exclusive).
- **Dismiss:** `POST /api/cockpit/morning-brief/dismiss?day=YYYY-MM-DD` (day optional; defaults today). Persists to `morning_brief_state.json`.

### Energy / drain profile (Power Trio ranking)

- Optional block in **`identity.json`**: `drain_profile` with `high_drain_labels` (e.g. `["#HighDrain"]`) and `high_drain_title_substrings` (e.g. `["tax","legal"]`). **Empty lists = no change** to ranking.
- Todoist tasks carry resolved **`labels`** names when syncing (label id map from Todoist API v1).
- During **peak cognitive hours** (default **08:00–11:00** local), Gemini is instructed not to put high-drain tasks in slots 1–2, and Python **`apply_peak_cognitive_drain_guard`** post-processes the ordered list if the model drifts. Override with `PEAK_COGNITIVE_START_HOUR` / `PEAK_COGNITIVE_END_HOUR`.

### Janitor — silent fluff auto-archive

- After the usual stale-age close pass, the janitor can run **pattern-based** closes when `JANITOR_AUTO_ARCHIVE_FLUFF=1` (`true`/`yes`/`on` also accepted). Default is **off**.
- Matches are **case-insensitive** substrings on title + description (see `AUTO_ARCHIVE_TITLE_SUBSTRINGS` in `todoist_service.py`). Tasks containing **`@Titan_Core`** (or other preserve tokens in `AUTO_ARCHIVE_PRESERVE_SUBSTRINGS`) are never auto-closed.
- Auto-closed rows append to the graveyard with **`source: "janitor_auto"`** (no UI toast). The janitor API response includes `auto_fluff_closed_count`.

### MCP / external context (deferred)

- Future work should expose calendar, mail, and CRM context through an **`ExternalContextProvider`** boundary (interface only in this phase). The cockpit and ranking stay on in-repo services and env-backed integrations until that contract exists.

## Environment variables (summary)

| Variable | Role |
|----------|------|
| `ALLOW_ORIGINS` | CORS allowlist (comma-separated) |
| `GOOGLE_OAUTH_REDIRECT_URI` | OAuth redirect (must match GCP) |
| `COCKPIT_FRONTEND_URL` | Where to send the browser after OAuth |
| `GOOGLE_CALENDAR_CREDENTIALS` | Path to OAuth client JSON |
| `TODOIST_API_KEY`, `GEMINI_API_KEY` | Same as Streamlit / `.env` |
| `APPLE_CALENDAR_ICS_URL` | **Or** use iCloud credentials below — public/secret ICS feed URL for personal events |
| `ICLOUD_APPLE_ID`, `ICLOUD_APP_PASSWORD` | App-specific password; optional `ICLOUD_CALENDAR_NAME` |
| `COCKPIT_OPERATOR_NAME` | Optional display name in runway copy (defaults to neutral “You”) |
| `COCKPIT_AWAKE_START`, `COCKPIT_AWAKE_END` | Local times (`HH:MM`) clipping deep-work kill zones; defaults `05:00` / `19:30` |
| `COCKPIT_EARLIEST_INTEGRITY_WAKE` | Local `HH:MM` floor for **Integrity Wake** / **Tactical** times (default `05:00`) so runway math never implies waking earlier |
| `SCHEDULE_MEETING_EXCLUDE_SUBSTRINGS` | Optional comma-separated substrings (case-insensitive) merged into schedule “blocked time” title exclusions (same family as commute/RDW). Example: `lunch,focus hold` |
| `SCHEDULE_MEETING_LOAD_WARN_MINUTES` / `SCHEDULE_MEETING_LOAD_WARN_HOURS` | Threshold for the weekday “heavy calendar” flag (`meeting_load_warning`). Weekends always suppress that flag while still reporting total blocked minutes. |
| `BRIEFING_ACTIVE_START_HOUR`, `BRIEFING_ACTIVE_END_HOUR` | Local hour window when the Morning Brief card is eligible (end exclusive). Defaults `8` and `11`. |
| `PEAK_COGNITIVE_START_HOUR`, `PEAK_COGNITIVE_END_HOUR` | Local hour window for high-drain demotion in ranking (end exclusive). Defaults `8` and `11`. |
| `JANITOR_AUTO_ARCHIVE_FLUFF` | Set to `1` / `true` / `yes` / `on` to enable fluff auto-close after stale janitor pass. |
| `JANITOR_SACRED_SUBSTRINGS` | Comma-separated substrings (case-insensitive) on task title/description that **block** stale janitor close and fluff auto-archive (e.g. `Jason,Ellie,Kaitlyn,Ragstone`). |
| `FOCUS_SHELL_START_HOUR`, `FOCUS_SHELL_END_HOUR` | Local hour window when the cockpit may offer **Focus shell** (end exclusive). Defaults fall back to `BRIEFING_ACTIVE_*` then `8` / `11`. |
| `COCKPIT_OPS_POSTURE_NUDGE_SUBSTRINGS` | Comma-separated title hints; during a matching **Google** or **work screenshot** calendar block today, the UI can show a symmetry/posture nudge. |

Load order for the API matches Streamlit’s precedence: `integrations/env_loader.load_ragstone_env_files()` (`~/.ragstone/command_center.env`, repo `.env`), then **optional** `load_streamlit_secrets_into_environ()` (repo `.streamlit/secrets.toml`) for any key **not** already set in the environment. If you already configured personal Apple calendar in **`.streamlit/secrets.toml`** for the Streamlit app, the Cockpit API will pick up the same `APPLE_CALENDAR_ICS_URL` / `ICLOUD_*` values without copying them into `.env`. The **uvicorn** process must be restarted after changing secrets.
