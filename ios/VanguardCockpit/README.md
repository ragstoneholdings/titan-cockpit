# Vanguard Cockpit (iOS)

Native SwiftUI client for the Titan Cockpit mobile API surface (`GET /api/mobile/dashboard`, `GET /api/mobile/power-trio`, `POST /api/mobile/opportunity-cost`, `POST /api/mobile/windshield-triage`).

## Generate the Xcode project

`VanguardCockpit.xcodeproj` is checked in after generation. To **regenerate** from `project.yml`:

```bash
cd "/path/to/Command Center Ops"
./scripts/ios_xcodegen.sh
```

That script uses `ios/VanguardCockpit/.tools/xcodegen/bin/xcodegen` if present, otherwise `xcodegen` on your `PATH` (e.g. `brew install xcodegen`). The `.tools/` folder is gitignored; download [XcodeGen releases](https://github.com/yonaskolb/XcodeGen/releases) and unzip so `bin/xcodegen` exists there, or rely on Homebrew.

```bash
open ios/VanguardCockpit/VanguardCockpit.xcodeproj
```

Set your **Development Team** on both the app and `DeviceActivityMonitor` targets. Enable the **Family Controls** and **App Groups** capabilities in Xcode if they are not applied from entitlements.

### Full Xcode for `xcodebuild`

Simulator/device builds require **Xcode.app**, not only Command Line Tools. If `xcodebuild` errors about CLT, point the active developer directory at Xcode (adjust path if your Xcode is elsewhere):

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

## API base URL

Default: `http://127.0.0.1:8000`. Override for Simulator/device:

- Scheme **Environment Variable**: `COCKPIT_API_BASE` = `http://<your-mac-lan-ip>:8000`

When the server sets **`COCKPIT_API_KEY`**, send the same value: use scheme env **`COCKPIT_API_KEY`**, or **Settings → API auth → Save to Keychain** (sends `X-Cockpit-Key` on each request). See [docs/DEPLOY.md](../../docs/DEPLOY.md).

## TestFlight (Phase 5)

1. Set **Development Team** on **VanguardCockpit** and **DeviceActivityMonitor**; verify entitlements (Family Controls, App Groups, HealthKit if used).
2. Confirm **privacy usage strings** in `project.yml` match enabled capabilities.
3. Point **`COCKPIT_API_BASE`** at your hosted API; set API key via Keychain or scheme.
4. **Product → Archive** → Distribute App → TestFlight.

**Executive CockPit/** at the repo root remains **non-canonical**; ship from this target only, or merge and archive the duplicate project.

## Build tiers

From repo root:

```bash
chmod +x scripts/ios_build.sh
./scripts/ios_build.sh fast    # compile only
./scripts/ios_build.sh test    # xcodebuild test
./scripts/ios_build.sh full    # build-for-testing + test
```

Use a **physical device** destination for Screen Time / haptics validation; Simulator is fine for compile + most UI.

## Cursor MCP

[`.cursor/mcp.json`](../../.cursor/mcp.json) includes an `xcodebuild` server via `npx`. If the package name or args differ for your setup, adjust them locally. Add a separate Apple documentation MCP if you use one.

## ManagedSettings note

Shielding an entire **category** overrides per-app exemptions inside that category. Prefer **application tokens** for granular blocks (see `ShieldManager.swift`).

## Physical device (Screen Time) smoke test

Simulator cannot fully validate Family Controls / Managed Settings. On a **provisioned iPhone**:

1. Set **Signing & Capabilities** → **Development Team** on **VanguardCockpit** and **DeviceActivityMonitor**; confirm **Family Controls** + **App Groups** (`group.com.ragstone.vanguard.cockpit`) match the Developer portal.
2. Install the build, open the app, tap **Request authorization** (Screen Time), then pick apps in **Family Activity** and **Apply shields to selection**.
3. Tap **Register daily schedules**; at a scheduled window, confirm expected shielding (or use Console / `log stream` for the extension).
4. Verify **App Group** shared keys (e.g. `lastIntervalStart` written by `DeviceActivityMonitorExtension`) via the shared `UserDefaults` suite or temporary UI.

## iOS projects in this repo

**Decision:** [`ios/VanguardCockpit/`](.) is the **canonical** Vanguard Cockpit iOS app (FastAPI client, Screen Time stack, extension, tests). The separate **`Executive CockPit/`** tree at the repo root is a **parallel** Xcode project (its own git history); keep it only while experimenting, then **merge** features here or **archive** it to avoid two maintenance surfaces.
