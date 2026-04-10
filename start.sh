#!/bin/bash

set -euo pipefail

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PY="$SCRIPT_DIR/.venv/bin/python"
PYTHON_BIN="python3"
if [[ -x "$VENV_PY" ]]; then
    PYTHON_BIN="$VENV_PY"
fi

DASHBOARD_DIR="$SCRIPT_DIR/upscrolled-pulse"
DASHBOARD_PORT="${BISHOP_DASHBOARD_PORT:-}"
if [[ -z "$DASHBOARD_PORT" && -f "$SCRIPT_DIR/.env" ]]; then
    DASHBOARD_PORT="$(awk -F= '/^BISHOP_DASHBOARD_PORT=/{print $2; exit}' "$SCRIPT_DIR/.env" | tr -d '"'"'[:space:]'"'"')"
fi
DASHBOARD_PORT="${DASHBOARD_PORT:-3113}"
START_LISTENER=1
START_DASHBOARD=1
START_MONITOR=0
AUTO_INSTALL_UI=1
PIDS=()
CLEANED_UP=0

usage() {
    cat <<EOF
BISHOP master launcher

Usage:
  ./start.sh [options]

Options:
  --no-listener     Start worker only, skip app.py
  --no-ui           Skip the Next.js dashboard
  --with-monitor    Also start github_monitor_worker.py
  --no-ui-install   Do not auto-run npm install when node_modules is missing
  --port <port>     Override dashboard port (default: 3113)
  --help            Show this help

Examples:
  ./start.sh
  ./start.sh --with-monitor
  ./start.sh --no-ui
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-listener)
            START_LISTENER=0
            ;;
        --no-ui)
            START_DASHBOARD=0
            ;;
        --with-monitor)
            START_MONITOR=1
            ;;
        --no-ui-install)
            AUTO_INSTALL_UI=0
            ;;
        --port)
            shift
            if [[ $# -eq 0 ]]; then
                echo "Missing value for --port" >&2
                exit 1
            fi
            DASHBOARD_PORT="$1"
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
    shift
done

log() {
    printf '%s\n' "$1"
}

require_cmd() {
    local cmd="$1"
    local help_text="$2"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Missing required command: $cmd" >&2
        echo "$help_text" >&2
        exit 1
    fi
}

start_process() {
    local label="$1"
    shift
    log "▶ $label"
    "$@" &
    local pid=$!
    PIDS+=("$pid")
    log "  pid=$pid"
}

cleanup() {
    if [[ "$CLEANED_UP" -eq 1 ]]; then
        return
    fi
    CLEANED_UP=1

    echo ""
    log "🛑 Shutting down BISHOP..."
    for pid in "${PIDS[@]:-}"; do
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
    done
    wait >/dev/null 2>&1 || true
}

trap cleanup EXIT SIGINT SIGTERM

log "🤖 Starting BISHOP local stack..."
log "🐍 Python: $PYTHON_BIN"

require_cmd "$PYTHON_BIN" "Create the project venv with: python3 -m venv .venv && ./.venv/bin/pip install -r requirements_local.txt"

if [[ "$START_DASHBOARD" -eq 1 ]]; then
    require_cmd npm "Install Node.js and npm to run the dashboard."
    if [[ ! -d "$DASHBOARD_DIR/node_modules" ]]; then
        if [[ "$AUTO_INSTALL_UI" -eq 1 ]]; then
            log "📦 Dashboard dependencies missing, running npm install..."
            (cd "$DASHBOARD_DIR" && npm install)
        else
            echo "Dashboard dependencies are missing at $DASHBOARD_DIR/node_modules" >&2
            echo "Run: cd $DASHBOARD_DIR && npm install" >&2
            exit 1
        fi
    fi
fi

start_process "Local worker" "$PYTHON_BIN" local_worker.py
sleep 2

if [[ "$START_LISTENER" -eq 1 ]]; then
    start_process "Slack listener + HTTP gateway" "$PYTHON_BIN" app.py
    sleep 1
fi

if [[ "$START_MONITOR" -eq 1 ]]; then
    start_process "GitHub monitor" "$PYTHON_BIN" github_monitor_worker.py
fi

if [[ "$START_DASHBOARD" -eq 1 ]]; then
    start_process "Dashboard UI on http://localhost:$DASHBOARD_PORT" bash -lc "cd '$DASHBOARD_DIR' && PORT='$DASHBOARD_PORT' npm run dev"
fi

echo ""
log "BISHOP is live."
log "- Worker: local task execution and session control"
if [[ "$START_LISTENER" -eq 1 ]]; then
    log "- Listener: Slack Socket Mode + local HTTP API"
fi
if [[ "$START_DASHBOARD" -eq 1 ]]; then
    log "- Dashboard: http://localhost:$DASHBOARD_PORT"
fi
if [[ "$START_MONITOR" -eq 1 ]]; then
    log "- GitHub monitor: enabled"
fi
log "Press Ctrl+C to stop the full stack."
echo ""

if command -v caffeinate >/dev/null 2>&1; then
    caffeinate -dimsu &
    CAFFEINATE_PID=$!
    PIDS+=("$CAFFEINATE_PID")
fi

wait
