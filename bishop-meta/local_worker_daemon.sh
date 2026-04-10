#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/Users/matthewbishop/BishopBot"
PY="$ROOT_DIR/.venv/bin/python"

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

cd "$ROOT_DIR"

# Keep the machine awake while the worker is running.
# Remove caffeinate if you don't want this behavior.
exec /usr/bin/caffeinate -is "$PY" "$ROOT_DIR/local_worker.py"
