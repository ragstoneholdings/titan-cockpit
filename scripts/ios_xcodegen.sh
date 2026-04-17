#!/usr/bin/env bash
# Regenerate ios/VanguardCockpit/VanguardCockpit.xcodeproj from project.yml.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IOS="$ROOT/ios/VanguardCockpit"
TOOL="$IOS/.tools/xcodegen/bin/xcodegen"

if [[ -x "$TOOL" ]]; then
  cd "$IOS"
  exec "$TOOL" generate
fi
if command -v xcodegen >/dev/null 2>&1; then
  cd "$IOS"
  exec xcodegen generate
fi
echo "No XcodeGen found. Either:"
echo "  1) brew install xcodegen"
echo "  2) Or unpack XcodeGen into: $IOS/.tools/xcodegen/ (see ios/VanguardCockpit/README.md)"
exit 1
