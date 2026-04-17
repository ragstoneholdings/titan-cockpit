#!/usr/bin/env bash
# After you create an EMPTY repository on GitHub (no README, no license, no .gitignore),
# run from the repo root:
#   chmod +x scripts/github_remote_push.sh
#   ./scripts/github_remote_push.sh git@github.com:YOURUSER/command-center-ops.git
# Or HTTPS:
#   ./scripts/github_remote_push.sh https://github.com/YOURUSER/command-center-ops.git
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <git-remote-url>" >&2
  echo "Create an empty GitHub repository first, then pass its clone URL." >&2
  exit 1
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -d .git ]]; then
  echo "No .git in $ROOT — run the import/bootstrap steps first." >&2
  exit 1
fi
git remote remove origin 2>/dev/null || true
git remote add origin "$1"
git push -u origin main
