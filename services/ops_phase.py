from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal

OpsPhase = Literal["intake", "triage", "execute", "verify", "recover", "handoff", "archived"]
OpsRisk = Literal["low", "medium", "high"]
OpsToolPolicy = Literal["observe", "plan", "tool-first"]

OPS_PHASES: tuple[str, ...] = ("intake", "triage", "execute", "verify", "recover", "handoff", "archived")
DEFAULT_OPS_PHASE: OpsPhase = "execute"

_PHASE_GUIDANCE: dict[str, dict[str, str]] = {
    "intake": {
        "goal": "collect context, ask only what is missing, and avoid premature action",
        "next": "triage",
        "exit": "enough context gathered to define scope",
    },
    "triage": {
        "goal": "summarize scope, constraints, risks, and the next concrete move",
        "next": "execute",
        "exit": "a workable plan is set",
    },
    "execute": {
        "goal": "use tools, make the change, and keep narration short",
        "next": "verify",
        "exit": "the requested work is implemented",
    },
    "verify": {
        "goal": "run checks, compare expected vs actual, and confirm success or failure",
        "next": "handoff",
        "exit": "validation passes or a clear blocker is known",
    },
    "recover": {
        "goal": "diagnose the failure, fix the smallest useful thing, and re-run verification",
        "next": "verify",
        "exit": "the blocker is removed",
    },
    "handoff": {
        "goal": "close the loop with a concise summary, artifacts, and any risks left behind",
        "next": "intake",
        "exit": "the user has enough information to continue or stop",
    },
    "archived": {
        "goal": "treat the session as closed and do not continue active prompting",
        "next": "intake",
        "exit": "finalized",
    },
}


@dataclass(slots=True)
class OpsPhaseState:
    phase: OpsPhase = DEFAULT_OPS_PHASE
    version: int = 1
    reason: str = "initial execution"
    confidence: float = 0.75
    risk: OpsRisk = "medium"
    tool_policy: OpsToolPolicy = "tool-first"
    needs_verification: bool = True
    next_expected: str | None = "verify"
    turn_id: int | None = None
    source: str = "system"
    tags: list[str] = field(default_factory=lambda: ["operator", "phase"])
    handoff_summary: str | None = None
    entered_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_phase(value: str | None, fallback: OpsPhase = DEFAULT_OPS_PHASE) -> OpsPhase:
    normalized = str(value or "").strip().lower()
    if normalized in OPS_PHASES:
        return normalized  # type: ignore[return-value]
    return fallback


def phase_guidance(phase: str | None) -> dict[str, str]:
    return _PHASE_GUIDANCE.get(normalize_phase(phase), _PHASE_GUIDANCE[DEFAULT_OPS_PHASE]).copy()


def make_ops_phase_state(
    phase: str | None = DEFAULT_OPS_PHASE,
    *,
    reason: str = "initial execution",
    risk: OpsRisk = "medium",
    confidence: float = 0.75,
    tool_policy: OpsToolPolicy = "tool-first",
    needs_verification: bool = True,
    next_expected: str | None = None,
    source: str = "system",
    tags: list[str] | None = None,
    turn_id: int | None = None,
    handoff_summary: str | None = None,
) -> OpsPhaseState:
    normalized = normalize_phase(phase)
    guidance = phase_guidance(normalized)
    return OpsPhaseState(
        phase=normalized,
        reason=reason,
        confidence=confidence,
        risk=risk,
        tool_policy=tool_policy,
        needs_verification=needs_verification,
        next_expected=next_expected or guidance["next"],
        source=source,
        tags=tags or ["operator", normalized],
        turn_id=turn_id,
        handoff_summary=handoff_summary,
        entered_at=utc_now(),
        updated_at=utc_now(),
    )


def render_ops_phase_block(
    phase: str | None = DEFAULT_OPS_PHASE,
    *,
    reason: str = "initial execution",
    risk: OpsRisk = "medium",
    confidence: float = 0.75,
    tool_policy: OpsToolPolicy = "tool-first",
) -> str:
    state = make_ops_phase_state(
        phase,
        reason=reason,
        risk=risk,
        confidence=confidence,
        tool_policy=tool_policy,
    )
    guidance = phase_guidance(state.phase)
    checklist = {
        "intake": [
            "collect missing context",
            "avoid tool calls until the scope is clear",
        ],
        "triage": [
            "summarize scope, constraints, and risks",
            "name the next concrete action",
        ],
        "execute": [
            "use tools now",
            "keep narration short and action-oriented",
        ],
        "verify": [
            "run checks",
            "compare actual output to the request",
        ],
        "recover": [
            "diagnose the blocker",
            "make the smallest useful fix",
        ],
        "handoff": [
            "summarize outcome and artifacts",
            "call out risks or follow-ups",
        ],
        "archived": [
            "do not continue active prompting",
        ],
    }.get(state.phase, [])

    lines = [
        "## Ops phase",
        f"- phase: {state.phase}",
        f"- reason: {state.reason}",
        f"- risk: {state.risk}",
        f"- confidence: {state.confidence:.2f}",
        f"- policy: {state.tool_policy}",
        f"- next: {state.next_expected or guidance['next']}",
        f"- exit criteria: {guidance['exit']}",
    ]
    if checklist:
        lines.append("- checklist:")
        lines.extend(f"  - {item}" for item in checklist)
    return "\n".join(lines)


def render_ops_protocol_block() -> str:
    return (
        "## Bishop ops protocol\n"
        "- understand the request before acting\n"
        "- plan briefly, then execute in an isolated terminal\n"
        "- verify the result against the request\n"
        "- if blocked, state the blocker plainly and stop\n"
        "- finish with a concise handoff that names artifacts, risks, and next steps"
    )
