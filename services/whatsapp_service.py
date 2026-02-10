import json
import time
import requests
from config import CONFIG

# WhatsApp Cloud API sender.
# Requires: WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID


def _chunk_text(text: str, limit: int = 3500):
    text = text or ""
    if len(text) <= limit:
        return [text]

    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        # Prefer splitting on newline near the limit.
        cut = remaining.rfind("\n", 0, limit)
        if cut < 200:  # no good newline split
            cut = limit
        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip("\n")

    return chunks


def send_text(to_wa_id: str, text: str, *, preview_url: bool = False):
    token = CONFIG.get("WHATSAPP_ACCESS_TOKEN")
    phone_number_id = CONFIG.get("WHATSAPP_PHONE_NUMBER_ID")

    if not token or not phone_number_id:
        print("⚠️ WhatsApp not configured (missing WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_NUMBER_ID).")
        return False

    url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    ok = True
    for chunk in _chunk_text(text):
        payload = {
            "messaging_product": "whatsapp",
            "to": to_wa_id,
            "type": "text",
            "text": {"body": chunk, "preview_url": preview_url},
        }

        try:
            resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
            if resp.status_code >= 300:
                ok = False
                print(f"❌ WhatsApp send failed: {resp.status_code} {resp.text}")
            # Avoid bursts that can trigger rate limits
            time.sleep(0.35)
        except Exception as e:
            ok = False
            print(f"❌ WhatsApp send exception: {e}")

    return ok
