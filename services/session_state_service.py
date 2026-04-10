from __future__ import annotations

from pathlib import Path
from typing import Any

from config import CONFIG


STATE_FILENAME_SUFFIX = ".state"


def _state_root() -> Path:
    configured = str(CONFIG.get("SESSION_STATE_DIR", "") or "").strip()
    if configured:
        root = Path(configured).expanduser()
        if not root.is_absolute():
            root = Path(CONFIG.get("PROJECT_ROOT_DIR") or ".") / root
    else:
        root = Path(CONFIG.get("PROJECT_ROOT_DIR") or ".") / "logs" / "session-state"
    root.mkdir(parents=True, exist_ok=True)
    return root


def session_state_path(session_id: str) -> Path:
    return _state_root() / f"{session_id}{STATE_FILENAME_SUFFIX}"


def initialize_session_state(session_id: str, **metadata: Any) -> str:
    path = session_state_path(session_id)
    lines = ["status=launching"]
    for key, value in metadata.items():
        if value is None:
            continue
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def parse_session_state(session_id: str) -> dict[str, str]:
    path = session_state_path(session_id)
    if not path.exists():
        return {}

    state: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        state[key.strip()] = value.strip()
    return state
