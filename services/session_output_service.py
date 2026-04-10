from __future__ import annotations

from pathlib import Path

from config import CONFIG


OUTPUT_FILENAME_SUFFIX = ".log"


def _output_root() -> Path:
    configured = str(CONFIG.get("SESSION_OUTPUT_DIR", "") or "").strip()
    if configured:
        root = Path(configured).expanduser()
        if not root.is_absolute():
            root = Path(CONFIG.get("PROJECT_ROOT_DIR") or ".") / root
    else:
        root = Path(CONFIG.get("PROJECT_ROOT_DIR") or ".") / "logs" / "session-output"
    root.mkdir(parents=True, exist_ok=True)
    return root


def session_output_path(session_id: str) -> Path:
    return _output_root() / f"{session_id}{OUTPUT_FILENAME_SUFFIX}"


def initialize_session_output(session_id: str) -> str:
    path = session_output_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return str(path)


def read_output_file(path: str | Path | None) -> str:
    if not path:
        return ""
    resolved = Path(path)
    if not resolved.exists():
        return ""
    return resolved.read_text(encoding="utf-8")


def read_session_output(session_id: str) -> str:
    return read_output_file(session_output_path(session_id))
