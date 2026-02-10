import urllib.parse
from http.server import BaseHTTPRequestHandler

from bishop_meta.whatsapp_webhook import WhatsAppWebhook
from config import CONFIG


class UnifiedHealthAndWhatsAppHandler(BaseHTTPRequestHandler):
    """Single handler that supports:

    - GET / -> OK (health)
    - GET /whatsapp/webhook -> Meta verification
    - POST /whatsapp/webhook -> message events
    """

    webhook = WhatsAppWebhook()

    def _send(self, status: int, body: str, content_type: str = "text/plain"):
        b = (body or "").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
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
