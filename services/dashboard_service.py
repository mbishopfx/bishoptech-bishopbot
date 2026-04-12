from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from config import CONFIG
from handlers import cli_handler
from services import agent_context_service, mcp_registry_service, session_log_service, session_output_service, session_state_service


ACTIVE_STATUSES = {"booting", "running", "waiting_for_input", "attention_needed", "settled"}


def _connect_memory() -> sqlite3.Connection:
    conn = sqlite3.connect(agent_context_service.memory_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _redis_queue() -> Any | None:
    if not CONFIG.get("REDIS_URL"):
        return None
    from redis import Redis
    from rq import Queue

    return Queue(CONFIG["TASK_QUEUE_NAME"], connection=Redis.from_url(CONFIG["REDIS_URL"]))


def _tail_text(text: str, max_lines: int = 24, max_chars: int = 5000) -> str:
    cleaned = (text or "").rstrip()
    if not cleaned:
        return ""
    lines = cleaned.splitlines()[-max_lines:]
    tailed = "\n".join(lines)
    return tailed[-max_chars:]


def _tail_file_text(path: Path, max_lines: int = 24, max_chars: int = 5000) -> str:
    if not path.exists():
        return ""

    max_lines = max(1, int(max_lines))
    max_chars = max(1, int(max_chars))
    chunks: list[bytes] = []
    total_bytes = 0
    newline_count = 0

    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        if position <= 0:
            return ""

        block_size = 8192
        while position > 0 and (newline_count <= max_lines or total_bytes < max_chars):
            read_size = min(block_size, position)
            position -= read_size
            handle.seek(position)
            data = handle.read(read_size)
            if not data:
                break

            chunks.append(data)
            total_bytes += len(data)
            newline_count += data.count(b"\n")

            if total_bytes >= max_chars * 2 and newline_count >= max_lines:
                break

    text = b"".join(reversed(chunks)).decode("utf-8", errors="replace")
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    tail = "\n".join(lines)
    return tail[-max_chars:].rstrip()


def _paths_payload() -> dict[str, str]:
    project_root = str(Path(CONFIG.get("PROJECT_ROOT_DIR") or ".").resolve())
    return {
        "project_root": project_root,
        "memory_db": str(agent_context_service.memory_db_path()),
        "vibes_file": str(agent_context_service.vibes_path()),
        "session_logs": str(session_log_service._log_root()),
        "session_output": str(session_output_service._output_root()),
        "session_state": str(session_state_service._state_root()),
        "hermes_home": str(Path(str(CONFIG.get("HERMES_HOME") or "~/.hermes")).expanduser()),
        "openclaw_home": str(Path(str(CONFIG.get("OPENCLAW_HOME") or "~/.openclaw")).expanduser()),
        "shared_skills_dir": str(Path(str(CONFIG.get("SHARED_SKILLS_DIR") or "~/.agents/skills")).expanduser()),
        "gemini_skills_dir": str(Path(str(CONFIG.get("GEMINI_SKILLS_DIR") or "~/.gemini/skills")).expanduser()),
        "mcp_catalog_dir": str(mcp_registry_service.catalog_repo_path()),
        "mcp_registry": str(mcp_registry_service.registry_path()),
        "gemini_settings": str(mcp_registry_service.gemini_settings_path()),
    }


def _session_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "session_id": row["session_id"],
        "runtime": row["runtime"],
        "launch_mode": row["launch_mode"],
        "user_id": row["user_id"],
        "status": row["status"],
        "ops_phase": row["ops_phase"],
        "ops_phase_reason": row["ops_phase_reason"],
        "ops_phase_risk": row["ops_phase_risk"],
        "ops_phase_next_expected": row["ops_phase_next_expected"],
        "original_request": row["original_request"],
        "refined_request": row["refined_request"],
        "plan_text": row["plan_text"],
        "final_summary": row["final_summary"],
        "started_at": row["started_at"],
        "updated_at": row["updated_at"],
        "completed_at": row["completed_at"],
        "response_target": row["response_target"],
    }


