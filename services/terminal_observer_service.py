from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests

from config import CONFIG


CONTROL_ORDER = [
    "ENTER",
    "Y",
    "N",
    "TAB",
    "SHIFT_TAB",
    "ARROW_UP",
    "ARROW_DOWN",
    "ARROW_LEFT",
    "ARROW_RIGHT",
    "ESC",
    "CTRL_C",
    "STATUS",
    "STOP",
]

CONTROL_LABELS = {
    "ENTER": "↵ Enter",
    "Y": "✅ Yes / Y",
    "N": "❌ No / N",
    "TAB": "⇥ Tab",
    "SHIFT_TAB": "⇤ Shift+Tab",
    "ARROW_UP": "↑ Up",
    "ARROW_DOWN": "↓ Down",
    "ARROW_LEFT": "← Left",
    "ARROW_RIGHT": "→ Right",
    "ESC": "⎋ Esc",
    "CTRL_C": "Ctrl+C",
    "STATUS": "📟 Status",
    "STOP": "🛑 Stop",
}

CONTROL_ACTION_IDS = {
    "ENTER": "cli_input_enter",
    "Y": "cli_input_yes",
    "N": "cli_input_no",
    "TAB": "cli_input_tab",
    "SHIFT_TAB": "cli_input_shift_tab",
    "ARROW_UP": "cli_input_arrow_up",
    "ARROW_DOWN": "cli_input_arrow_down",
    "ARROW_LEFT": "cli_input_arrow_left",
    "ARROW_RIGHT": "cli_input_arrow_right",
    "ESC": "cli_input_esc",
    "CTRL_C": "cli_input_ctrl_c",
    "STATUS": "cli_status",
    "STOP": "cli_stop",
}

REMOTE_STATES = {"working", "awaiting_input", "attention_needed", "completed", "settled", "closed"}

INPUT_PATTERNS = (
    (re.compile(r"\b(?:press|hit|use)\s+(?:enter|return)\b", re.IGNORECASE), ["ENTER"]),
    (re.compile(r"\b(?:yes/no|y/n)\b", re.IGNORECASE), ["Y", "N"]),
    (re.compile(r"\bconfirm\b|\bapprove\b", re.IGNORECASE), ["ENTER", "Y", "N"]),
    (re.compile(r"\bshift\s*\+\s*tab\b|\bshift-tab\b|\bbacktab\b", re.IGNORECASE), ["SHIFT_TAB", "TAB"]),
    (re.compile(r"\btab\b", re.IGNORECASE), ["TAB", "SHIFT_TAB"]),
    (re.compile(r"\barrow keys?\b|\bup/down\b|\bnavigate\b|\bselect\b|\bmove\b", re.IGNORECASE), ["ARROW_UP", "ARROW_DOWN", "ENTER"]),
    (re.compile(r"\bup arrow\b", re.IGNORECASE), ["ARROW_UP"]),
    (re.compile(r"\bdown arrow\b", re.IGNORECASE), ["ARROW_DOWN"]),
    (re.compile(r"\bleft arrow\b", re.IGNORECASE), ["ARROW_LEFT"]),
    (re.compile(r"\bright arrow\b", re.IGNORECASE), ["ARROW_RIGHT"]),
    (re.compile(r"\bpress esc\b|\bescape\b", re.IGNORECASE), ["ESC"]),
)

PROMPT_PATTERNS = (
    re.compile(r"\?\s*$"),
    re.compile(r"\bcontinue\?\s*$", re.IGNORECASE),
    re.compile(r"\bwould you like to continue\b", re.IGNORECASE),
    re.compile(r"\bchoose an option\b", re.IGNORECASE),
    re.compile(r"\bselect an option\b", re.IGNORECASE),
    re.compile(r"\bwaiting for input\b", re.IGNORECASE),
    re.compile(r"\bwaiting for confirmation\b", re.IGNORECASE),
    re.compile(r"\bpress (?:enter|return)\b", re.IGNORECASE),
    re.compile(r"^\s*[>\-*\u2022]\s+\[[ x]\]\s+", re.IGNORECASE),
)

MENU_MARKERS = ("❯", "›", "→", "[ ]", "( )")


