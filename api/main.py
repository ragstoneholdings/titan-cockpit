"""
FastAPI entrypoint for the Titan Cockpit web UI.

Dev:
  uvicorn api.main:app --reload --port 8000

CORS: set ALLOW_ORIGINS to a comma-separated list (e.g. https://app.example.com,http://localhost:5173).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.middleware.cockpit_auth import CockpitAuthMiddleware
from api.middleware.request_logging import RequestContextMiddleware
from integrations.env_loader import env_str, load_ragstone_env_files, load_streamlit_secrets_into_environ

load_ragstone_env_files()
load_streamlit_secrets_into_environ()

from api.routers import (  # noqa: E402
    calendar_advisory,
    cockpit,
    device_push,
    golden_path_api,
    google_auth,
    health,
    identity_api,
    integrations,
    integrity_api,
    mobile,
    posture_protocol_api,
    protocol_api,
    qbo,
    runway_api,
    schedule_tradeoffs,
    titan_prep,
    todoist,
    vanguard,
)


def _cors_origins() -> list[str]:
    raw = env_str("ALLOW_ORIGINS", "").strip()
    if raw:
        return [x.strip() for x in raw.split(",") if x.strip()]
    return [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


app = FastAPI(title="Ragstone Command Center API", version="0.1.0")

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CockpitAuthMiddleware)

app.include_router(health.router, prefix="/api")
app.include_router(cockpit.router, prefix="/api")
app.include_router(mobile.router, prefix="/api")
app.include_router(todoist.router, prefix="/api")
app.include_router(calendar_advisory.router, prefix="/api")
app.include_router(google_auth.router, prefix="/api")
app.include_router(runway_api.router, prefix="/api")
app.include_router(protocol_api.router, prefix="/api")
app.include_router(identity_api.router, prefix="/api")
app.include_router(integrity_api.router, prefix="/api")
app.include_router(posture_protocol_api.router, prefix="/api")
app.include_router(schedule_tradeoffs.router, prefix="/api")
app.include_router(golden_path_api.router, prefix="/api")
app.include_router(titan_prep.router, prefix="/api")
app.include_router(vanguard.router, prefix="/api")
app.include_router(qbo.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(device_push.router, prefix="/api")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WEB_DIST = _REPO_ROOT / "web" / "dist"

_COCKPIT_ROOT_HINT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Titan Cockpit — API only</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 42rem; margin: 2rem; line-height: 1.5; color: #e8eef5; background: #0f1419; }
    code { background: #1a222c; padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.9em; }
    a { color: #fbbf24; }
  </style>
</head>
<body>
  <h1>Titan Cockpit API is running</h1>
  <p>No built UI found in <code>web/dist</code>. Pick one:</p>
  <ul>
    <li><strong>Dev (hot reload):</strong> run <code>cd web &amp;&amp; npm install &amp;&amp; npm run dev</code>,
      then open <a href="http://localhost:5173">http://localhost:5173</a> — Vite proxies <code>/api</code> to this server.</li>
    <li><strong>Or build once:</strong> <code>cd web &amp;&amp; npm run build</code>, restart the API — the UI is served here on port 8000.</li>
    <li><strong>Or use the launcher:</strong> <code>./scripts/start_titan_cockpit.sh</code> (starts API + Vite).</li>
  </ul>
  <p><a href="/api/health">API health</a> · <a href="/docs">OpenAPI docs</a></p>
</body>
</html>"""


if _WEB_DIST.is_dir() and (_WEB_DIST / "index.html").is_file():
    app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="cockpit_web")
else:

    @app.get("/", include_in_schema=False)
    def _cockpit_root_hint() -> HTMLResponse:
        return HTMLResponse(_COCKPIT_ROOT_HINT_HTML)
