import re
from services import slack_service, whatsapp_service


_WHATSAPP_PREFIX_RE = re.compile(r"^whatsapp:(.+)$")


def is_whatsapp_target(target: str) -> bool:
    if not target:
        return False
    return bool(_WHATSAPP_PREFIX_RE.match(target.strip()))


def _parse_whatsapp_target(target: str):
    m = _WHATSAPP_PREFIX_RE.match((target or "").strip())
    if not m:
        return None
    return m.group(1).strip()


def send(target: str, text: str, *, blocks=None):
    """Send a message to either Slack (response_url) or WhatsApp (whatsapp:<wa_id>)."""
    if not target:
        print("⚠️ No reply target provided; skipping send.")
        return False

    wa_id = _parse_whatsapp_target(target)
    if wa_id:
        # WhatsApp doesn't support Slack blocks; we ignore blocks.
        return whatsapp_service.send_text(wa_id, text)

    # Default: treat as Slack response_url
    return slack_service.send_delayed_message(target, text, blocks=blocks)
