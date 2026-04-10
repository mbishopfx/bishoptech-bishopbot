#!/bin/bash

# Railway Entrypoint Script
# Runs both the Slack Listener and the GitHub Monitor in one container.

echo "🚀 Starting BishopBot on Railway..."

# 0. Ensure requirements are installed
echo "📦 Installing requirements..."
python3 -m pip install -r requirements.txt

# 1. Start the GitHub Monitor in the background
echo "🕵️ Starting GitHub Monitor..."
python github_monitor_worker.py &

# 2. Start the Slack Listener (Master process)
# This process will also run the HTTP health check server on $PORT
echo "📡 Starting Slack Listener..."
python app.py
