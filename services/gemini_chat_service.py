from __future__ import annotations

import shutil
import subprocess
from typing import Optional

import requests

from config import CONFIG
from services import agent_context_service, openai_service


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_OPENAI_FALLBACK_MODEL = "gpt-4o-mini"


def _configured_model() -> str:
    return str(CONFIG.get("GEMINI_CHAT_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL


def is_configured() -> bool:
    return bool(CONFIG.get("GEMINI_API_KEY"))


def _fallback_model() -> str:
    return str(CONFIG.get("MENTION_CHAT_OPENAI_FALLBACK_MODEL") or DEFAULT_OPENAI_FALLBACK_MODEL).strip() or DEFAULT_OPENAI_FALLBACK_MODEL


def build_system_prompt() -> str:
    context = agent_context_service.build_prompt_context()
    return (
        "You are BISHOP's lightweight Slack brainstorming assistant.\n"
        "You are not the terminal execution path.\n"
        "Use concise, useful answers optimized for collaboration and planning.\n"
        "Prefer repo context, local paths, and BISHOP's persistent context when relevant.\n"
        "Do not pretend to have run code or terminal commands.\n"
        "Do not claim MCP tools are active unless the current project Gemini settings show them enabled.\n"
        "If the user wants real execution, tell them to use /cli or /codex.\n\n"
        f"{context}"
    )


def _normalize_prompt(text: str, user_id: Optional[str] = None) -> str:
    prefix = f"Slack user: {user_id}\n\n" if user_id else ""
    return prefix + text.strip()


def _gemini_endpoint(model: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _extract_response_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    return "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()


def _gemini_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text.strip() or f"HTTP {response.status_code}"
    error = payload.get("error") or {}
    message = error.get("message") or response.text.strip() or f"HTTP {response.status_code}"
    return str(message).strip()


def _generate_via_gemini(text: str, *, user_id: Optional[str] = None) -> str:
    payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": build_system_prompt(),
                }
            ]
        },
        "contents": [
            {
                "parts": [
                    {
                        "text": _normalize_prompt(text, user_id=user_id),
                    }
                ]
            }
        ],
    }
    response = requests.post(
        _gemini_endpoint(_configured_model()),
        headers={
            "x-goog-api-key": str(CONFIG["GEMINI_API_KEY"]),
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(_gemini_error_message(response))
    output = _extract_response_text(response.json())
    return output.strip()


def _gemini_cli_binary() -> Optional[str]:
    return shutil.which("gemini")


def _build_cli_prompt(text: str, *, user_id: Optional[str] = None) -> str:
    return (
        f"{build_system_prompt()}\n\n"
        f"User message:\n{_normalize_prompt(text, user_id=user_id)}\n\n"
        "Reply as the lightweight Slack brainstorming assistant. "
        "Do not claim code execution or tool execution."
    )


def _clean_cli_output(output: str) -> str:
    lines = []
    for raw_line in (output or "").splitlines():
        line = raw_line.strip()
        if not line:
            lines.append("")
            continue
        lower_line = line.lower()
        if lower_line.startswith("skill conflict detected:"):
            continue
        if lower_line.startswith('skill "') and "overriding" in lower_line:
            continue
        if lower_line.startswith("loaded cached credentials"):
            continue
        lines.append(line)

    cleaned = "\n".join(lines).strip()
    while "\n\n\n" in cleaned:
        cleaned = cleaned.replace("\n\n\n", "\n\n")
    return cleaned.strip()


def _generate_via_gemini_cli(text: str, *, user_id: Optional[str] = None) -> str:
    binary = _gemini_cli_binary()
    if not binary:
        raise RuntimeError("Gemini CLI is not installed")

    result = subprocess.run(
        [
            binary,
            "--approval-mode",
            "plan",
            "-m",
            _configured_model(),
            "-p",
            _build_cli_prompt(text, user_id=user_id),
        ],
        cwd=CONFIG.get("PROJECT_ROOT_DIR") or None,
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        error_text = _clean_cli_output(result.stderr or result.stdout)
        raise RuntimeError(error_text or f"Gemini CLI exited with code {result.returncode}")

    output = _clean_cli_output(result.stdout)
    if not output:
        raise RuntimeError("Gemini CLI returned an empty response")
    return output


def _generate_via_openai_fallback(text: str, *, user_id: Optional[str] = None) -> str:
    if not CONFIG.get("OPENAI_API_KEY"):
        raise RuntimeError("OpenAI fallback is not configured")
    prompt = _normalize_prompt(text, user_id=user_id)
    response = openai_service.generate_response(
        prompt,
        system_prompt=build_system_prompt(),
        model=_fallback_model(),
    ).strip()
    return response


def generate_chat_reply(text: str, *, user_id: Optional[str] = None) -> str:
    if not is_configured() and not CONFIG.get("OPENAI_API_KEY"):
        raise RuntimeError("Neither GEMINI_API_KEY nor OPENAI_API_KEY is configured")

    gemini_api_error = None
    if is_configured():
        try:
            output = _generate_via_gemini(text, user_id=user_id)
            if output:
                return output
        except Exception as exc:
            gemini_api_error = exc

    try:
        cli_output = _generate_via_gemini_cli(text, user_id=user_id)
        if cli_output:
            if gemini_api_error is not None:
                return f"_Gemini Studio API was unavailable, so this reply used the signed-in local Gemini CLI._\n\n{cli_output}"
            return cli_output
    except Exception:
        pass

    if CONFIG.get("OPENAI_API_KEY"):
        try:
            fallback = _generate_via_openai_fallback(text, user_id=user_id)
            if fallback:
                if gemini_api_error is not None:
                    return f"_Gemini was unavailable, so this reply used the OpenAI fallback._\n\n{fallback}"
                return fallback
        except Exception:
            pass

    raise RuntimeError(
        "Gemini mention chat is unavailable for the current API key or Google project, "
        "and no local fallback succeeded. Use /cli or /codex for terminal execution."
    ) from gemini_api_error
