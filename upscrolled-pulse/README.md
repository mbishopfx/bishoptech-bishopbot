# BISHOP Dashboard

This app is the local dashboard for BISHOP.

It is a Next.js control surface that mirrors the same worker flow used by Slack:

- queue `/cli` and `/codex` jobs
- inspect recent sessions and live output tails
- send follow-up input into active terminal sessions
- browse durable memory, logs, and indexed resource paths

## How it fits

The UI does not launch terminals directly.

It proxies requests to the Python HTTP server at `/api/dashboard/*`, and that server enqueues the same RQ jobs the Slack listener uses. That keeps one execution path for both Slack and dashboard traffic.

## Local development

From the repo root, make sure the Python side is running:

```bash
./install.sh
./start.sh
```

If you want to run only the dashboard side manually:

```bash
./.venv/bin/python local_worker.py
./.venv/bin/python app.py
cd upscrolled-pulse
cp .env.example .env.local
npm install
npm run dev:bishop
```

Open [http://localhost:3113](http://localhost:3113).

## Environment

`upscrolled-pulse/.env.local` supports:

```bash
BISHOP_DASHBOARD_API_URL=http://127.0.0.1:8080
BISHOP_DASHBOARD_API_TOKEN=
```

Leave `BISHOP_DASHBOARD_API_TOKEN` empty when the dashboard talks to a localhost API. Set it only when the UI needs to proxy to a non-local backend protected by the same `DASHBOARD_API_TOKEN` value in the root `.env`.

## Design goals

- dark, local-operator UI instead of generic SaaS chrome
- read-heavy session inspection with fast follow-up control
- zero divergence from the Slack execution model
- durable-state awareness through SQLite, session logs, and session state sidecars
