from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from config import CONFIG
from services import mcp_registry_service


MAX_VIBES_CHARS = 4000
MAX_NOTE_CHARS = 1200
MAX_NOTES = 6
MAX_CONTEXT_NOTES = 3


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


def vibes_full_path() -> Path:
    return context_root() / "vibes-full.md"


def memory_db_path() -> Path:
    return context_root() / "memory.sqlite"


def memory_script_path() -> Path:
    return _project_root() / "scripts" / "agent_memory.py"


def mcp_registry_path() -> Path:
    return mcp_registry_service.registry_path()


def mcp_catalog_snapshot_path() -> Path:
    return mcp_registry_service.catalog_snapshot_path()


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
    hermes_home = Path(str(CONFIG.get("HERMES_HOME") or "~/.hermes")).expanduser()
    openclaw_home = Path(str(CONFIG.get("OPENCLAW_HOME") or "~/.openclaw")).expanduser()
    shared_skills_dir = Path(str(CONFIG.get("SHARED_SKILLS_DIR") or "~/.agents/skills")).expanduser()
    gemini_skills_dir = Path(str(CONFIG.get("GEMINI_SKILLS_DIR") or "~/.gemini/skills")).expanduser()
    openclaw_soul = _openclaw_soul_path()
    root = _project_root()
    now = _utc_now()
    rows = [
        ("bishopbot_project", "project", str(root), "BishopBot project root.", "seed", now),
        ("bishopbot_vibes", "context", str(vibes_path()), "Durable operator guidance for BishopBot-driven Gemini/Codex sessions.", "seed", now),
        ("bishopbot_vibes_full", "context", str(vibes_full_path()), "Generated environment map used to keep runtime prompts compact.", "seed", now),
        ("bishopbot_memory_db", "context", str(memory_db_path()), "SQLite database for session tracking, durable notes, and known resource paths.", "seed", now),
        ("bishopbot_memory_script", "tool", str(memory_script_path()), "Helper CLI for viewing resources and writing durable notes into the memory DB.", "seed", now),
        ("bishopbot_mcp_registry", "context", str(mcp_registry_path()), "Curated BISHOP MCP registry with placeholders and enable flags.", "seed", now),
        ("bishopbot_mcp_catalog_snapshot", "context", str(mcp_catalog_snapshot_path()), "Generated searchable snapshot of the external MCP catalog repo.", "seed", now),
        ("bishopbot_gemini_settings", "context", str(mcp_registry_service.gemini_settings_path()), "Project Gemini settings file used for MCP server activation.", "seed", now),
        ("hermes_home", "external", str(hermes_home), "Hermes home directory.", "seed", now),
        ("hermes_config", "external", str(hermes_home / "config.yaml"), "Hermes runtime configuration.", "seed", now),
        ("hermes_state_db", "external", str(hermes_home / "state.db"), "Hermes SQLite state database.", "seed", now),
        ("hermes_sessions", "external", str(hermes_home / "sessions"), "Hermes session and cron session artifacts.", "seed", now),
        ("openclaw_home", "external", str(openclaw_home), "OpenClaw home directory.", "seed", now),
        ("openclaw_runs_db", "external", str(openclaw_home / "tasks" / "runs.sqlite"), "OpenClaw run tracking database.", "seed", now),
        ("openclaw_memory", "external", str(openclaw_home / "workspace" / "memory"), "OpenClaw memory markdown directory.", "seed", now),
        ("openclaw_workspace", "external", str(openclaw_home / "workspace"), "OpenClaw main workspace.", "seed", now),
        ("openclaw_scripts", "external", str(openclaw_home / "workspace" / "scripts"), "OpenClaw helper scripts and cron-related utilities.", "seed", now),
        ("agents_skills", "external", str(shared_skills_dir), "Shared Codex/Gemini skills directory.", "seed", now),
        ("gemini_skills", "external", str(gemini_skills_dir), "Gemini-specific skill directory.", "seed", now),
    ]
    if openclaw_soul:
        rows.append(("openclaw_soul", "external", openclaw_soul, "Optional OpenClaw tone file.", "seed", now))
    if mcp_registry_service.catalog_repo_path().exists():
        rows.append(("bishopbot_mcp_catalog_repo", "external", str(mcp_registry_service.catalog_repo_path()), "External BishopTech API/MCP source catalog repo.", "seed", now))
    if mcp_registry_service.project_gemini_md_path().exists():
        rows.append(("bishopbot_gemini_md", "context", str(mcp_registry_service.project_gemini_md_path()), "Project-level GEMINI.md instructions for the current repo.", "seed", now))
    return rows


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
    hermes_home = Path(str(CONFIG.get("HERMES_HOME") or "~/.hermes")).expanduser()
    openclaw_home = Path(str(CONFIG.get("OPENCLAW_HOME") or "~/.openclaw")).expanduser()
    shared_skills_dir = Path(str(CONFIG.get("SHARED_SKILLS_DIR") or "~/.agents/skills")).expanduser()
    gemini_skills_dir = Path(str(CONFIG.get("GEMINI_SKILLS_DIR") or "~/.gemini/skills")).expanduser()
    path.write_text(
        f"""# BishopBot Vibes

## Purpose
- BishopBot sessions should act like a pragmatic local operator for Matthew's environment.
- Prefer reading the repo, skills, and known system folders before guessing.

## Durable Rules
- Update this file only for stable, high-signal guidance that should affect future sessions.
- Do not store secrets here.
- Record durable notes in the memory DB when you discover a reusable fact, workflow, or important location.

## Important Systems
- Hermes home: `{hermes_home}`
- OpenClaw home: `{openclaw_home}`
- Shared skills: `{shared_skills_dir}`
- Gemini skills: `{gemini_skills_dir}`

## Memory Policy
- The SQLite DB at `agent-context/memory.sqlite` automatically tracks BishopBot session lifecycle.
- Add note rows only for durable facts or operational guidance worth reusing.

## Current Guidance
- Keep prompts compact and operational.
- When a task references Hermes or OpenClaw, inspect their real files before making assumptions.
""",
        encoding="utf-8",
    )


