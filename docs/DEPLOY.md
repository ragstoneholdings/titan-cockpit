# Titan Cockpit — production API

Phase 2 provides a **Docker image** and local compose ([DOCKER.md](DOCKER.md)). This document covers **hosted** deployments: TLS, secrets, CORS, persistence, Zapier, and operations.

## TLS

Terminate TLS at your **load balancer**, **reverse proxy** (Caddy, nginx), or **PaaS** (Fly.io, Railway, etc.). The container listens on plain HTTP on `PORT` (default **8000**) inside the private network.

## Health checks and monitoring

Use **`GET /api/health`** — returns `{"status":"ok"}` and stays **unauthenticated** even when `COCKPIT_API_KEY` is set.

Configure your platform’s **uptime check** or synthetic probe against that URL over HTTPS. Alert on **5xx** from the edge or app logs; use the platform’s log drain (Datadog, CloudWatch, etc.) if available.

Each response includes **`X-Request-ID`** (also accepted on inbound requests) for correlating support tickets with access logs.

## CORS

Set **`ALLOW_ORIGINS`** to a comma-separated list of browser origins (e.g. `https://cockpit.example.com,http://localhost:5173`). See [`_cors_origins`](../api/main.py). Do not use `*` in production.

## API authentication

When **`COCKPIT_API_KEY`** is set, every route except **`GET /api/health`** requires:

- Header **`X-Cockpit-Key: <key>`**, or  
- Header **`Authorization: Bearer <key>`**

**Zapier:** add **`X-Cockpit-Key`** as a custom header on the action that POSTs to Titan (same value as `COCKPIT_API_KEY`).

**iOS:** set the key in Keychain (Settings) or **`COCKPIT_API_KEY`** in the Xcode scheme; the app sends `X-Cockpit-Key` when configured ([`AppConfig`](../ios/VanguardCockpit/Sources/VanguardCockpit/AppConfig.swift)).

If `COCKPIT_API_KEY` is **unset**, the API behaves as in local dev (no key required). **Production should always set the key.**

## Rotating `COCKPIT_API_KEY`

1. Generate a new secret (long random string).
2. Set it in your host secret store (`fly secrets set`, Railway variables, etc.).
3. Redeploy or restart the service so the new value is live.
4. Update every client that sends the key: **Zapier** custom header, **iOS** Keychain / scheme, scripts, and any other integrations.
5. Revoke the old key by ensuring nothing still sends it; old key stops working as soon as the env var changes.

## Zapier inbound webhook

**URL (HTTPS only):**

`https://<your-public-host>/api/integrations/zapier/inbound`

**Headers:**

| Header | Value |
|--------|--------|
| `Content-Type` | `application/json` |
| `X-Cockpit-Key` | Same as `COCKPIT_API_KEY` (required when the API is key-gated) |
| `X-Idempotency-Key` or `Idempotency-Key` | Optional; duplicate values within ~48h return `deduped: true` without re-running side effects |

**Body:** JSON; see OpenAPI `/api/integrations/zapier/inbound` for structured fields. Unknown keys are allowed for Zapier passthrough.

If Todoist delegation fails, the response may include **`todoist_error`** and a structured **`error`** object; check application logs for the same (warning line).

## Persistence (`RAGSTONE_DATA_ROOT`)

Mutable JSON files (device tokens, Zapier trace, power trio state, schedule tradeoffs, etc.) default to the **application directory** (`PROJECT_ROOT`). In containers without a bind mount, that is **ephemeral**.

For production, set **`RAGSTONE_DATA_ROOT`** to a path on a **persistent volume** (e.g. `/data` on Fly.io after `fly volumes create` and a `[mounts]` entry in [`fly.toml`](../fly.toml)). The process will create the directory if possible.

Back up that directory on your platform’s schedule, or document export of the JSON files you care about before destructive operations.

## Fly.io (example)

1. Copy [`fly.toml`](../fly.toml); set `app` to your app name (`fly launch` can generate one).
2. `fly secrets set COCKPIT_API_KEY=...` plus other vars from [`.env.example`](../.env.example).
3. `fly secrets set ALLOW_ORIGINS=https://your-frontend.example.com`
4. Optionally create a volume, set `RAGSTONE_DATA_ROOT=/data`, and uncomment `[[mounts]]` in `fly.toml`.
5. `fly deploy`

Keep the **same image** CI builds in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Docker Compose (production-style)

See [`docker-compose.prod.yml`](../docker-compose.prod.yml): builds the image, no `--reload`, optional volume for `/data` + `RAGSTONE_DATA_ROOT`.

## Device tokens and APNs (Phase 8)

- **`POST /api/device/register`** stores the device token (hex). Requires the API key when `COCKPIT_API_KEY` is set.
- **`GET /api/device/tokens`** lists stored rows; protected by the same middleware when the key is set. Set **`COCKPIT_BLOCK_DEVICE_TOKENS_WITHOUT_KEY=1`** to return **403** when `COCKPIT_API_KEY` is unset (stricter production guard).
- Server push uses **`APNS_KEY_ID`**, **`APNS_TEAM_ID`**, **`APNS_BUNDLE_ID`** (same as iOS bundle id), **`APNS_KEY_PATH`** (path to `.p8` inside the container or on a secret mount). Set **`APNS_USE_SANDBOX=true`** for development builds.
- **`POST /api/device/push/test`** — broadcast test alert (requires `COCKPIT_API_KEY` and APNs env).
- **`POST /api/device/push/integrity-sentry`** — if today’s cockpit **`integrity_sentry_state`** is `CRITICAL`, sends one alert to all registered devices (for cron or manual smoke tests).

## Incident basics

1. **API down:** Check platform status, recent deploy, and secrets. Hit **`GET /api/health`** from outside the VPC.
2. **401 everywhere:** Key mismatch — verify `COCKPIT_API_KEY` on the server matches Zapier/iOS.
3. **CORS errors in browser:** Add your site origin to **`ALLOW_ORIGINS`** (exact scheme + host + port).
4. **Data loss after redeploy:** Ensure **`RAGSTONE_DATA_ROOT`** points at a persistent volume or restore from backup.

## Device tokens (Phase 5+)

`POST /api/device/register` stores APNs device token hex for push. When `COCKPIT_API_KEY` is set, clients must send the key like any other route.

**iOS builds:** Enable the Push Notifications capability in Xcode (Apple Developer). For **TestFlight / App Store** builds, set **`aps-environment`** to **`production`** in the app entitlements; keep **`development`** for local debug. The Vanguard Cockpit target uses [`VanguardCockpit.entitlements`](../ios/VanguardCockpit/Sources/VanguardCockpit/VanguardCockpit.entitlements).
