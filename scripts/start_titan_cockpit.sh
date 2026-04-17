#!/usr/bin/env bash
# Start Titan Cockpit: FastAPI (8000) + Vite (5173) in ONE terminal.
# Run from your Mac Terminal (not pytest): ./scripts/start_titan_cockpit.sh
# Then open http://localhost:5173
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo ""
echo ">>> Titan Cockpit launcher (repo: $ROOT)"
echo ""

# Pick up Homebrew / common Node locations (and nvm if installed).
export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH:-}"
if [[ -z "${NVM_DIR:-}" && -d "$HOME/.nvm" ]]; then
  export NVM_DIR="$HOME/.nvm"
fi
if [[ -s "$HOME/.nvm/nvm.sh" ]]; then
  # shellcheck source=/dev/null
  . "$HOME/.nvm/nvm.sh"
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js (e.g. brew install node) or nvm, then retry." >&2
  exit 1
fi

if [[ ! -x "$ROOT/.venv/bin/uvicorn" ]]; then
  echo "ERROR: Missing .venv. From repo root run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

API_PID=""
WEB_PID=""

cleanup() {
  echo ""
  echo "Stopping servers..."
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${WEB_PID:-}" ]] && kill "$WEB_PID" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo "Installing web deps (if needed; first run can take a minute)..."
(cd "$ROOT/web" && npm install) || {
  echo "ERROR: npm install failed. Check Node/npm and network, then retry." >&2
  exit 1
}

echo ""
echo "Starting API  → http://127.0.0.1:8000"
"$ROOT/.venv/bin/uvicorn" api.main:app --reload --host 127.0.0.1 --port 8000 &
API_PID=$!

sleep 1

echo "Starting Vite → http://localhost:5173"
(cd "$ROOT/web" && npm run dev) &
WEB_PID=$!

sleep 1

echo ""
echo "==================================================================="
echo " Open the Command Center:  http://localhost:5173"
echo " API health check:          http://127.0.0.1:8000/api/health"
echo " Press Ctrl+C here to stop BOTH servers."
echo "==================================================================="
echo ""

wait