@dataclass(frozen=True)
class TerminalObservation:
    state: str
    reason: str
    controls: list[str]
    confidence: float
    human_input_needed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "observer_state": self.state,
            "observer_reason": self.reason,
            "observer_confidence": self.confidence,
            "suggested_controls": list(self.controls),
            "requires_human_input": self.human_input_needed,
        }


def button_label(control: str, runtime_controls: dict[str, Any] | None = None) -> str:
    runtime_controls = runtime_controls or {}
    if control == "ENTER":
        return str(runtime_controls.get("enter_button_label") or CONTROL_LABELS[control])
    if control == "N":
        return str(runtime_controls.get("no_button_label") or CONTROL_LABELS[control])
    return CONTROL_LABELS.get(control, control.title())


def normalize_controls(controls: list[str], interactive_allowed: bool) -> list[str]:
    allowed = {"STATUS", "STOP"}
    if interactive_allowed:
        allowed.update(CONTROL_LABELS)
    ordered: list[str] = []
    for control in CONTROL_ORDER:
        if control in controls and control in allowed and control not in ordered:
            ordered.append(control)
    for control in controls:
        if control in allowed and control not in ordered:
            ordered.append(control)
    return ordered


def control_chunks(controls: list[str], size: int = 5) -> list[list[str]]:
    return [controls[index:index + size] for index in range(0, len(controls), size)]


def infer_controls(output: str, *, interactive_allowed: bool) -> list[str]:
    controls: list[str] = []
    lower_output = (output or "").lower()

    for pattern, suggested in INPUT_PATTERNS:
        if pattern.search(output or ""):
            controls.extend(suggested)

    if any(marker in output for marker in MENU_MARKERS):
        controls.extend(["ARROW_UP", "ARROW_DOWN", "ENTER"])

    if "yes" in lower_output and "no" in lower_output:
        controls.extend(["Y", "N"])

    if interactive_allowed and not controls:
        controls.extend(["ENTER", "TAB", "SHIFT_TAB", "ARROW_UP", "ARROW_DOWN"])

    controls.extend(["STATUS", "STOP"])
    return normalize_controls(controls, interactive_allowed=interactive_allowed)


def detect_input_required(output: str, *, interactive_allowed: bool, terminal_busy: bool) -> bool:
    if not interactive_allowed or terminal_busy:
        return False

    cleaned = (output or "").strip()
    if not cleaned:
        return False

    tail = "\n".join(cleaned.splitlines()[-10:])
    if any(pattern.search(tail) for pattern in PROMPT_PATTERNS):
        return True

    lower_tail = tail.lower()
    return any(keyword in lower_tail for keyword in ("select an option", "choose an option", "waiting for input", "press enter"))


def _heuristic_observation(
    *,
    session_status: str,
    output: str,
    prompt_transport: str,
    terminal_busy: bool,
) -> TerminalObservation:
    interactive_allowed = prompt_transport == "stdin"

    if session_status == "completed":
        return TerminalObservation("completed", "runtime completed successfully", ["STATUS"], 0.99, False)
    if session_status in {"closed", "timed_out"}:
        return TerminalObservation("closed", "session is no longer active", ["STATUS"], 0.99, False)
    if session_status == "attention_needed":
        return TerminalObservation(
            "attention_needed",
            "runtime reported an error or is blocked",
            infer_controls(output, interactive_allowed=interactive_allowed),
            0.92,
            interactive_allowed,
        )
    if session_status == "waiting_for_input":
        return TerminalObservation(
            "awaiting_input",
            "runtime is waiting on operator input",
            infer_controls(output, interactive_allowed=interactive_allowed),
            0.95,
            interactive_allowed,
        )
    if detect_input_required(output, interactive_allowed=interactive_allowed, terminal_busy=terminal_busy):
        return TerminalObservation(
            "awaiting_input",
            "visible terminal prompt looks interactive",
            infer_controls(output, interactive_allowed=interactive_allowed),
            0.82,
            interactive_allowed,
        )
    if session_status == "settled":
        return TerminalObservation("settled", "runtime output settled; verify the result", ["STATUS", "STOP"], 0.8, False)
    return TerminalObservation("working", "runtime is still producing or evaluating output", ["STATUS", "STOP"], 0.78, False)


