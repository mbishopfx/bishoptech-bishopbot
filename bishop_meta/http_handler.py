from __future__ import annotations

import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from bishop_meta.telegram_miniapp_auth import parse_allowed_user_ids, validate_telegram_init_data
from bishop_meta.whatsapp_webhook import WhatsAppWebhook
from config import CONFIG
from services import dashboard_service


class UnifiedHealthAndWhatsAppHandler(BaseHTTPRequestHandler):
    """Single handler that supports:

    - GET / -> OK (health)
    - GET /whatsapp/webhook -> Meta verification
    - POST /whatsapp/webhook -> message events
    """

    webhook = WhatsAppWebhook()

    def _send(self, status: int, body: str | bytes, content_type: str = "text/plain"):
        if isinstance(body, bytes):
            b = body
        else:
            b = (body or "").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _send_json(self, status: int, payload):
        self._send(status, dashboard_service.json_bytes(payload), "application/json")

    def _dashboard_allowed(self) -> bool:
        token = str(CONFIG.get("DASHBOARD_API_TOKEN", "") or "").strip()
        if token:
            return (self.headers.get("X-Bishop-Dashboard-Token") or "").strip() == token
        client_ip = (self.client_address or ("", 0))[0]
        return client_ip in {"127.0.0.1", "::1"}

    def _miniapp_root(self) -> Path:
        return Path(str(CONFIG.get("TELEGRAM_MINIAPP_DIR") or "")).expanduser().resolve()

    def _miniapp_allowed(self) -> bool:
        bot_token = str(CONFIG.get("TELEGRAM_BOT_TOKEN") or "").strip()
        owner_id_raw = str(CONFIG.get("TELEGRAM_OWNER_ID") or "").strip()
        allowed = parse_allowed_user_ids(str(CONFIG.get("TELEGRAM_ALLOWED_USERS") or ""))
        owner_id = None
        if owner_id_raw:
            try:
                owner_id = int(owner_id_raw)
            except Exception:
                owner_id = None
        init_data = self.headers.get("X-Telegram-Init-Data") or ""
        auth = validate_telegram_init_data(
            init_data,
            bot_token=bot_token,
            allowed_user_ids=allowed,
            owner_id=owner_id,
            max_age_seconds=86400,
        )
        if auth.valid:
            if owner_id is None and not allowed:
                return False
            self._telegram_user_id = auth.user_id
            self._telegram_username = auth.username
            return True

        bearer = (self.headers.get("Authorization") or "").strip()
        fallback = str(CONFIG.get("DASHBOARD_API_TOKEN", "") or "").strip()
        if fallback and bearer == f"Bearer {fallback}":
            self._telegram_user_id = owner_id
            self._telegram_username = None
            return True
        return False

    def _dashboard_path_parts(self) -> list[str]:
        parsed = urllib.parse.urlparse(self.path)
        return [part for part in parsed.path.split("/") if part][2:]

    def _miniapp_path_parts(self) -> list[str]:
        parsed = urllib.parse.urlparse(self.path)
        return [part for part in parsed.path.split("/") if part][2:]

    def _serve_static_miniapp(self):
        root = self._miniapp_root()
        parsed = urllib.parse.urlparse(self.path)
        rel = parsed.path[len("/miniapp") :].lstrip("/")
        if not rel or rel == "":
            rel = "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        file_path = (root / rel).resolve()
        try:
            file_path.relative_to(root)
        except Exception:
            self._send_json(404, {"error": "Not found"})
            return
        if not file_path.exists() or not file_path.is_file():
            self._send_json(404, {"error": "Mini app asset not found"})
            return
        content_type, _ = mimetypes.guess_type(str(file_path))
        self._send(200, file_path.read_bytes(), content_type or "application/octet-stream")

    def do_GET(self):
        if self.path.startswith("/api/dashboard"):
            if not self._dashboard_allowed():
                self._send_json(403, {"error": "Dashboard API is restricted to localhost or a valid token."})
                return

            parts = self._dashboard_path_parts()
            if not parts or parts == ["overview"]:
                self._send_json(200, dashboard_service.overview())
                return
            if parts == ["sessions"]:
                self._send_json(200, {"sessions": dashboard_service.list_sessions()})
                return
            if len(parts) == 2 and parts[0] == "sessions":
                session = dashboard_service.get_session(parts[1])
                if not session:
                    self._send_json(404, {"error": "Session not found"})
                    return
                self._send_json(200, session)
                return
            if parts == ["resources"]:
                self._send_json(200, {"resources": dashboard_service.list_resources()})
                return
            if parts == ["notes"]:
                self._send_json(200, {"notes": dashboard_service.list_notes()})
                return
            self._send_json(404, {"error": "Not found"})
            return

        if self.path.startswith("/api/miniapp"):
            if not self._miniapp_allowed():
                self._send_json(401, {"error": "Telegram auth failed"})
                return

            parts = self._miniapp_path_parts()
            if not parts or parts == ["overview"]:
                overview = dashboard_service.overview()
                overview["owner"] = {
                    "user_id": getattr(self, "_telegram_user_id", None),
                    "username": getattr(self, "_telegram_username", None),
                }
                overview["title"] = str(CONFIG.get("TELEGRAM_MINIAPP_TITLE") or "BishopBot Terminal")
                self._send_json(200, overview)
                return
            if parts == ["sessions"]:
                self._send_json(200, {"sessions": dashboard_service.list_sessions()})
                return
            if len(parts) == 2 and parts[0] == "sessions":
                session = dashboard_service.get_session(parts[1])
                if not session:
                    self._send_json(404, {"error": "Session not found"})
                    return
                self._send_json(200, session)
                return
            self._send_json(404, {"error": "Not found"})
            return

        if self.path.startswith("/miniapp"):
            self._serve_static_miniapp()
            return

        if self.path.startswith("/whatsapp/webhook"):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            # parse_qs gives lists
            flat = {k: (v[0] if isinstance(v, list) and v else "") for k, v in query.items()}
            status, body = self.webhook.verify_get(flat)
            if str(CONFIG.get("WHATSAPP_DEBUG", "false")).lower() == "true":
                mode = flat.get("hub.mode", "")
                has_token = bool(flat.get("hub.verify_token"))
                has_challenge = bool(flat.get("hub.challenge"))
                print(f"WA_WEBHOOK GET mode={mode} token={has_token} challenge={has_challenge} -> {status}")
            self._send(status, body)
            return

        # default health
        self._send(200, "OK")

    def do_POST(self):
        if self.path.startswith("/api/glass/commands"):
            if not self._dashboard_allowed():
                self._send_json(403, {"error": "Glass API is restricted to localhost or a valid token."})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8") or "{}")
            except Exception:
                self._send_json(400, {"error": "Invalid JSON"})
                return

            try:
                result = dashboard_service.run_glass_command(
                    str(payload.get("command") or "/cli"),
                    str(payload.get("text") or ""),
                )
                self._send_json(202, result)
                return
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except Exception as exc:
                self._send_json(500, {"error": str(exc)})
                return

        if self.path.startswith("/api/miniapp"):
            if not self._miniapp_allowed():
                self._send_json(401, {"error": "Telegram auth failed"})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8") or "{}")
            except Exception:
                self._send_json(400, {"error": "Invalid JSON"})
                return

            parts = self._miniapp_path_parts()
            try:
                if parts == ["commands"]:
                    result = dashboard_service.enqueue_dashboard_command(
                        str(payload.get("command") or "/cli"),
                        str(payload.get("text") or ""),
                        str(payload.get("runtime_mode") or "").strip() or None,
                    )
                    self._send_json(202, result)
                    return

                if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "input":
                    result = dashboard_service.enqueue_session_input(parts[1], str(payload.get("text") or ""))
                    self._send_json(202, result)
                    return
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except RuntimeError as exc:
                self._send_json(503, {"error": str(exc)})
                return

            self._send_json(404, {"error": "Not found"})
            return

        if self.path.startswith("/api/dashboard"):
            if not self._dashboard_allowed():
                self._send_json(403, {"error": "Dashboard API is restricted to localhost or a valid token."})
                return

            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8") or "{}")
            except Exception:
                self._send_json(400, {"error": "Invalid JSON"})
                return

            parts = self._dashboard_path_parts()
            try:
                if parts == ["commands"]:
                    self._send_json(410, {"error": "Dashboard is read-only. Launch /cli and /codex from Slack."})
                    return

                if len(parts) == 3 and parts[0] == "sessions" and parts[2] == "input":
                    self._send_json(410, {"error": "Dashboard is read-only. Continue sessions from Slack controls or a Slack thread reply."})
                    return
            except ValueError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except RuntimeError as exc:
                self._send_json(503, {"error": str(exc)})
                return

            self._send_json(404, {"error": "Not found"})
            return

        if not self.path.startswith("/whatsapp/webhook"):
            self._send(404, "Not Found")
            return

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw_body = self.rfile.read(length) if length > 0 else b""
        headers = {k: v for k, v in self.headers.items()}

        status, body = self.webhook.handle_post(raw_body, headers)
        if str(CONFIG.get("WHATSAPP_DEBUG", "false")).lower() == "true":
            sig_present = bool(headers.get("x-hub-signature-256") or headers.get("X-Hub-Signature-256"))
            print(f"WA_WEBHOOK POST bytes={len(raw_body)} sig={sig_present} -> {status}")
        self._send(status, body)

    def log_message(self, fmt, *args):
        # Reduce noise in Railway logs.
        return
