#!/usr/bin/env python3
"""
Run Telegram webhook server for interactive digest buttons.
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.config.digest_config import DigestConfigManager
from src.services.telegram_webhook_service import TelegramWebhookService


class TelegramWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path != self.server.webhook_path:
            self.send_response(404)
            self.end_headers()
            return
        secret_token = self.server.secret_token
        if secret_token:
            header_token = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if header_token != secret_token:
                self.send_response(403)
                self.end_headers()
                return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return
        self.server.webhook_service.handle_update(payload)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram webhook server")
    parser.add_argument("--config", help="Path to daily digest config")
    parser.add_argument("--host", help="Override webhook host")
    parser.add_argument("--port", type=int, help="Override webhook port")
    parser.add_argument("--path", help="Override webhook path")
    parser.add_argument("--secret-token", help="Override webhook secret token")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cfg_manager = DigestConfigManager(args.config)
    cfg = cfg_manager.config
    telegram_cfg = cfg.get("telegram", {})
    webhook_cfg = telegram_cfg.get("webhook", {}) if telegram_cfg else {}

    host = args.host or webhook_cfg.get("host", "0.0.0.0")
    port = int(args.port or webhook_cfg.get("port", 8090))
    path = args.path or webhook_cfg.get("path", "/telegram/webhook")
    secret_token = args.secret_token or webhook_cfg.get("secret_token")

    service = TelegramWebhookService(args.config)
    server = ThreadingHTTPServer((host, port), TelegramWebhookHandler)
    server.webhook_service = service
    server.webhook_path = path
    server.secret_token = secret_token

    print(json.dumps({
        "message": "Telegram webhook server started",
        "host": host,
        "port": port,
        "path": path
    }, ensure_ascii=False))
    server.serve_forever()


if __name__ == "__main__":
    main()
