# Titan Cockpit — Docker (API)

Phase 2 adds a **repeatable API image** and optional **docker compose** for local development. Production hosting, TLS, and mobile API auth are **Phase 3**.

## Quick start

From the repo root:

```bash
cp .env.example .env   # fill in secrets as needed
docker compose up --build
```

Smoke check:

```bash
curl -sSf http://127.0.0.1:8000/api/health
```

The API runs with **hot reload** (`--reload`) and mounts the **repository** at `/app`, so JSON state files stay on your Mac at the same paths as `make dev-api`. Runtime config is loaded from **`.env`** in the repo root via [`integrations/env_loader.py`](../integrations/env_loader.py).

## Build the image only

```bash
docker build -t titan-cockpit-api:local .
```

## Port

Override the host port:

```bash
COCKPIT_PORT=9000 docker compose up
```

## iOS Simulator and `COCKPIT_API_BASE`

- **API on the Mac (no Docker):** `localhost` / `127.0.0.1:8000` works from the Simulator.
- **API in Docker with `docker compose`:** the API is published on the host’s loopback (`127.0.0.1:8000` by default), so **same** Simulator URL as above.
- **Physical device:** `127.0.0.1` points at the phone, not your Mac — use your Mac’s LAN IP or a tunnel (Phase 3).

Set the Xcode scheme environment variable **`COCKPIT_API_BASE`** (see [`AppConfig.swift`](../ios/VanguardCockpit/Sources/VanguardCockpit/AppConfig.swift)), e.g. `http://127.0.0.1:8000`.

## CI

GitHub Actions runs `pytest` and `docker build` on push/PR (see `.github/workflows/ci.yml`).

## Production auth

If you set **`COCKPIT_API_KEY`** in the container environment, clients must send **`X-Cockpit-Key`** or **`Authorization: Bearer`**. `GET /api/health` stays public. See [DEPLOY.md](DEPLOY.md).

## What is not in this phase

- No TLS or public hostname.
- No API key auth for clients (see [`api/main.py`](../api/main.py) CORS only).
- State remains **JSON files under the repo root** when using bind-mount; for serverless/ephemeral containers, use Phase 3 storage or env-driven paths.
