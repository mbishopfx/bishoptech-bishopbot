# BISHOP

BISHOP is a lightweight Slack-controlled local operator for Gemini, Codex, Hermes, and OpenClaw-adjacent workflows.

It is built for people who want the leverage of agent tooling without handing every task to a heavy hosted platform. BISHOP keeps the control plane local, uses the CLIs you already trust, and adds the missing glue: Slack-triggered sessions, terminal monitoring, thread-based replies, durable context, and low-friction memory.

## What BISHOP does

- Opens real local terminal sessions from Slack commands.
- Launches Gemini or Codex in runtime-specific modes like `gemini --yolo` and `codex exec --full-auto`.
- Streams terminal progress back to Slack.
- Keeps each session inside one Slack thread so replies can feed more input into the same terminal run.
- Maintains a local context layer with `agent-context/vibes.md` and `agent-context/memory.sqlite`.
- Indexes important local systems like Hermes, OpenClaw, shared skill folders, and project paths so the runtime can reason from actual files instead of guessing.

## Why use it

Compared with heavier agent platforms, BISHOP is:

- Lower cost: it rides local CLIs and your own machine.
- More transparent: the work happens in visible terminal sessions.
- More hackable: the orchestration layer is small Python plus Slack Bolt, Redis, and AppleScript.
- Easier to extend: you can add paths, prompts, memories, and runtime adapters without rebuilding the whole stack.

## Current architecture

- `app.py`: Slack Socket Mode listener and input routing.
- `local_worker.py`: local RQ worker that launches and controls terminal sessions.
- `services/terminal_session_manager.py`: runtime lifecycle, polling, Slack updates, and status recovery.
- `services/runtime_adapters.py`: Gemini/Codex launch behavior and prompt construction.
- `services/agent_context_service.py`: durable context, seeded resource index, and SQLite session memory.
- `services/dashboard_service.py`: dashboard read models plus queue-backed command and follow-up input dispatch.
- `scripts/agent_memory.py`: helper CLI for reading and writing BISHOP memory.
- `scripts/bishop_onboard.py`: onboarding and environment doctor CLI.

## Quickstart

### 1. Clone

```bash
git clone <repo-url>
cd BishopBot
```

### 2. Install the local stack

```bash
./install.sh
```

`./install.sh` is the one-shot bootstrap command. It will:

- install missing local system dependencies with Homebrew when possible (`python@3.11`, `node`, `redis`)
- rebuild `.venv` with a compatible Python if your current venv is too old
- install Python dependencies from `requirements_local.txt`
- install dashboard dependencies in `upscrolled-pulse`
- create `.env` and `upscrolled-pulse/.env.local` from templates when missing
- start Redis if it is installed but not running
- run import and dashboard build smoke checks

### 3. Generate or inspect `.env`

```bash
./scripts/bishop_onboard.py init-env
```

This writes a starter `.env` using detected defaults for:

- `PROJECT_ROOT_DIR`
- `HERMES_HOME`
- `OPENCLAW_HOME`
- `SHARED_SKILLS_DIR`
- `GEMINI_SKILLS_DIR`

If you need to validate a machine before running anything:

```bash
./scripts/bishop_onboard.py doctor
```

### 4. Fill your secrets in `.env`

At minimum for Slack:

- `SLACK_BOT_TOKEN`
- `SLACK_APP_TOKEN`
- `SLACK_SIGNING_SECRET`

Common optional keys:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `FIRECRAWL_API_KEY`

### 5. Configure your local paths

BISHOP is portable because these paths are now explicit in `.env`:

```bash
PROJECT_ROOT_DIR=/absolute/path/to/your/repo
HERMES_HOME=/Users/your-user/.hermes
OPENCLAW_HOME=/Users/your-user/.openclaw
SHARED_SKILLS_DIR=/Users/your-user/.agents/skills
GEMINI_SKILLS_DIR=/Users/your-user/.gemini/skills
```

If you do not use Hermes or OpenClaw on a machine, you can still point these to where your equivalent files live, or leave the defaults and let the doctor report what is missing.

### 6. Set up Slack

Import or update the app manifest from:

```bash
manifest.json
```

Important capabilities in the manifest:

- Slash commands
- Socket Mode
- `message.*` bot events for thread replies
- `chat:write` scopes and history scopes for thread routing

