#!/bin/bash

# BishopBot Startup Script
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

echo "🤖 Starting BishopBot Local Environment..."

# Function to stop background processes on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down BishopBot processes..."
    # Kill all background jobs started by this script
    pkill -P $$
    exit
}

trap cleanup SIGINT

# 1. Start the Local Worker (The Core)
echo "⚙️  Starting Local Worker (Task execution + Knowledge Refresh)..."
python3 local_worker.py &
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

read -p "❓ Start Slack Listener (app.py) locally? [y/N] " run_app
if [[ "$run_app" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "📡 Starting Local Slack Listener..."
    python3 app.py &
fi

read -p "❓ Start GitHub Monitor locally? [y/N] " run_monitor
if [[ "$run_monitor" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "🕵️  Starting GitHub Monitor..."
    python3 github_monitor_worker.py &
fi

echo ""
echo "🚀 BishopBot is active! Logs will appear below."
echo "📌 Press Ctrl+C to stop ALL processes safely."
echo "-------------------------------------------------------"

# Wait for the worker to finish (it won't, until Ctrl+C)
# caffeinate keeps the system from sleeping while the worker is active
echo "☕ System sleep prevention active..."
caffeinate -is wait $WORKER_PID
