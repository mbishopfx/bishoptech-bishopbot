from __future__ import annotations

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

    if is_configured():
        try:
            output = _generate_via_gemini(text, user_id=user_id)
            if output:
                return output
        except Exception as exc:
            if CONFIG.get("OPENAI_API_KEY"):
                fallback = _generate_via_openai_fallback(text, user_id=user_id)
                if fallback:
                    return f"_Gemini was unavailable, so this reply used the OpenAI fallback._\n\n{fallback}"
            raise RuntimeError(f"Gemini mention chat failed: {exc}") from exc

    fallback = _generate_via_openai_fallback(text, user_id=user_id)
    return fallback or "I do not have a response yet. Use /cli or /codex if you want me to execute work."
