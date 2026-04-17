#!/usr/bin/env bash
# Tiered builds for ios/VanguardCockpit (see ios/VanguardCockpit/README.md).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IOS="$ROOT/ios/VanguardCockpit"
SCHEME="${SCHEME:-VanguardCockpit}"
DEST="${DEST:-platform=iOS Simulator,name=iPhone 17}"

tier="${1:-fast}"

if [[ ! -d "$IOS/VanguardCockpit.xcodeproj" ]]; then
  echo "Missing Xcode project. From $IOS run: xcodegen generate"
  exit 1
fi

cd "$IOS"

case "$tier" in
  fast)
    xcodebuild -project VanguardCockpit.xcodeproj -scheme "$SCHEME" -destination "$DEST" -configuration Debug build
    ;;
  test)
    xcodebuild -project VanguardCockpit.xcodeproj -scheme "$SCHEME" -destination "$DEST" -configuration Debug test
    ;;
  full)
    xcodebuild -project VanguardCockpit.xcodeproj -scheme "$SCHEME" -destination "$DEST" -configuration Debug build-for-testing test
    ;;
  *)
    echo "Usage: $0 [fast|test|full]"
    exit 1
    ;;
esac
