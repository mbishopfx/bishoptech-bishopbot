#!/usr/bin/env bash
set -euo pipefail

PLIST_SRC="/Users/matthewbishop/BishopBot/bishop-meta/launchd/com.bishopbot.local-worker.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.bishopbot.local-worker.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cp -f "$PLIST_SRC" "$PLIST_DST"

UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

# Best-effort unload if already running
launchctl bootout "$DOMAIN" "$PLIST_DST" 2>/dev/null || true

# Load
launchctl bootstrap "$DOMAIN" "$PLIST_DST"
launchctl enable "$DOMAIN/com.bishopbot.local-worker" || true
launchctl kickstart -k "$DOMAIN/com.bishopbot.local-worker" || true

echo "Installed and started: com.bishopbot.local-worker"