def _openclaw_soul_path() -> str | None:
    openclaw_home = Path(str(CONFIG.get("OPENCLAW_HOME") or "~/.openclaw")).expanduser()
    candidates = (
        openclaw_home / "workspace" / "soul.md",
        openclaw_home / "soul.md",
    )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _render_vibes_full(resources: Iterable[sqlite3.Row], notes: Iterable[sqlite3.Row]) -> str:
    resource_lines = "\n".join(
        f"- {row['key']}: {row['path']} | {row['description']}"
        for row in resources
    ) or "- No indexed resources yet."
    note_lines = "\n".join(
        f"- {row['title']}: {row['content'][:MAX_NOTE_CHARS]}"
        for row in notes
    ) or "- No durable notes yet."
    soul_path = _openclaw_soul_path() or "null"

    return (
        "# BISHOP Vibes Full\n\n"
        "This file is the compact environment map for Gemini and Codex sessions.\n"
        "Read it when you need routes, durable memory locations, or nearby agent-system context.\n\n"
        "## Primary Files\n"
        f"- Vibes: {vibes_path()}\n"
        f"- Memory DB: {memory_db_path()}\n"
        f"- Memory helper: {memory_script_path()}\n"
        f"- OpenClaw soul: {soul_path}\n\n"
        "## Route Map\n"
        f"{resource_lines}\n\n"
        "## Durable Notes\n"
        f"{note_lines}\n\n"
        "## Policy\n"
        "- Use `vibes.md` for stable behavioral guidance.\n"
        "- Use the SQLite memory only for reusable facts.\n"
        "- If `OpenClaw soul` is `null`, do not assume it exists.\n"
    )


def _refresh_vibes_full(resources: Iterable[sqlite3.Row], notes: Iterable[sqlite3.Row]) -> None:
    vibes_full_path().write_text(_render_vibes_full(resources, notes), encoding="utf-8")


def ensure_context_assets():
    context_root()
    _ensure_vibes_file()
    mcp_registry_service.ensure_registry_files()
    with _connect() as conn:
        _ensure_schema(conn)
        _seed_resources(conn)
        _refresh_vibes_full(_resource_rows(conn), _recent_notes(conn))


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
        notes = _recent_notes(conn)[:MAX_CONTEXT_NOTES]
    _refresh_vibes_full(resources, notes)
    note_lines = "\n".join(
        f"- {row['title']}: {row['content'][:MAX_NOTE_CHARS]}"
        for row in notes
    ) or "- No durable notes yet."
    soul_path = _openclaw_soul_path() or "null"
    mcp_summary = mcp_registry_service.registry_summary()

    return (
        "Persistent operator context is available for this session.\n"
        f"- Read `{vibes_full_path()}` for the environment map and route overview.\n"
        f"- Core vibes live in `{vibes_path()}`.\n"
        f"- Memory DB: `{memory_db_path()}`\n"
        f"- Memory helper: `{memory_script_path()}`\n"
        f"- MCP registry: `{mcp_registry_path()}`\n"
        f"- MCP catalog snapshot: `{mcp_catalog_snapshot_path()}`\n"
        f"- Project Gemini settings: `{mcp_registry_service.gemini_settings_path()}`\n"
        f"- Project GEMINI.md: `{mcp_registry_service.project_gemini_md_path()}`\n"
        f"- OpenClaw soul reference: `{soul_path}`\n\n"
        "MCP state:\n"
        f"- Catalog repo: `{mcp_summary['catalog_source_dir']}`\n"
        f"- Catalog entries: {mcp_summary['catalog_mcp_count']}\n"
        f"- Enabled project MCP servers: {mcp_summary['enabled_server_count']}\n\n"
        "Current vibes.md excerpt:\n"
        f"{_read_vibes_excerpt()}\n\n"
        "Recent durable notes:\n"
        f"{note_lines}\n\n"
        "Use this context when relevant. If a task needs MCP tools, inspect the MCP registry and project Gemini settings before assuming a server is active. At the end of the task, update `vibes.md` only for stable guidance changes and add a durable note to the memory DB only when the new fact will help future sessions."
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
