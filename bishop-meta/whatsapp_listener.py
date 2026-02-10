import os
from http.server import HTTPServer

from bishop_meta.http_handler import UnifiedHealthAndWhatsAppHandler


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), UnifiedHealthAndWhatsAppHandler)
    print(f"WhatsApp webhook server listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
