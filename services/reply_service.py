import re
from services import slack_service, whatsapp_service


_WHATSAPP_PREFIX_RE = re.compile(r"^whatsapp:(.+)$")
_CONSOLE_PREFIX_RE = re.compile(r"^console(?::(.+))?$")


def is_whatsapp_target(target: str) -> bool:
    if not target:
        return False
    return bool(_WHATSAPP_PREFIX_RE.match(target.strip()))


def is_console_target(target: str) -> bool:
    if not target:
        return False
    return bool(_CONSOLE_PREFIX_RE.match(target.strip()))


def _parse_whatsapp_target(target: str):
    m = _WHATSAPP_PREFIX_RE.match((target or "").strip())
    if not m:
        return None
    return m.group(1).strip()


def _parse_console_target(target: str):
    m = _CONSOLE_PREFIX_RE.match((target or "").strip())
    if not m:
        return None
    label = (m.group(1) or "local").strip()
    return label or "local"


def send(target: str, text: str, *, blocks=None):
    """Send a message to Slack, WhatsApp, or a local console target."""
    if not target:
        print("⚠️ No reply target provided; skipping send.")
        return False

    wa_id = _parse_whatsapp_target(target)
    if wa_id:
        # WhatsApp doesn't support Slack blocks; we ignore blocks.
        return whatsapp_service.send_text(wa_id, text)

    console_label = _parse_console_target(target)
    if console_label:
        print(f"\n===== BishopBot console:{console_label} =====\n{text}\n")
        if blocks:
            print(f"[console:{console_label}] Slack blocks omitted in console mode ({len(blocks)} block(s)).")
        return True

    # Default: treat as Slack response_url
    return slack_service.send_delayed_message(target, text, blocks=blocks)
