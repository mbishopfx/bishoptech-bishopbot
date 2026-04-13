from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import parse_qsl


TELEGRAM_WEBAPP_SECRET = b"WebAppData"


@dataclass(slots=True)
class TelegramMiniAppAuthResult:
    valid: bool
    reason: str
    user_id: int | None = None
    username: str | None = None


def _normalize_init_data(raw_init_data: str) -> dict[str, str]:
    data = {}
    for key, value in parse_qsl(raw_init_data, keep_blank_values=True, strict_parsing=False):
        if key:
            data[key] = value
    return data


def _build_data_check_string(data: dict[str, str]) -> str:
    pairs = [f"{key}={value}" for key, value in sorted(data.items()) if key != "hash"]
    return "\n".join(pairs)


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(TELEGRAM_WEBAPP_SECRET, bot_token.encode("utf-8"), hashlib.sha256).digest()


def _safe_user_parse(raw_user: str | None) -> tuple[int | None, str | None]:
    if not raw_user:
        return None, None
    try:
        user = json.loads(raw_user)
    except Exception:
        return None, None
    user_id = user.get("id")
    username = user.get("username")
    try:
        return int(user_id), str(username) if username else None
    except Exception:
        return None, str(username) if username else None


def validate_telegram_init_data(
    raw_init_data: str | None,
    *,
    bot_token: str | None,
    allowed_user_ids: Iterable[int] | None = None,
    owner_id: int | None = None,
    max_age_seconds: int = 86400,
) -> TelegramMiniAppAuthResult:
    if not raw_init_data:
        return TelegramMiniAppAuthResult(False, "missing init data")
    if not bot_token:
        return TelegramMiniAppAuthResult(False, "missing bot token")

    data = _normalize_init_data(raw_init_data)
    if not data:
        return TelegramMiniAppAuthResult(False, "empty init data")

    provided_hash = data.get("hash")
    if not provided_hash:
        return TelegramMiniAppAuthResult(False, "missing hash")

    auth_date_raw = data.get("auth_date") or "0"
    try:
        auth_date = int(auth_date_raw)
    except Exception:
        return TelegramMiniAppAuthResult(False, "invalid auth date")

    if max_age_seconds > 0:
        import time

        age = int(time.time()) - auth_date
        if age < -60:
            return TelegramMiniAppAuthResult(False, "auth date is from the future")
        if age > max_age_seconds:
            return TelegramMiniAppAuthResult(False, "init data expired")

    data_check_string = _build_data_check_string(data)
    digest = hmac.new(_secret_key(bot_token), data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(digest, provided_hash):
        return TelegramMiniAppAuthResult(False, "signature mismatch")

    user_id, username = _safe_user_parse(data.get("user"))
    allowed = set(allowed_user_ids or [])
    if owner_id is not None:
        allowed.add(int(owner_id))
    if allowed and user_id is not None and user_id not in allowed:
        return TelegramMiniAppAuthResult(False, "user not allowed", user_id=user_id, username=username)

    return TelegramMiniAppAuthResult(True, "ok", user_id=user_id, username=username)


def parse_allowed_user_ids(raw: str | None) -> list[int]:
    if not raw:
        return []
    ids: list[int] = []
    for part in raw.split(","):
        piece = part.strip()
        if not piece:
            continue
        try:
            ids.append(int(piece))
        except Exception:
            continue
    return ids
