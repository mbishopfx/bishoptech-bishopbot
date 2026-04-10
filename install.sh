#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR="$SCRIPT_DIR/.venv"
UI_DIR="$SCRIPT_DIR/upscrolled-pulse"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
TARGET_PYTHON_MINOR=11
AUTO_SYSTEM_DEPS=1
ENSURE_ONLY=0
PIP_INSTALL_ARGS=()
NPM_INSTALL_ARGS=()

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
BISHOP installer

Usage:
  ./install.sh [options]

Options:
  --ensure           Quietly ensure local dependencies exist and repair the venv if needed
  --no-system-deps   Do not use Homebrew to install missing python/node/redis
  --help             Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ensure)
            ENSURE_ONLY=1
            ;;
        --no-system-deps)
            AUTO_SYSTEM_DEPS=0
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

if [[ "$ENSURE_ONLY" -eq 1 ]]; then
    PIP_INSTALL_ARGS=(-q --disable-pip-version-check)
    NPM_INSTALL_ARGS=(--silent)
fi

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
    printf '%b\n' "${BISHOP_STEEL}INSTALLER · local deps · redis · dashboard${BISHOP_RESET}"
}

have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

choose_python() {
    local candidate=""
    for cmd in python3.11 python3.12 python3.13 python3.10 python3; do
        if have_cmd "$cmd"; then
            if "$cmd" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
            then
                candidate="$cmd"
                break
            fi
        fi
    done
    printf '%s' "$candidate"
}

ensure_homebrew_pkg() {
    local binary="$1"
    local package="$2"

    if have_cmd "$binary"; then
        return 0
    fi

    if [[ "$AUTO_SYSTEM_DEPS" -ne 1 ]]; then
        echo "Missing required command: $binary" >&2
        echo "Install it manually, or rerun ./install.sh without --no-system-deps." >&2
        exit 1
    fi

    if ! have_cmd brew; then
        echo "Missing required command: $binary" >&2
        echo "Homebrew is not installed, so BISHOP cannot auto-install $package." >&2
        exit 1
    fi

    log "📦 Installing $package via Homebrew..."
    brew install "$package"
}

venv_python_ok() {
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        return 1
    fi

    "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

ensure_redis_running() {
    if ! have_cmd redis-server; then
        echo "redis-server is not available after install." >&2
        exit 1
    fi

    if have_cmd redis-cli && redis-cli ping >/dev/null 2>&1; then
        return 0
    fi

    if have_cmd brew && brew list redis >/dev/null 2>&1; then
        log "🔌 Starting Redis via Homebrew services..."
        brew services start redis >/dev/null
    else
        log "🔌 Starting Redis in the background..."
        redis-server --daemonize yes >/dev/null
    fi

    if have_cmd redis-cli; then
        for _ in 1 2 3 4 5; do
            if redis-cli ping >/dev/null 2>&1; then
                return 0
            fi
            sleep 1
        done
    fi

    echo "Redis did not start cleanly." >&2
    exit 1
}

ensure_python_env() {
    local python_cmd
    python_cmd="$(choose_python)"
    if [[ -z "$python_cmd" ]]; then
        ensure_homebrew_pkg python3.11 python@3.11
        python_cmd="$(choose_python)"
    fi

    if [[ -z "$python_cmd" ]]; then
        echo "No compatible Python 3.10+ interpreter found." >&2
        exit 1
    fi

    log "🐍 Using $python_cmd for BISHOP"

    if ! venv_python_ok; then
        log "🧼 Rebuilding .venv with $python_cmd..."
        rm -rf "$VENV_DIR"
        "$python_cmd" -m venv "$VENV_DIR"
    fi

    "$VENV_DIR/bin/python" -m pip install "${PIP_INSTALL_ARGS[@]}" --upgrade pip setuptools wheel
    "$VENV_DIR/bin/pip" install "${PIP_INSTALL_ARGS[@]}" -r requirements_local.txt
}

ensure_node_env() {
    ensure_homebrew_pkg node node
    ensure_homebrew_pkg npm node

    if [[ ! -d "$UI_DIR/node_modules" ]]; then
        log "📦 Installing dashboard dependencies..."
        (cd "$UI_DIR" && npm install "${NPM_INSTALL_ARGS[@]}")
    else
        log "📦 Refreshing dashboard dependencies..."
        (cd "$UI_DIR" && npm install "${NPM_INSTALL_ARGS[@]}")
    fi
}

ensure_env_files() {
    if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
        log "📝 Writing starter .env..."
        "$VENV_DIR/bin/python" scripts/bishop_onboard.py init-env
    fi

    if [[ ! -f "$UI_DIR/.env.local" && -f "$UI_DIR/.env.example" ]]; then
        cp "$UI_DIR/.env.example" "$UI_DIR/.env.local"
        log "📝 Wrote upscrolled-pulse/.env.local from template"
    fi
}

run_smoke_checks() {
    log "🧪 Running import smoke checks..."
    "$VENV_DIR/bin/python" - <<'PY'
import app
import local_worker
print("python_imports_ok")
PY

    log "🧪 Running dashboard build check..."
    (cd "$UI_DIR" && npm run build >/dev/null)
}

print_banner
log "Installing BISHOP local dependencies..."
ensure_homebrew_pkg redis-server redis
ensure_python_env
ensure_node_env
ensure_env_files
ensure_redis_running
run_smoke_checks

if [[ "$ENSURE_ONLY" -eq 1 ]]; then
    log "✅ BISHOP local environment is ready."
else
    log "✅ Install complete."
    log "Next steps:"
    log "- Fill Slack tokens in .env if needed"
    log "- Run ./start.sh"
fi
