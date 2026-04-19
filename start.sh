#!/bin/bash

set -euo pipefail

export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PY="$SCRIPT_DIR/.venv/bin/python"
PYTHON_BIN="$VENV_PY"

DASHBOARD_DIR="$SCRIPT_DIR/upscrolled-pulse"
DASHBOARD_PORT="${BISHOP_DASHBOARD_PORT:-}"
if [[ -z "$DASHBOARD_PORT" && -f "$SCRIPT_DIR/.env" ]]; then
    DASHBOARD_PORT="$(awk -F= '/^BISHOP_DASHBOARD_PORT=/{print $2; exit}' "$SCRIPT_DIR/.env" | tr -d '"'"'[:space:]'"'"')"
fi
DASHBOARD_PORT="${DASHBOARD_PORT:-3113}"
START_LISTENER=1
START_DASHBOARD=1
START_MONITOR=0
START_OBSERVER=0
AUTO_BOOTSTRAP=1
PIDS=()
CLEANED_UP=0
APP_PORT="${PORT:-8080}"
LAST_PID=""
OBSERVER_BOOT_CMD="${BISHOP_TERMINAL_OBSERVER_BOOT_CMD:-}"
OBSERVER_HEALTH_URL="${TERMINAL_OBSERVER_LOCAL_URL:-}"
if [[ -n "$OBSERVER_BOOT_CMD" ]]; then
    START_OBSERVER=1
fi

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
    BISHOP_NEON=$'\033[38;5;118m'
    BISHOP_STEEL=$'\033[38;5;245m'
    BISHOP_RESET=$'\033[0m'
else
    BISHOP_NEON=''
    BISHOP_STEEL=''
    BISHOP_RESET=''
fi

usage() {
    cat <<EOF
BISHOP master launcher

Usage:
  ./start.sh [options]

Options:
  --no-listener     Start worker only, skip app.py
  --no-ui           Skip the Next.js dashboard
  --with-monitor    Also start github_monitor_worker.py
  --with-observer   Start the optional terminal observer sidecar from \$BISHOP_TERMINAL_OBSERVER_BOOT_CMD
  --skip-install    Do not auto-run ./install.sh --ensure before startup
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
        --with-observer)
            START_OBSERVER=1
            ;;
        --skip-install)
            AUTO_BOOTSTRAP=0
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

