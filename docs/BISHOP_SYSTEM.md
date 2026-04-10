# BISHOP System Brief

BISHOP is a local-first operator system that turns Slack and a lightweight dashboard into a command layer for real terminal-based AI work.

It is designed to give a team the practical upside of agent workflows without the cost, opacity, and platform lock-in of heavier hosted agent products.

## Executive Summary

BISHOP lets an operator trigger Gemini or Codex sessions from Slack or a local dashboard, watch the terminal output in real time, continue the same run by replying in-thread, and keep durable context locally through files and SQLite.

Instead of building a giant agent platform, BISHOP focuses on a smaller control plane:

- local runtime control
- visible terminal execution
- Slack-native collaboration
- one queue and one worker path
- portable local memory and environment awareness

That makes it cheaper to run, easier to inspect, and faster to modify.

## What BISHOP Actually Does

At a high level, BISHOP does five jobs:

1. Accepts work from Slack slash commands or the dashboard UI.
2. Queues the job through Redis/RQ.
3. Opens a real local terminal session and launches the requested runtime.
4. Streams session output and status back into Slack or the dashboard.
5. Maintains durable context about the environment, prior sessions, and reusable notes.

This means the system is not pretending to be an agent platform. It is an orchestration layer around real CLI tools that already work.

## Core Powers

### 1. Slack-Controlled AI Sessions

Users can trigger runtime work from Slack with commands like:

```text
/cli inspect the listener and fix the failure
/codex scaffold a route and summarize the changes
/cli runtime:codex --yolo investigate the auth bug
```

BISHOP turns those into structured jobs and routes them into the same local execution system every time.

### 2. Real Terminal Sessions

BISHOP does not fake execution in a hidden service.

It opens actual macOS Terminal sessions, launches Gemini or Codex using their native CLI modes, and monitors the terminal state and captured output.

That gives the operator:

- visibility into what is happening
- a real shell environment
- compatibility with local tools, files, and credentials
- lower cost than moving everything through a hosted orchestration layer

### 3. Thread-Based Session Continuation in Slack

Each session keeps one Slack thread.

The first status message becomes the thread root. All later updates stay in that same thread. If a user replies in the thread, BISHOP sends that reply back into the active terminal session.

That creates a clean operational loop:

- start a run
- watch progress
- answer questions or redirect the run
- keep the full context in one thread

### 4. Dashboard Control Plane

BISHOP includes a local Next.js dashboard at `http://localhost:3113`.

The dashboard is not a separate execution engine. It uses the same worker path as Slack, which keeps the system simpler and more reliable.

The dashboard provides:

- launch controls for `/cli` and `/codex`
- session inspection
- output tails and log excerpts
- follow-up input into active sessions
- durable memory and path visibility
- queue and status awareness

### 5. Durable Context and Local Memory

BISHOP keeps a lightweight memory layer in:

- `agent-context/vibes.md`
- `agent-context/memory.sqlite`
- generated `agent-context/vibes-full.md`

This gives the runtimes awareness of:

- important local directories
- stable operator guidance
- reusable notes
- prior session metadata
- Hermes and OpenClaw-adjacent paths

BISHOP does not need a large hosted memory system to be useful. SQLite is enough for operational memory, session history, and durable notes.

## Why This Matters

Most agent products try to do everything inside their own platform.

BISHOP takes the opposite approach:

- keep the control plane small
- keep the execution local
- keep the state inspectable
- keep the system hackable

That has practical advantages.

### Lower Cost

BISHOP uses local CLIs and your existing machine instead of adding another full hosted orchestration bill.

### Better Visibility

The work is happening in real terminals, with logs, state files, and thread history. Operators can see what happened instead of trusting a black box.

### Faster Iteration

Because the orchestration layer is relatively small, new capabilities can be added quickly:

- new runtime adapters
- new dashboard panels
- new Slack flows
- new memory behaviors
- new local integrations

### Easier Team Adoption

The interface is familiar:

- Slack for requests
- a dashboard for control
- a terminal for execution

That makes it much easier to explain and demo to a team than a fully abstract agent stack.

## Architecture

### Control Surfaces

- Slack slash commands
- Slack thread replies
- Local dashboard UI

### Execution Layer

- Redis queue
- local RQ worker
- runtime adapters for Gemini and Codex
- macOS Terminal session management

### Context Layer

- `vibes.md` for durable operating guidance
- `vibes-full.md` for a compact environment map
- `memory.sqlite` for resources, notes, and session lifecycle

