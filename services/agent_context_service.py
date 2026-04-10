from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from config import CONFIG


MAX_VIBES_CHARS = 4000
MAX_NOTE_CHARS = 1200
MAX_NOTES = 6


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _project_root() -> Path:
    return Path(CONFIG.get("PROJECT_ROOT_DIR") or ".").expanduser().resolve()


def context_root() -> Path:
    root = _project_root() / "agent-context"
    root.mkdir(parents=True, exist_ok=True)
    return root


def vibes_path() -> Path:
    return context_root() / "vibes.md"


def memory_db_path() -> Path:
    return context_root() / "memory.sqlite"


def memory_script_path() -> Path:
    return _project_root() / "scripts" / "agent_memory.py"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(memory_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS resources (
            key TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            path TEXT NOT NULL,
            description TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'seed',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            runtime TEXT,
            launch_mode TEXT,
            user_id TEXT,
            response_target TEXT,
            status TEXT NOT NULL,
            original_request TEXT,
            refined_request TEXT,
            plan_text TEXT,
            final_summary TEXT,
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL DEFAULT 'durable',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            session_id TEXT,
            pinned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def _seeded_resources() -> list[tuple[str, str, str, str, str, str]]:
    user_home = Path("/Users/matthewbishop")
    hermes_home = user_home / ".hermes"
    openclaw_home = user_home / ".openclaw"
    agents_home = user_home / ".agents"
    gemini_home = user_home / ".gemini"
    root = _project_root()
    now = _utc_now()
    return [
        ("bishopbot_project", "project", str(root), "BishopBot project root.", "seed", now),
        ("bishopbot_vibes", "context", str(vibes_path()), "Durable operator guidance for BishopBot-driven Gemini/Codex sessions.", "seed", now),
        ("bishopbot_memory_db", "context", str(memory_db_path()), "SQLite database for session tracking, durable notes, and known resource paths.", "seed", now),
        ("bishopbot_memory_script", "tool", str(memory_script_path()), "Helper CLI for viewing resources and writing durable notes into the memory DB.", "seed", now),
        ("hermes_home", "external", str(hermes_home), "Hermes home directory.", "seed", now),
        ("hermes_config", "external", str(hermes_home / "config.yaml"), "Hermes runtime configuration.", "seed", now),
        ("hermes_state_db", "external", str(hermes_home / "state.db"), "Hermes SQLite state database.", "seed", now),
        ("hermes_sessions", "external", str(hermes_home / "sessions"), "Hermes session and cron session artifacts.", "seed", now),
        ("openclaw_home", "external", str(openclaw_home), "OpenClaw home directory.", "seed", now),
        ("openclaw_runs_db", "external", str(openclaw_home / "tasks" / "runs.sqlite"), "OpenClaw run tracking database.", "seed", now),
        ("openclaw_memory", "external", str(openclaw_home / "workspace" / "memory"), "OpenClaw memory markdown directory.", "seed", now),
        ("openclaw_workspace", "external", str(openclaw_home / "workspace"), "OpenClaw main workspace.", "seed", now),
        ("openclaw_scripts", "external", str(openclaw_home / "workspace" / "scripts"), "OpenClaw helper scripts and cron-related utilities.", "seed", now),
        ("agents_skills", "external", str(agents_home / "skills"), "Shared Codex/Gemini skills directory.", "seed", now),
        ("gemini_skills", "external", str(gemini_home / "skills"), "Gemini-specific skill directory.", "seed", now),
    ]


def _seed_resources(conn: sqlite3.Connection):
    conn.executemany(
        """
        INSERT INTO resources (key, category, path, description, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            category = excluded.category,
            path = excluded.path,
            description = excluded.description,
            source = excluded.source,
            updated_at = excluded.updated_at
        """,
        _seeded_resources(),
    )


def _ensure_vibes_file():
    path = vibes_path()
    if path.exists():
        return
    path.write_text(
        """# BishopBot Vibes

## Purpose
- BishopBot sessions should act like a pragmatic local operator for Matthew's environment.
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
""",
        encoding="utf-8",
    )


def ensure_context_assets():
    context_root()
    _ensure_vibes_file()
    with _connect() as conn:
        _ensure_schema(conn)
        _seed_resources(conn)


def _read_vibes_excerpt() -> str:
    text = vibes_path().read_text(encoding="utf-8")
    return text[:MAX_VIBES_CHARS].strip()


def _recent_notes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT kind, title, content, session_id, updated_at
        FROM notes
        ORDER BY pinned DESC, updated_at DESC, id DESC
        LIMIT ?
        """,
        (MAX_NOTES,),
    ).fetchall()


def _resource_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT category, key, path, description
        FROM resources
        ORDER BY
            CASE category
                WHEN 'project' THEN 1
                WHEN 'context' THEN 2
                WHEN 'tool' THEN 3
                ELSE 4
            END,
            key
        """
    ).fetchall()


def build_prompt_context() -> str:
    ensure_context_assets()
    with _connect() as conn:
        resources = _resource_rows(conn)
        notes = _recent_notes(conn)

    resource_lines = "\n".join(
        f"- {row['key']}: `{row['path']}` ({row['description']})"
        for row in resources
    )
    note_lines = "\n".join(
        f"- [{row['kind']}] {row['title']}: {row['content'][:MAX_NOTE_CHARS]}"
        for row in notes
    ) or "- No durable notes yet."

    return (
        "Persistent operator context is available for this session.\n"
        f"- Vibes file: `{vibes_path()}`\n"
        f"- Memory DB: `{memory_db_path()}`\n"
        f"- Memory helper: `{memory_script_path()}`\n\n"
        "Known resource index:\n"
        f"{resource_lines}\n\n"
        "Current vibes.md excerpt:\n"
        f"{_read_vibes_excerpt()}\n\n"
        "Recent durable notes:\n"
        f"{note_lines}\n\n"
        "Use this context when relevant. At the end of the task, update `vibes.md` only for stable guidance changes and add a durable note to the memory DB only when the new fact will help future sessions."
    )


def record_session_start(
    session_id: str,
    *,
    runtime: str,
    launch_mode: str | None,
    user_id: str | None,
    response_target: str | None,
    original_request: str | None,
    refined_request: str | None,
    plan_text: str | None,
):
    ensure_context_assets()
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                session_id, runtime, launch_mode, user_id, response_target, status,
                original_request, refined_request, plan_text, started_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                runtime = excluded.runtime,
                launch_mode = excluded.launch_mode,
                user_id = excluded.user_id,
                response_target = excluded.response_target,
                status = excluded.status,
                original_request = excluded.original_request,
                refined_request = excluded.refined_request,
                plan_text = excluded.plan_text,
                updated_at = excluded.updated_at
            """,
            (
                session_id,
                runtime,
                launch_mode,
                user_id,
                response_target,
                "running",
                original_request,
                refined_request,
                plan_text,
                now,
                now,
            ),
        )


def update_session_status(session_id: str, *, status: str, response_target: str | None = None, final_summary: str | None = None):
    ensure_context_assets()
    now = _utc_now()
    completed_at = now if status in {"completed", "closed", "timed_out", "attention_needed"} else None
    with _connect() as conn:
        conn.execute(
            """
            UPDATE sessions
            SET status = ?,
                response_target = COALESCE(?, response_target),
                final_summary = COALESCE(?, final_summary),
                updated_at = ?,
                completed_at = COALESCE(?, completed_at)
            WHERE session_id = ?
            """,
            (status, response_target, final_summary, now, completed_at, session_id),
        )


def add_note(title: str, content: str, *, kind: str = "durable", session_id: str | None = None, pinned: bool = False):
    ensure_context_assets()
    now = _utc_now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO notes (kind, title, content, session_id, pinned, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (kind, title.strip(), content.strip(), session_id, 1 if pinned else 0, now, now),
        )


def list_resources() -> list[dict]:
    ensure_context_assets()
    with _connect() as conn:
        rows = _resource_rows(conn)
    return [dict(row) for row in rows]


def list_recent_notes() -> list[dict]:
    ensure_context_assets()
    with _connect() as conn:
        rows = _recent_notes(conn)
    return [dict(row) for row in rows]
