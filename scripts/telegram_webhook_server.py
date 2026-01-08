#!/usr/bin/env python3
"""
Run Telegram webhook server for interactive digest buttons.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import threading
from urllib.parse import urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.config.digest_config import DigestConfigManager
from src.config.paths import LOG_DIR
from src.services.telegram_webhook_service import TelegramWebhookService
import requests

logger = logging.getLogger(__name__)


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
        self._log_update(payload)
        self.send_response(200)
        self.end_headers()
        try:
            self.wfile.write(b"OK")
        except BrokenPipeError:
            return
        threading.Thread(
            target=self.server.webhook_service.handle_update,
            args=(payload,),
            daemon=True
        ).start()

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

    def _log_update(self, payload: dict) -> None:
        update_id = payload.get("update_id")
        if "callback_query" in payload:
            callback = payload.get("callback_query", {})
            data = callback.get("data", "")
            from_user = callback.get("from", {}).get("id")
            message_id = callback.get("message", {}).get("message_id")
            logger.info(
                "Telegram callback update_id=%s from=%s message_id=%s data=%s",
                update_id,
                from_user,
                message_id,
                data
            )
            return
        message = payload.get("message", {})
        if message:
            from_user = message.get("from", {}).get("id")
            text = message.get("text", "")
            logger.info(
                "Telegram message update_id=%s from=%s text=%s",
                update_id,
                from_user,
                text
            )
            return
        logger.info("Telegram update_id=%s (unknown payload)", update_id)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Telegram webhook server")
    parser.add_argument("--config", help="Path to daily digest config")
    parser.add_argument("--host", help="Override webhook host")
    parser.add_argument("--port", type=int, help="Override webhook port")
    parser.add_argument("--path", help="Override webhook path")
    parser.add_argument("--secret-token", help="Override webhook secret token")
    parser.add_argument("--public-url", help="Public HTTPS URL for Telegram webhook")
    return parser.parse_args()


def _set_webhook(
    service: TelegramWebhookService,
    public_url: str,
    secret_token: str | None
) -> None:
    if not service.bot_token:
        raise ValueError("Missing Telegram bot_token in config")
    payload = {"url": public_url}
    if secret_token:
        payload["secret_token"] = secret_token
    response = requests.post(
        f"{service.api_base}/bot{service.bot_token}/setWebhook",
        json=payload,
        timeout=10
    )
    response.raise_for_status()


def main() -> None:
    args = _parse_args()
    log_path = Path(os.getenv("TELEGRAM_WEBHOOK_LOG", str(LOG_DIR / "telegram_webhook.log")))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    cfg_manager = DigestConfigManager(args.config)
    cfg = cfg_manager.config
    telegram_cfg = cfg.get("telegram", {})
    config_webhook_url = telegram_cfg.get("webhook_url")
    config_secret = telegram_cfg.get("webhook_secret")

    host = args.host or os.getenv("TELEGRAM_WEBHOOK_HOST", "0.0.0.0")
    port = int(args.port or os.getenv("TELEGRAM_WEBHOOK_PORT", "9142"))
    path = args.path or os.getenv("TELEGRAM_WEBHOOK_PATH")
    public_url = args.public_url or os.getenv("TELEGRAM_WEBHOOK_URL") or config_webhook_url
    secret_token = args.secret_token or os.getenv("TELEGRAM_WEBHOOK_SECRET") or config_secret

    if not path:
        parsed = urlparse(public_url or "")
        path = parsed.path or "/telegram/webhook"

    service = TelegramWebhookService(args.config)
    server = ThreadingHTTPServer((host, port), TelegramWebhookHandler)
    server.webhook_service = service
    server.webhook_path = path
    server.secret_token = secret_token

    if public_url:
        _set_webhook(service, public_url, secret_token)

    logger.info(
        "Telegram webhook server started host=%s port=%s path=%s webhook_url=%s log=%s",
        host,
        port,
        path,
        public_url,
        log_path
    )
    print(json.dumps({
        "message": "Telegram webhook server started",
        "host": host,
        "port": port,
        "path": path,
        "webhook_url": public_url
    }, ensure_ascii=False))
    server.serve_forever()


if __name__ == "__main__":
    main()
