#!/bin/bash

# BISHOP Startup Script
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="$SCRIPT_DIR/.venv/bin/python"
PYTHON_BIN="python3"

if [[ -x "$VENV_PY" ]]; then
    PYTHON_BIN="$VENV_PY"
    echo "🐍 Using project venv: $VENV_PY"
else
    echo "⚠️  Project venv not found at .venv; falling back to python3"
fi

echo "🤖 Starting BISHOP Local Environment..."

# Function to stop background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down BISHOP processes..."
    # Kill all background jobs started by this script
    pkill -P $$
    exit
}

trap cleanup SIGINT

# 1. Start the Local Worker (The Core)
echo "⚙️  Starting Local Worker (Task execution + Knowledge Refresh)..."
"$PYTHON_BIN" local_worker.py &
WORKER_PID=$!

# Give it a few seconds to initialize and print warnings
sleep 5

# 2. Ask if user wants to run the listener or monitor locally
echo ""
echo "-------------------------------------------------------"
echo "RAILWAY: Runs your Slack Listener (app.py) and GitHub Monitor."
echo "LOCAL: Runs the Worker (local_worker.py) to execute CLI/Google tasks."
echo "-------------------------------------------------------"

# Clear any accidental keystrokes from the buffer
read -t 1 -n 10000 discard

read -p "❓ Start Listener (app.py: Slack Socket Mode + HTTP gateway/WhatsApp) locally? [y/N] " run_app
if [[ "$run_app" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "📡 Starting Local Listener..."
    "$PYTHON_BIN" app.py &
fi

read -p "❓ Start GitHub Monitor locally? [y/N] " run_monitor
if [[ "$run_monitor" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "🕵️  Starting GitHub Monitor..."
    "$PYTHON_BIN" github_monitor_worker.py &
fi

echo ""
echo "🚀 BISHOP is active. Logs will appear below."
echo "📌 Press Ctrl+C to stop ALL processes safely."
echo "-------------------------------------------------------"

# caffeinate keeps the system from sleep while the worker is active
# The -w flag waits for the specific worker PID to exit
echo "☕ System sleep prevention active for Worker PID: $WORKER_PID..."
caffeinate -is -w $WORKER_PID
