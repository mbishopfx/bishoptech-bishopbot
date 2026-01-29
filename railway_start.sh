#!/bin/bash

# Railway Entrypoint Script
# Runs both the Slack Listener and the GitHub Monitor in one container.

echo "🚀 Starting BishopBot on Railway..."

# 1. Start the GitHub Monitor in the background
echo "🕵️ Starting GitHub Monitor..."
python github_monitor_worker.py &

# 2. Start the Slack Listener (Master process)
# This process will also run the HTTP health check server on $PORT
echo "📡 Starting Slack Listener..."
python app.py
