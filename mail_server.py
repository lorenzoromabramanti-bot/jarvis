# -*- coding: utf-8 -*-
"""Serveur autonome de la messagerie web JARVIS.

Point d'entrée officiel : importe email_hub directement, ne démarre pas
main2.py / le reste de JARVIS. Lancé par MESSAGERIE_JARVIS.bat.
"""

import http.server
import json
import os
from urllib.parse import parse_qs, urlparse

import email_hub


PORT = 8090
WEBMAIL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webmail")


class WebmailHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEBMAIL_DIR, **kwargs)

    def log_message(self, *_args):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path)

        if path.path == "/api/inbox":
            try:
                data = email_hub.boite_unifiee()
            except Exception as exc:
                data = {"configured": False, "accounts": [], "messages": [],
                        "error": str(exc)}
            return self._json(data)

        if path.path == "/api/accounts":
            try:
                accounts = email_hub.charger_comptes()
                data = [{"name": account.get("name"),
                         "user": account.get("user"),
                         "provider": account.get("provider")}
                        for account in accounts]
            except Exception as exc:
                data = {"error": str(exc)}
            return self._json(data)

        if path.path == "/api/message":
            query = parse_qs(path.query)
            account = (query.get("account") or [""])[0]
            message_id = (query.get("id") or [""])[0]
            try:
                data = email_hub.lire_message(account, message_id)
            except Exception as exc:
                data = {"error": str(exc)}
            return self._json(data)

        return super().do_GET()


def main():
    if not os.path.isdir(WEBMAIL_DIR):
        raise SystemExit(f"Dossier webmail/ introuvable: {WEBMAIL_DIR}")
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), WebmailHandler)
    print(f"[MAIL] JARVIS Mail sur http://127.0.0.1:{PORT}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
