import hmac
import hashlib
import json
from redis import Redis
from rq import Queue

from config import CONFIG
from services import whatsapp_service
from services.session_link_service import get_last_session


class WhatsAppWebhook:
    """Meta WhatsApp Cloud API webhook -> enqueue jobs to the same Redis queue as Slack."""

    def __init__(self):
        redis_url = CONFIG.get("REDIS_URL")
        self.redis_conn = Redis.from_url(redis_url) if redis_url else None
        self.q = Queue(CONFIG.get("TASK_QUEUE_NAME", "bishopbot_tasks"), connection=self.redis_conn) if self.redis_conn else None

    def verify_get(self, query: dict):
        mode = query.get("hub.mode")
        token = query.get("hub.verify_token")
        challenge = query.get("hub.challenge")

        if mode == "subscribe" and token and token == CONFIG.get("WHATSAPP_VERIFY_TOKEN"):
            return 200, (challenge or "")
        return 403, "Forbidden"

    def _verify_signature(self, raw_body: bytes, headers: dict) -> bool:
        secret = CONFIG.get("WHATSAPP_APP_SECRET")
        if not secret:
            return True  # optional

        sig = headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256")
        if not sig or not sig.startswith("sha256="):
            return False

        expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        got = sig.split("=", 1)[1]
        return hmac.compare_digest(expected, got)

    def handle_post(self, raw_body: bytes, headers: dict):
        if not self._verify_signature(raw_body, headers):
            return 403, "Bad signature"

        try:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        except Exception:
            return 400, "Invalid JSON"

        # Meta sends various webhook events; we only care about inbound messages.
        messages = []
        try:
            for entry in payload.get("entry", []) or []:
                for change in entry.get("changes", []) or []:
                    value = change.get("value", {}) or {}
                    for msg in value.get("messages", []) or []:
                        messages.append(msg)
        except Exception:
            messages = []

        if not messages:
            return 200, "OK"

        if not self.q:
            print("⚠️ WhatsApp webhook received message but REDIS_URL is not configured.")
            return 500, "Redis not configured"

        for msg in messages:
            msg_type = msg.get("type")
            from_wa_id = (msg.get("from") or "").strip()
            text = ((msg.get("text") or {}).get("body") or "").strip()

            if not from_wa_id:
                continue

            # Non-text messages: acknowledge and ignore for now.
            if msg_type != "text":
                whatsapp_service.send_text(from_wa_id, "I only handle text messages right now.")
                continue

            # Command parsing
            # Interactive control keywords:
            # - !enter [session]
            # - !n [session]
            # - !y [session]
            # - !stop [session]
            # - !new <prompt>   (force new session)
            # - !send <session> <text>
            if text.lower().startswith("!enter") or text.strip().upper() == "ENTER":
                session_id = _extract_session_id(text)
                session_id = session_id or get_last_session(from_wa_id)
                if not session_id:
                    whatsapp_service.send_text(from_wa_id, "No session found. Start one by sending a prompt (or !new <prompt>).")
                    continue
                self.q.enqueue(
                    "local_worker.process_terminal_input",
                    session_id=session_id,
                    input_text="ENTER",
                    user_id=from_wa_id,
                    response_url=f"whatsapp:{from_wa_id}",
                )
                whatsapp_service.send_text(from_wa_id, f"Sent ENTER to session {session_id}.")
                continue

            if text.lower().startswith("!n"):
                session_id = _extract_session_id(text)
                session_id = session_id or get_last_session(from_wa_id)
                if not session_id:
                    whatsapp_service.send_text(from_wa_id, "No session found. Start one first.")
                    continue
                self.q.enqueue(
                    "local_worker.process_terminal_input",
                    session_id=session_id,
                    input_text="N",
                    user_id=from_wa_id,
                    response_url=f"whatsapp:{from_wa_id}",
                )
                whatsapp_service.send_text(from_wa_id, f"Sent N to session {session_id}.")
                continue

            if text.lower().startswith("!y"):
                session_id = _extract_session_id(text)
                session_id = session_id or get_last_session(from_wa_id)
                if not session_id:
                    whatsapp_service.send_text(from_wa_id, "No session found. Start one first.")
                    continue
                self.q.enqueue(
                    "local_worker.process_terminal_input",
                    session_id=session_id,
                    input_text="Y",
                    user_id=from_wa_id,
                    response_url=f"whatsapp:{from_wa_id}",
                )
                whatsapp_service.send_text(from_wa_id, f"Sent Y to session {session_id}.")
                continue

            if text.lower().startswith("!stop"):
                session_id = _extract_session_id(text)
                session_id = session_id or get_last_session(from_wa_id)
                if not session_id:
                    whatsapp_service.send_text(from_wa_id, "No session found. Start one first.")
                    continue
                self.q.enqueue(
                    "local_worker.process_terminal_input",
                    session_id=session_id,
                    input_text="STOP",
                    user_id=from_wa_id,
                    response_url=f"whatsapp:{from_wa_id}",
                )
                whatsapp_service.send_text(from_wa_id, f"Stopping session {session_id}.")
                continue

            if text.lower().startswith("!status"):
                session_id = _extract_session_id(text)
                session_id = session_id or get_last_session(from_wa_id)
                if not session_id:
                    whatsapp_service.send_text(from_wa_id, "No session found. Start one by sending a prompt (or !new <prompt>).")
                    continue
                self.q.enqueue(
                    "local_worker.process_terminal_input",
                    session_id=session_id,
                    input_text="STATUS",
                    user_id=from_wa_id,
                    response_url=f"whatsapp:{from_wa_id}",
                )
                whatsapp_service.send_text(from_wa_id, f"Fetching status for session {session_id}...")
                continue

            if text.lower().startswith("!send "):
                parts = text.split(" ", 2)
                if len(parts) < 3:
                    whatsapp_service.send_text(from_wa_id, "Usage: !send <session_id> <text>")
                    continue
                session_id = parts[1].strip()
                payload_text = parts[2].strip()
                self.q.enqueue(
                    "local_worker.process_terminal_input",
                    session_id=session_id,
                    input_text=payload_text,
                    user_id=from_wa_id,
                    response_url=f"whatsapp:{from_wa_id}",
                )
                whatsapp_service.send_text(from_wa_id, f"Sent text to session {session_id}.")
                continue

            # New session: explicit or default
            command, input_text = _parse_task_command(text)

            # Always create a new session by default (matches your request).
            self.q.enqueue(
                "local_worker.process_task",
                command=command,
                input_text=input_text,
                response_url=f"whatsapp:{from_wa_id}",
                user_id=from_wa_id,
            )

            whatsapp_service.send_text(
                from_wa_id,
                "Queued on your local worker. I'll stream Gemini output here.\n\n"
                "Controls: !enter [session], !n [session], !y [session], !status [session], !stop [session]",
            )

        return 200, "OK"


def _extract_session_id(text: str):
    parts = (text or "").strip().split()
    if len(parts) >= 2:
        return parts[1].strip()
    return None


def _parse_task_command(text: str):
    t = (text or "").strip()
    low = t.lower()

    # Normalize a few explicit prefixes
    for prefix, cmd in [
        ("/cli", "/cli"),
        ("cli", "/cli"),
        ("/codex", "/codex"),
        ("codex", "/codex"),
        ("/research", "/research"),
        ("research", "/research"),
        ("!new", "/cli"),
    ]:
        if low == prefix:
            return cmd, ""
        if low.startswith(prefix + " "):
            return cmd, t[len(prefix) :].strip()

    # Default: treat everything as a CLI automation prompt
    return "/cli", t
