#!/usr/bin/env bash
# Run the new Titan Cockpit stack (API + Vite UI).
# Usage:
#   Terminal 1: ./scripts/dev_cockpit.sh api
#   Terminal 2: ./scripts/dev_cockpit.sh web
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
case "${1:-}" in
  api)
    exec .venv/bin/uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
    ;;
  web)
    cd web && npm install && npm run dev
    ;;
  *)
    echo "Usage: $0 api|web" >&2
    exit 1
    ;;
esac