### Monitoring Layer

- session state files
- session output capture
- runtime logs
- Slack thread updates
- dashboard polling

## Primary Components

- [app.py](/Users/matthewbishop/BishopBot/app.py)
  Slack listener and local HTTP gateway.
- [local_worker.py](/Users/matthewbishop/BishopBot/local_worker.py)
  Queue worker that executes command jobs and session follow-ups.
- [services/terminal_session_manager.py](/Users/matthewbishop/BishopBot/services/terminal_session_manager.py)
  Runtime session lifecycle, polling, Slack updates, and recovery logic.
- [services/runtime_adapters.py](/Users/matthewbishop/BishopBot/services/runtime_adapters.py)
  Runtime-specific boot and prompt rules for Gemini and Codex.
- [services/agent_context_service.py](/Users/matthewbishop/BishopBot/services/agent_context_service.py)
  Durable context, resource indexing, and SQLite-backed session memory.
- [services/dashboard_service.py](/Users/matthewbishop/BishopBot/services/dashboard_service.py)
  Dashboard read models and queue-backed actions.
- [upscrolled-pulse/app/dashboard-shell.tsx](/Users/matthewbishop/BishopBot/upscrolled-pulse/app/dashboard-shell.tsx)
  Operator dashboard UI.

## Session Lifecycle

This is the normal BISHOP runtime flow:

1. A user sends `/cli` or `/codex` from Slack, or triggers the same action from the dashboard.
2. BISHOP refines the request and builds a runtime prompt.
3. The local worker opens a terminal session.
4. BISHOP launches the chosen runtime.
5. For Gemini-style stdin flows, BISHOP waits for boot, sends the prompt, then submits it.
6. BISHOP polls the session, captures output, and posts updates back to Slack.
7. If the user replies in the Slack thread, BISHOP forwards the new input into the same live session.
8. When the session completes, BISHOP stores the final summary and lifecycle state in SQLite.

## Runtime Awareness

BISHOP currently understands different runtime behaviors instead of treating all CLIs the same.

### Gemini

- commonly launched with `gemini --yolo`
- uses a shell-first interactive flow
- supports delayed prompt injection and follow-up input

### Codex

- can run in direct `argv` modes like `exec --full-auto`
- supports shell and full-auto variants
- can be integrated into the same queue and monitoring model

This adapter model is important because different runtimes need different launch logic.

## Hermes and OpenClaw Relationship

BISHOP is not trying to replace Hermes or OpenClaw line-for-line.

It is a lighter orchestration layer that can understand where those systems live and route work around them.

That means BISHOP can:

- know where Hermes files and sessions live
- know where OpenClaw memory and cron-related artifacts live
- reference OpenClaw `soul.md` if it exists
- reason from local skills and environment structure

This is useful because it lets a session act with more context than a blank CLI prompt, without hard-coupling BISHOP to a single agent system.

## Why It Is a Good Alternative

For a team, the value proposition is straightforward.

BISHOP is:

- lighter than full hosted agent platforms
- cheaper to operate
- easier to inspect
- easier to extend
- better aligned with local tools and workflows

It is especially useful if the team already trusts terminal-based tools and wants a clean way to operationalize them through Slack and a dashboard.

## Current Team Use Cases

BISHOP is already well-suited for:

- engineering triage
- repo inspection and patching
- local ops work
- dashboard-driven operator workflows
- Slack-native AI task execution
- human-in-the-loop agent sessions
- lightweight multi-agent environment awareness

## What Makes It Powerful

The power is not in one big feature. It is in the combination:

- local execution
- thread continuation
- durable memory
- path awareness
- one worker path
- UI plus Slack parity

That combination gives the team a practical operator system, not just a chatbot.

## How To Demo It

If you are showing BISHOP to the team, the best flow is:

1. Start the stack with `./start.sh`.
2. Show the dashboard on `localhost:3113`.
3. Trigger a `/cli` task from Slack.
4. Show the session thread updating live.
5. Reply in the thread to continue the same session.
6. Open the dashboard and show the same session state, logs, and memory.
7. Explain that the entire workflow is local-first and queue-backed.

That makes the system’s value obvious very quickly.

## One-Line Positioning

BISHOP is a lightweight local-first AI operator that gives teams Slack-triggered terminal automation, durable context, and a live control dashboard without the cost and complexity of a heavy hosted agent platform.