After importing or updating the manifest, reinstall the Slack app in your workspace.

### 7. Start BISHOP locally

The master command is now:

```bash
./start.sh
```

`./start.sh` now runs `./install.sh --ensure` first by default, then starts the local worker, the Slack listener / local HTTP API, and the dashboard UI in one shot. If any core process crashes on boot, `start.sh` exits with the real failure instead of pretending the stack is healthy.

Default local endpoints:

- Dashboard: `http://localhost:3113`
- Python API: `http://127.0.0.1:8080`

You can also run the parts manually:

```bash
./.venv/bin/python local_worker.py
./.venv/bin/python app.py
```

### 8. Dashboard details

The dashboard lives under `upscrolled-pulse/`. It is a Next.js control surface that proxies into the local Python API and uses the same Redis/RQ worker path as Slack.

```bash
cd upscrolled-pulse
cp .env.example .env.local
npm install
npm run dev:bishop
```

By default the UI expects the Python API at `http://127.0.0.1:8080` and serves on `http://localhost:3113`.

If the UI and API are not both local, set a shared token in both places:

```bash
# root .env
DASHBOARD_API_TOKEN=choose-a-secret

# upscrolled-pulse/.env.local
BISHOP_DASHBOARD_API_TOKEN=choose-a-secret
```

Open [http://localhost:3113](http://localhost:3113) to use the dashboard.

## launchd option

To run the local worker automatically on macOS login:

```bash
./bishop-meta/launchd/install.sh
```

To remove it:

```bash
./bishop-meta/launchd/uninstall.sh
```

## Runtime behavior

### Gemini

- Default launch mode: `--yolo`
- Default prompt transport: `stdin`
- Session flow: open shell, start Gemini, wait for boot, inject prompt, stream output

### Codex

- Default launch mode: `exec --full-auto`
- Default prompt transport: `argv`

## Slack usage

Examples:

```text
/cli inspect the repo and fix the failing listener test
/codex scaffold a new route and summarize the changes
/cli runtime:codex --yolo inspect the auth flow and patch the issue
```

Session behavior:

1. BISHOP posts the initial status as a Slack message.
2. That message becomes the session thread root.
3. All later output stays in that thread.
4. If you reply in the thread, your reply is sent into the active terminal session.

## Dashboard usage

The dashboard mirrors the same local-first operator flow as Slack rather than bypassing it.

- Trigger `/cli` and `/codex` through the same queue and local worker Slack uses.
- Inspect recent sessions, live output tails, log excerpts, and final summaries.
- Send follow-up input into active sessions from the UI.
- Browse durable memory, path inventory, and resource locations for Hermes, OpenClaw, session logs, and the SQLite store.

This keeps the control plane crisp: one worker path, one session model, one durable state layer.

## Persistent context and memory

BISHOP ships with a local context layer:

- `agent-context/vibes.md`
- `agent-context/memory.sqlite`

The runtime prompt now includes:

- the BISHOP vibes file path
- the memory DB path
- the memory helper path
- seeded external paths for Hermes, OpenClaw, and skill directories
- recent durable notes

The session lifecycle is also tracked automatically in SQLite, including:

- session id
- runtime
- launch mode
- original request
- refined request
- final summary
- response target / thread target
- status transitions

To inspect the current context:

```bash
./scripts/agent_memory.py summary
```

To write a durable note manually:

```bash
./scripts/agent_memory.py note --title "Useful path" --content "The OpenClaw cron scripts live under OPENCLAW_HOME/workspace/scripts."
```

## Hermes and OpenClaw integration model

BISHOP does not try to replace Hermes or OpenClaw internals.

Instead, it gives Gemini/Codex enough durable context to:

- know where Hermes and OpenClaw live
- inspect their config, memory, sessions, and script directories
- discover cron-related artifacts and skill folders
- use those systems intelligently when your request implies it

That keeps BISHOP thin and cheap while still making it operationally aware of your broader agent stack.

## Recommended install flow for a new machine

```bash
git clone <repo-url>
cd BishopBot
./install.sh
./start.sh
```

## Notes

- Generated local state like `agent-context/memory.sqlite` is gitignored.
- Your `.env`, `token.json`, and other machine-local state should stay uncommitted.
- The branding in this README is `BISHOP`; the underlying runtime identifiers and Slack command names can stay as they are while the project evolves.