print_banner() {
    printf '%b\n' "${BISHOP_NEON}██████╗ ██╗███████╗██╗  ██╗ ██████╗ ██████╗ ${BISHOP_RESET}"
    printf '%b\n' "${BISHOP_NEON}██╔══██╗██║██╔════╝██║  ██║██╔═══██╗██╔══██╗${BISHOP_RESET}"
    printf '%b\n' "${BISHOP_NEON}██████╔╝██║███████╗███████║██║   ██║██████╔╝${BISHOP_RESET}"
    printf '%b\n' "${BISHOP_NEON}██╔══██╗██║╚════██║██╔══██║██║   ██║██╔═══╝ ${BISHOP_RESET}"
    printf '%b\n' "${BISHOP_NEON}██████╔╝██║███████║██║  ██║╚██████╔╝██║     ${BISHOP_RESET}"
    printf '%b\n' "${BISHOP_NEON}╚═════╝ ╚═╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝     ${BISHOP_RESET}"
    printf '%b\n' "${BISHOP_STEEL}LOCAL STACK · worker · slack · dashboard${BISHOP_RESET}"
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

require_http() {
    local url="$1"
    local label="$2"
    local attempts="${3:-10}"
    local delay_seconds="${4:-1}"

    for _ in $(seq 1 "$attempts"); do
        if curl -fsS "$url" >/dev/null 2>&1; then
            return 0
        fi
        sleep "$delay_seconds"
    done

    echo "$label did not become healthy at $url" >&2
    return 1
}

port_in_use() {
    local port="$1"
    python3 - "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

port = int(sys.argv[1])
sock = socket.socket()
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(0)
finally:
    sock.close()
raise SystemExit(1)
PY
}

require_port_free() {
    local port="$1"
    local label="$2"
    if port_in_use "$port"; then
        echo "$label port $port is already in use." >&2
        if command -v lsof >/dev/null 2>&1; then
            echo "Process using port $port:" >&2
            lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2 || true
        fi
        exit 1
    fi
}

require_alive() {
    local pid="$1"
    local label="$2"
    if ! kill -0 "$pid" >/dev/null 2>&1; then
        echo "$label exited immediately. Check the logs above." >&2
        exit 1
    fi
}

start_process() {
    local label="$1"
    shift
    log "▶ $label"
    "$@" &
    local pid=$!
    LAST_PID="$pid"
    PIDS+=("$pid")
    log "  pid=$pid"
}

cleanup() {
    if [[ "$CLEANED_UP" -eq 1 ]]; then
        return
    fi
    CLEANED_UP=1

    echo ""
    log "Shutting down BISHOP..."
    for pid in "${PIDS[@]:-}"; do
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" >/dev/null 2>&1 || true
        fi
    done
    wait >/dev/null 2>&1 || true
}

trap cleanup EXIT SIGINT SIGTERM

print_banner
log "Starting BISHOP local stack..."
if [[ "$AUTO_BOOTSTRAP" -eq 1 ]]; then
    log "Ensuring local dependencies..."
    bash "$SCRIPT_DIR/install.sh" --ensure
fi

require_cmd "$PYTHON_BIN" "Run ./install.sh to create a compatible local environment."
require_cmd curl "curl is required for local health checks."
log "Python: $PYTHON_BIN"

"$PYTHON_BIN" - <<'PY' >/dev/null
import app
import local_worker
PY

if [[ "$START_LISTENER" -eq 1 ]]; then
    require_port_free "$APP_PORT" "Python API"
fi
if [[ "$START_DASHBOARD" -eq 1 ]]; then
    require_port_free "$DASHBOARD_PORT" "Dashboard UI"
fi

if [[ "$START_OBSERVER" -eq 1 && -z "$OBSERVER_BOOT_CMD" ]]; then
    echo "Observer sidecar requested, but BISHOP_TERMINAL_OBSERVER_BOOT_CMD is not set." >&2
    exit 1
fi

start_process "Local worker" "$PYTHON_BIN" local_worker.py
sleep 2
WORKER_PID="$LAST_PID"
require_alive "$WORKER_PID" "Local worker"

if [[ "$START_LISTENER" -eq 1 ]]; then
    start_process "Slack listener + HTTP gateway" "$PYTHON_BIN" app.py
    sleep 2
    LISTENER_PID="$LAST_PID"
    require_alive "$LISTENER_PID" "Slack listener + HTTP gateway"
    require_http "http://127.0.0.1:$APP_PORT/" "Python API" 12 1
    require_alive "$LISTENER_PID" "Slack listener + HTTP gateway"
fi

if [[ "$START_OBSERVER" -eq 1 ]]; then
    start_process "Terminal observer sidecar" bash -lc "$OBSERVER_BOOT_CMD"
    sleep 2
    OBSERVER_PID="$LAST_PID"
    require_alive "$OBSERVER_PID" "Terminal observer sidecar"
    if [[ -n "$OBSERVER_HEALTH_URL" ]]; then
        require_http "$OBSERVER_HEALTH_URL" "Terminal observer sidecar" 10 1
        require_alive "$OBSERVER_PID" "Terminal observer sidecar"
    fi
fi

if [[ "$START_MONITOR" -eq 1 ]]; then
    start_process "GitHub monitor" "$PYTHON_BIN" github_monitor_worker.py
fi

if [[ "$START_DASHBOARD" -eq 1 ]]; then
    start_process "Dashboard UI on http://localhost:$DASHBOARD_PORT" bash -lc "cd '$DASHBOARD_DIR' && PORT='$DASHBOARD_PORT' npm run dev"
    DASHBOARD_PID="$LAST_PID"
    require_alive "$DASHBOARD_PID" "Dashboard UI"
    require_http "http://127.0.0.1:$DASHBOARD_PORT/" "Dashboard UI" 20 1
    require_alive "$DASHBOARD_PID" "Dashboard UI"
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
