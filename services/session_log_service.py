from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from config import CONFIG


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _log_root() -> Path:
    configured = str(CONFIG.get("SESSION_LOG_DIR", "") or "").strip()
    if configured:
        root = Path(configured).expanduser()
        if not root.is_absolute():
            root = Path(CONFIG.get("PROJECT_ROOT_DIR") or ".") / root
    else:
        root = Path(CONFIG.get("PROJECT_ROOT_DIR") or ".") / "logs" / "sessions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def session_log_path(session_id: str) -> Path:
    return _log_root() / f"{session_id}.md"


def _append_block(path: Path, title: str, body: str) -> None:
    body = (body or "").rstrip()
    if not body:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## [{_utc_timestamp()}] {title}\n\n")
        handle.write(body)
        handle.write("\n")


def initialize_session_log(session_id: str, session: Mapping[str, Any]) -> str:
    path = session_log_path(session_id)
    tasks = session.get("tasks") or []
    task_lines = "\n".join(f"- {task}" for task in tasks) or "- (no explicit tasks)"
    plan_text = (session.get("plan_text") or "").strip() or "(no plan text)"
    header = "\n".join(
        [
            f"# Session {session_id}",
            "",
            f"- Runtime: {session.get('runtime_label', session.get('runtime', 'unknown'))}",
            f"- Launch mode: {session.get('launch_mode_label', session.get('launch_mode', 'default'))}",
            f"- Launch command: `{session.get('launch_command', '(unknown)')}`",
            f"- Prompt transport: `{session.get('prompt_transport', 'stdin')}`",
            f"- Ops phase: `{session.get('ops_phase', 'execute')}`",
            f"- Window ID: `{session.get('window_id', '')}`",
            f"- User ID: `{session.get('user_id', '')}`",
            f"- Response target: `{session.get('response_url', '')}`",
            f"- Boot delay: {session.get('boot_delay_seconds', 0)}s",
            f"- Output capture: `{session.get('output_path', '')}`",
            "",
            "## Plan",
            "",
            plan_text,
            "",
            "## Tasks",
            "",
            task_lines,
            "",
        ]
    )
    path.write_text(header, encoding="utf-8")
    return str(path)


def append_event(session_id: str, title: str, body: str) -> str:
    path = session_log_path(session_id)
    _append_block(path, title, body)
    return str(path)


def append_snapshot(
    session_id: str,
    *,
    status: str,
    exists: bool,
    busy: bool,
    visible_tail: str,
    full_output: Optional[str] = None,
) -> str:
    parts = [
        f"- Status: {status}",
        f"- Terminal exists: {exists}",
        f"- Terminal busy: {busy}",
        "",
        "### Visible tail",
        "",
        "```text",
        (visible_tail or "(no visible output)").rstrip(),
        "```",
    ]
    cleaned_full = (full_output or "").rstrip()
    if cleaned_full and cleaned_full.strip() != (visible_tail or "").rstrip().strip():
        parts.extend([
            "",
            "### Full sanitized snapshot",
            "",
            "```text",
            cleaned_full,
            "```",
        ])
    append_event(session_id, "Terminal snapshot", "\n".join(parts))
    return str(session_log_path(session_id))
