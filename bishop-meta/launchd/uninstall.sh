#!/usr/bin/env bash
set -euo pipefail

PLIST_DST="$HOME/Library/LaunchAgents/com.bishopbot.local-worker.plist"

UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

if [[ -f "$PLIST_DST" ]]; then
  launchctl bootout "$DOMAIN" "$PLIST_DST" 2>/dev/null || true
  rm -f "$PLIST_DST"
fi

echo "Uninstalled: com.bishopbot.local-worker"