def _observer_timeout_seconds() -> int:
    try:
        return max(1, int(str(CONFIG.get("TERMINAL_OBSERVER_TIMEOUT_SECONDS", "5") or "5")))
    except Exception:
        return 5


def _observer_mode() -> str:
    return str(CONFIG.get("TERMINAL_OBSERVER_MODE") or "heuristic").strip().lower() or "heuristic"


def _call_local_observer(payload: dict[str, Any]) -> TerminalObservation | None:
    url = str(CONFIG.get("TERMINAL_OBSERVER_LOCAL_URL") or "").strip()
    if not url:
        return None

    response = requests.post(url, json=payload, timeout=_observer_timeout_seconds())
    response.raise_for_status()
    return _parse_remote_observation(response.json(), fallback_reason="local observer")


def _gemini_endpoint(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _call_gemini_observer(payload: dict[str, Any]) -> TerminalObservation | None:
    api_key = str(CONFIG.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None

    model = str(CONFIG.get("TERMINAL_OBSERVER_GEMINI_MODEL") or "gemini-2.5-flash").strip()
    prompt = (
        "Classify this terminal session into one of: working, awaiting_input, attention_needed, completed, settled, closed.\n"
        "Return JSON only with keys: state, reason, controls, confidence, human_input_needed.\n"
        "controls must use only these values: ENTER, Y, N, TAB, SHIFT_TAB, ARROW_UP, ARROW_DOWN, ARROW_LEFT, "
        "ARROW_RIGHT, ESC, CTRL_C, STATUS, STOP.\n"
        "Prefer STATUS and STOP for working sessions. Add interactive controls only when the visible terminal clearly "
        "looks like it needs operator input.\n\n"
        f"Session payload:\n{json.dumps(payload, ensure_ascii=True)}"
    )
    response = requests.post(
        _gemini_endpoint(model),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
            },
        },
        timeout=_observer_timeout_seconds(),
    )
    response.raise_for_status()
    body = response.json()
    candidates = body.get("candidates") or []
    if not candidates:
        return None
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    text = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
    if not text:
        return None
    return _parse_remote_observation(json.loads(text), fallback_reason="gemini observer")


def _parse_remote_observation(payload: dict[str, Any], *, fallback_reason: str) -> TerminalObservation | None:
    state = str(payload.get("state") or "").strip().lower()
    if state not in REMOTE_STATES:
        return None

    interactive_allowed = bool(payload.get("human_input_needed"))
    controls = normalize_controls(
        [str(control).strip().upper() for control in payload.get("controls") or [] if str(control).strip()],
        interactive_allowed=interactive_allowed,
    )
    if not controls:
        controls = ["STATUS", "STOP"]

    try:
        confidence = float(payload.get("confidence") or 0.7)
    except Exception:
        confidence = 0.7

    reason = str(payload.get("reason") or fallback_reason).strip() or fallback_reason
    return TerminalObservation(state, reason, controls, max(0.0, min(confidence, 1.0)), interactive_allowed)


def observe_terminal(
    *,
    session_status: str,
    output: str,
    prompt_transport: str,
    terminal_busy: bool,
    runtime_label: str,
    launch_mode: str | None,
) -> TerminalObservation:
    heuristic = _heuristic_observation(
        session_status=session_status,
        output=output,
        prompt_transport=prompt_transport,
        terminal_busy=terminal_busy,
    )

    mode = _observer_mode()
    if mode == "heuristic":
        return heuristic

    payload = {
        "runtime": runtime_label,
        "launch_mode": launch_mode,
        "status": session_status,
        "prompt_transport": prompt_transport,
        "terminal_busy": terminal_busy,
        "visible_terminal_output": output[-5000:],
        "heuristic": heuristic.as_dict(),
    }

    try:
        if mode == "local":
            remote = _call_local_observer(payload)
        elif mode == "gemini":
            remote = _call_gemini_observer(payload)
        else:
            remote = None
        if remote is not None:
            return remote
    except Exception:
        pass

    return heuristic
