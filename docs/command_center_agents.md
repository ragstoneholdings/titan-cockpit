# Command Center — Cursor agents & MCP (platform layer)

These workflows run **outside** the Streamlit app (`command_center_v2.py`). Configure them in **Cursor** (Agent mode, rules, MCP).

## Project Janitor (Todoist)

- **Cadence:** e.g. every **4 hours** (manual agent run, cron, or CI).
- **Logic:** For each active Todoist task, if it has been **untouched for 14 days** and does not align with your **Titan** identity brief, **archive** it or move it to a **Someday** project and append one line to a **graveyard log** (e.g. `someday_graveyard.md` in this repo).
- **Implementation:** Use a Cursor **Agent** with an explicit checklist, or a small Python script plus `TODOIST_API_KEY`, documented in `.cursor/rules` or `AGENTS.md`.

## Google Workspace MCP

- **Goal:** Let an agent **read** Gmail (and optionally Calendar) via **MCP** to gather context and **draft replies** aligned with **Power Trio** tasks.
- **Setup:** Install the Google Workspace MCP server your team uses, add it to Cursor MCP settings, and store OAuth / service credentials per that server’s docs.
- **Boundary:** The Streamlit UI does not call MCP directly in v1; drafts can be pasted into **Strike** outputs manually or wired later.

## Secrets

- `TODOIST_API_KEY` — Power Trio REST API.
- `GEMINI_API_KEY` — ranking, The Plan, Strike, Architect.
- Google Calendar OAuth — `credentials.json` + `token.json` in the project root (Integrity Runway anchor).
