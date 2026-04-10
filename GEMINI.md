# BISHOP Project Context

## Purpose

- BISHOP is a local-first operator system for Slack-triggered and dashboard-triggered Gemini/Codex terminal sessions.
- The repo combines Slack intake, queue-backed execution, terminal monitoring, local memory, and a Next.js dashboard.

## Key Runtime Files

- `app.py`: Slack listener and local HTTP gateway
- `local_worker.py`: local RQ worker
- `services/terminal_session_manager.py`: runtime session lifecycle
- `services/runtime_adapters.py`: Gemini/Codex runtime behavior
- `services/agent_context_service.py`: local durable context and memory
- `services/mcp_registry_service.py`: MCP catalog, curated registry, and Gemini settings generation
- `upscrolled-pulse/`: dashboard UI

## MCP and Gemini Structure

- `.gemini/settings.json`: active Gemini project settings
- `config/mcp_registry.json`: curated BISHOP MCP registry created by `scripts/bishop_mcp.py init`
- `agent-context/mcp_catalog_snapshot.json`: generated snapshot of the external MCP catalog repo
- `docs/GEMINI_MCP_PROJECTS.md`: usage documentation for project-scoped MCP setup

## Rules

- Prefer the existing services layer over new ad hoc orchestration files.
- Keep prompts compact; use the generated context files and registry paths instead of dumping long route maps inline.
- If a task needs MCP tools, inspect `config/mcp_registry.json` and `.gemini/settings.json` before assuming a server is active.
- Do not invent MCP connection commands. Use placeholders until a real command or URL is known.
- Keep secrets in environment variables, not in committed JSON.

## Verification

- Run targeted pytest coverage for changed backend files.
- If dashboard code changes, run `npm run build` in `upscrolled-pulse`.
- Preserve the one-worker-path model: Slack and dashboard should enqueue the same job flow.
