# BishopBot Vibes

## Purpose
- BishopBot sessions should operate like a pragmatic local operator for Matthew's environment.
- Prefer reading the repo, skills, and known system folders before guessing.

## Durable Rules
- Update this file only for stable, high-signal guidance that should affect future sessions.
- Do not store secrets here.
- Record durable notes in the memory DB when you discover a reusable fact, workflow, or important location.

## Important Systems
- Hermes home: `/Users/matthewbishop/.hermes`
- OpenClaw home: `/Users/matthewbishop/.openclaw`
- Shared skills: `/Users/matthewbishop/.agents/skills`
- Gemini skills: `/Users/matthewbishop/.gemini/skills`

## Memory Policy
- The SQLite DB at `agent-context/memory.sqlite` automatically tracks BishopBot session lifecycle.
- Add note rows only for durable facts or operational guidance worth reusing.

## Current Guidance
- Keep prompts compact and operational.
- When a task references Hermes or OpenClaw, inspect their real files before making assumptions.
