# Titan Cockpit (Command Center Ops)

Monorepo: **FastAPI** backend, **Vite/React** web UI, **Swift** iOS (Vanguard Cockpit), Docker/Fly deployment.

## CI (matches GitHub Actions)

Local parity with [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && python -m pytest tests/ -q
docker build -t titan-cockpit-api:ci .
cd web && npm ci && npm run build
```

## API (development)

```bash
cp .env.example .env   # fill secrets locally; never commit .env
uvicorn api.main:app --reload --port 8000
# or: docker compose up --build
```

- Health: `GET /api/health` (public)
- Docs: [docs/COCKPIT_DEV.md](docs/COCKPIT_DEV.md), [docs/DOCKER.md](docs/DOCKER.md)

## Web UI

```bash
cd web && npm install && npm run dev
```

Vite dev server proxies `/api` when configured; production build: `npm run build`.

## iOS (Vanguard Cockpit)

```bash
cd ios/VanguardCockpit && ./../../scripts/ios_xcodegen.sh && open VanguardCockpit.xcodeproj
```

See [ios/VanguardCockpit/README.md](ios/VanguardCockpit/README.md).

iOS canonical API contract is the mobile namespace:

- `GET /api/mobile/dashboard`
- `GET /api/mobile/power-trio`
- `POST /api/mobile/opportunity-cost`
- `POST /api/mobile/windshield-triage`

The web cockpit routes remain separate and are non-canonical for iOS.

**Production / device / TestFlight:** set Xcode scheme environment variables:

| Variable | Example |
|----------|---------|
| `COCKPIT_API_BASE` | `https://ragstone-titan-cockpit.fly.dev` |
| `COCKPIT_API_KEY` | same value as server `COCKPIT_API_KEY` |

Or store the key in-app Keychain (Settings); base URL still needs `COCKPIT_API_BASE` for non-local hosts.

## Production API (Fly.io)

Current app host (example): **https://ragstone-titan-cockpit.fly.dev**

Set secrets on the app (replace values; do not commit):

```bash
fly secrets set COCKPIT_API_KEY="..." ALLOW_ORIGINS="https://your-frontend.example.com"
# add: TODOIST_API_KEY, GEMINI_API_KEY, etc. per .env.example
```

Optional persistent JSON state: create a volume, mount e.g. `/data`, then `fly secrets set RAGSTONE_DATA_ROOT=/data` (see [docs/DEPLOY.md](docs/DEPLOY.md), [fly.toml](fly.toml)).

Smoke tests:

```bash
curl -sS "https://ragstone-titan-cockpit.fly.dev/api/health"
curl -sS -H "X-Cockpit-Key: YOUR_KEY" "https://ragstone-titan-cockpit.fly.dev/api/cockpit"
```

## Zapier

HTTPS POST (JSON body):

`https://ragstone-titan-cockpit.fly.dev/api/integrations/zapier/inbound`

Header: `X-Cockpit-Key: <same as COCKPIT_API_KEY>` when the API is key-gated.

Details: [docs/DEPLOY.md](docs/DEPLOY.md).

## Optional: Apple push (server → device)

Server env: `APNS_KEY_ID`, `APNS_TEAM_ID`, `APNS_BUNDLE_ID`, `APNS_KEY_PATH` (see [.env.example](.env.example)). iOS entitlements and TestFlight: [docs/DEPLOY.md](docs/DEPLOY.md) (Device tokens + APNs).

## License / ownership

Internal Ragstone / Vanguard Cockpit project.