def list_sessions(limit: int = 20) -> list[dict[str, Any]]:
    agent_context_service.ensure_context_assets()
    with _connect_memory() as conn:
        rows = conn.execute(
            """
            SELECT session_id, runtime, launch_mode, user_id, status, ops_phase,
                   ops_phase_reason, ops_phase_risk, ops_phase_next_expected,
                   original_request, refined_request, plan_text, final_summary, started_at, updated_at,
                   completed_at, response_target
            FROM sessions
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_session_row_to_dict(row) for row in rows]


def get_session(session_id: str) -> dict[str, Any] | None:
    agent_context_service.ensure_context_assets()
    with _connect_memory() as conn:
        row = conn.execute(
            """
            SELECT session_id, runtime, launch_mode, user_id, status, ops_phase,
                   ops_phase_reason, ops_phase_risk, ops_phase_next_expected,
                   original_request, refined_request, plan_text, final_summary, started_at, updated_at,
                   completed_at, response_target
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
    if not row:
        return None

    session = _session_row_to_dict(row)
    session["state"] = session_state_service.parse_session_state(session_id)
    session["output_tail"] = _tail_file_text(session_output_service.session_output_path(session_id), max_lines=40)
    log_path = session_log_service.session_log_path(session_id)
    session["log_path"] = str(log_path)
    session["log_excerpt"] = _tail_file_text(log_path, max_lines=48)
    return session


def list_resources() -> list[dict[str, Any]]:
    return agent_context_service.list_resources()


def list_notes() -> list[dict[str, Any]]:
    return agent_context_service.list_recent_notes()


def overview() -> dict[str, Any]:
    sessions = list_sessions(limit=60)
    queue = _redis_queue()
    pending_jobs = []
    if queue is not None:
        try:
            pending_jobs = queue.get_job_ids(offset=0, length=10)
        except Exception:
            pending_jobs = []

    return {
        "brand": CONFIG.get("BISHOP_BRAND_NAME", "BISHOP"),
        "paths": _paths_payload(),
        "queue": {
            "name": CONFIG.get("TASK_QUEUE_NAME", "bishopbot_tasks"),
            "pending_count": len(pending_jobs),
            "pending_jobs": pending_jobs,
        },
        "sessions": {
            "total": len(sessions),
            "active": sum(1 for session in sessions if session["status"] in ACTIVE_STATUSES),
            "waiting": sum(1 for session in sessions if session["status"] == "waiting_for_input"),
            "attention": sum(1 for session in sessions if session["status"] == "attention_needed"),
            "completed": sum(1 for session in sessions if session["status"] == "completed"),
        },
        "memory": {
            "resources_count": len(list_resources()),
            "notes_count": len(list_notes()),
            "db_path": str(agent_context_service.memory_db_path()),
            "vibes_path": str(agent_context_service.vibes_path()),
        },
        "recent_sessions": sessions[:8],
    }


def _is_session_accepting_input(session_id: str) -> bool:
    session = get_session(session_id)
    if not session:
        return False

    state = session.get("state") or {}
    state_status = (state.get("status") or "").strip().lower()
    session_status = str(session.get("status") or "").strip().lower()
    effective_status = state_status or session_status
    prompt_transport = (state.get("prompt_transport") or "").strip().lower()
    if prompt_transport == "argv":
        return False
    return effective_status in ACTIVE_STATUSES


def enqueue_dashboard_command(command: str, text: str, runtime_mode: str | None = None) -> dict[str, Any]:
    queue = _redis_queue()
    if queue is None:
        raise RuntimeError("Redis queue is not configured")

    normalized_command = command.strip()
    if normalized_command not in {"/cli", "/codex"}:
        raise ValueError("Only /cli and /codex are supported from the dashboard")

    body_text = text.strip()
    if not body_text:
        raise ValueError("Command text is required")

    if runtime_mode:
        body_text = f"{runtime_mode} {body_text}".strip()

    job = queue.enqueue(
        "local_worker.process_task",
        command=normalized_command,
        input_text=body_text,
        response_url="console:dashboard",
        user_id="dashboard",
    )
    return {
        "job_id": job.id,
        "command": normalized_command,
        "input_text": body_text,
        "queue": queue.name,
    }


def run_glass_command(command: str, text: str) -> dict[str, Any]:
    normalized_command = command.strip()
    if normalized_command not in {"/cli", "/codex"}:
        raise ValueError("Only /cli and /codex are supported from the glass bridge")

    payload = text or ""
    if not payload.strip():
        raise ValueError("Command text is required")

    mode = "codex" if normalized_command == "/codex" else "gemini"
    result = cli_handler.handle_cli_command(
        payload,
        response_url="console:glass",
        user_id="glass",
        mode=mode,
    )
    result["command"] = normalized_command
    return result


def enqueue_session_input(session_id: str, text: str) -> dict[str, Any]:
    queue = _redis_queue()
    if queue is None:
        raise RuntimeError("Redis queue is not configured")

    if not _is_session_accepting_input(session_id):
        raise ValueError("Session is not active or is no longer accepting input")

    payload = text or ""
    if not payload.strip():
        raise ValueError("Input text is required")

    job = queue.enqueue(
        "local_worker.process_terminal_input",
        session_id=session_id,
        input_text=payload,
        user_id="dashboard",
        response_url="console:dashboard",
        send_ack=False,
    )
    return {
        "job_id": job.id,
        "session_id": session_id,
        "input_text": payload,
    }


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
