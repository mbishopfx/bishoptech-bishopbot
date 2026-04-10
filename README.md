<p align="center">
  <img src="docs/assets/logo.png" alt="BISHOP logo" width="460" />
</p>

<h1 align="center">BISHOP</h1>

<p align="center">
  <strong>Local-first operator platform for terminal-native AI work.</strong>
</p>

<p align="center">
  Slack + Dashboard + Gemini/Codex CLIs + Durable local memory + MCP-aware context
</p>

<p align="center">
  <a href="#quickstart"><strong>Quickstart</strong></a>
  ·
  <a href="docs/BISHOP_SYSTEM.md"><strong>System Brief</strong></a>
  ·
  <a href="docs/BISHOP_USE_CASES.md"><strong>Use Cases</strong></a>
  ·
  <a href="docs/GEMINI_MCP_PROJECTS.md"><strong>Gemini + MCP Docs</strong></a>
</p>

<p align="center">
  <code>@BISHOP</code> for brainstorming
  ·
  <code>/cli</code> for Gemini execution
  ·
  <code>/codex</code> for Codex execution
  ·
  <code>localhost:3113</code> for dashboard control
</p>

---

BISHOP turns Slack and a dashboard into a control plane for real Gemini and Codex CLI sessions while keeping execution on your machine, preserving visible terminal state, and layering in durable memory, queueing, and environment awareness.

It is intentionally lighter than full hosted agent platforms: smaller control plane, lower runtime cost, clearer execution model, and far less platform lock-in.

## At a glance

| Surface | What it does |
| --- | --- |
| Slack | Start sessions, monitor progress, and continue work inside one thread |
| Dashboard | Launch commands, inspect sessions, read logs, and send follow-ups |
| Terminal | Run real Gemini and Codex CLI sessions locally |
| Memory | Keep durable context in `GEMINI.md`, `vibes.md`, and SQLite |
| MCP layer | Enable project MCP servers only when they are actually needed |

## Core loop

1. Trigger work from Slack or the dashboard.
2. Queue it through Redis/RQ.
3. Launch the real runtime in Terminal.
4. Stream output back to Slack and the dashboard.
5. Continue the same run with thread replies or follow-up input.
6. Preserve durable context locally for future sessions.

## Platform summary

BISHOP is best understood as four layers working together:

- Control surfaces: Slack commands, Slack thread replies, and the local dashboard UI.
- Orchestration: Redis/RQ queueing, request refinement, runtime planning, and session routing.
- Execution: real Gemini and Codex CLI sessions inside Terminal.
- Context: `GEMINI.md`, `agent-context/vibes.md`, `agent-context/vibes-full.md`, and `agent-context/memory.sqlite`.

The product value is not that it invents a new model runtime. The value is that it makes existing runtimes operational: startable from Slack, observable in one thread, steerable mid-run, and grounded in local context and files.

## What BISHOP does

- Starts real local terminal sessions from Slack or the dashboard.
- Launches Gemini or Codex in runtime-specific modes such as `gemini --yolo` and `codex exec --full-auto`.
- Streams runtime output and status back into Slack threads and the dashboard session view.
- Lets operators continue the same run by replying in Slack or sending follow-up input from the dashboard.
- Maintains durable local context with `GEMINI.md`, `agent-context/vibes.md`, and `agent-context/memory.sqlite`.
- Indexes important system paths like Hermes, OpenClaw, skill directories, logs, and MCP registry files so runtimes reason from actual files instead of guesses.
- Provides a curated MCP registry and project Gemini settings workflow without forcing MCP usage on every task.

## What makes it different

- Local-first execution: work runs in real terminals on your machine, not inside a hidden hosted agent runtime.
- One worker path: Slack and the dashboard both enqueue into the same Redis/RQ flow, which reduces drift and debugging complexity.
- Thread-native collaboration: one session maps to one Slack thread, so status, follow-ups, and results stay together.
- Small durable memory: SQLite plus a few markdown files is enough to make sessions stateful without introducing a heavy memory platform.
- Thin integration layer: Hermes and OpenClaw stay external systems; BISHOP knows where they live and how to inspect them, but does not try to reimplement them.

## Why use it

Compared with heavier agent platforms, BISHOP is:

- Lower cost: it rides local CLIs and your own machine.
- More transparent: the work happens in visible terminal sessions with logs, state files, and queue history.
- More controllable: you can interrupt, redirect, or continue a session without leaving Slack or the dashboard.
- More hackable: the orchestration layer is small Python plus Slack Bolt, Redis/RQ, Next.js, and AppleScript.
- Easier to extend: you can add paths, prompts, memories, MCP entries, and runtime adapters without rebuilding the whole stack.

## Current architecture

- `app.py`: Slack Socket Mode listener and input routing.
- `local_worker.py`: local RQ worker that launches and controls terminal sessions.
- `services/terminal_session_manager.py`: runtime lifecycle, polling, Slack updates, and status recovery.
- `services/runtime_adapters.py`: Gemini/Codex launch behavior and prompt construction.
- `services/agent_context_service.py`: durable context, seeded resource index, and SQLite session memory.
- `services/dashboard_service.py`: dashboard read models plus queue-backed command and follow-up input dispatch.
- `services/mcp_registry_service.py`: MCP catalog sync, registry curation, and project Gemini settings generation.
- `scripts/agent_memory.py`: helper CLI for reading and writing BISHOP memory.
- `scripts/bishop_onboard.py`: onboarding and environment doctor CLI.
- `upscrolled-pulse/`: Next.js operator dashboard.

## Runtime model

### `@BISHOP`

- lightweight brainstorming and drafting path
- prefers Gemini API when available
- can fall back to local signed-in Gemini CLI and then OpenAI when needed
- does not claim execution

### `/cli`

- default execution path
- launches Gemini in a real Terminal session
- waits for Gemini to become ready before pasting and submitting the request
- keeps the run inside one Slack thread

### `/codex`

- alternate execution path for Codex
- supports `exec --full-auto` and shell-style variants
- uses the same queue, session model, and dashboard visibility as `/cli`

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
- Session flow: open shell, start Gemini, wait for the actual Gemini input prompt, paste the request, submit, stream output
- Repo behavior and stable guidance should live in `GEMINI.md`, not in a giant injected first prompt
- The first runtime message explicitly tells Gemini to follow the project `GEMINI.md`

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
- Uses a left-rail operator layout with throttled polling rather than a separate execution engine.

This keeps the control plane crisp: one worker path, one session model, one durable state layer.

## Persistent context and memory

BISHOP ships with a local context layer:

- `agent-context/vibes.md`
- `agent-context/memory.sqlite`
- `agent-context/vibes-full.md`
- `GEMINI.md`

The runtime prompt now includes:

- compact task/request guidance
- file-based project context from `GEMINI.md`
- the BISHOP memory and environment map when needed
- seeded external paths for Hermes, OpenClaw, and skill directories
- recent durable notes when they are relevant

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

## MCP integration model

BISHOP supports MCPs, but it does not force them into every run.

- `config/mcp_registry.json` is the curated registry.
- `agent-context/mcp_catalog_snapshot.json` is the generated searchable snapshot of the external catalog repo.
- `.gemini/settings.json` is the actual project activation layer for Gemini MCP servers. It is a local generated file and is gitignored.

If `.gemini/settings.json` is missing on a machine, generate it with:

```bash
./scripts/bishop_mcp.py build-gemini
```

Operationally:

- if a server is not enabled in `.gemini/settings.json`, Gemini cannot use it
- if a server is enabled, Gemini can use it when the task actually calls for it
- BISHOP should prefer local repo/files first and only reach for MCP capability when it materially improves the task

## Recommended install flow for a new machine

```bash
git clone <repo-url>
cd BishopBot
./install.sh
./start.sh
```

## Product framing

If you need one sentence for the team:

BISHOP is a lightweight local operator platform that turns Slack and a dashboard into a control plane for real Gemini and Codex terminal sessions, with thread-based collaboration, durable local context, and optional MCP awareness.

## Notes

- Generated local state like `agent-context/memory.sqlite` is gitignored.
- Your `.env`, `token.json`, and other machine-local state should stay uncommitted.
- The branding in this README is `BISHOP`; the underlying runtime identifiers and Slack command names can stay as they are while the project evolves.
