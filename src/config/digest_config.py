"""
Daily digest configuration manager.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .paths import DIGEST_CONFIG_JSON

logger = logging.getLogger(__name__)


class DigestConfigManager:
    """Load/save config for daily email digest."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "schedule": {
            "enabled": True,
            "time": "09:40"
        },
        "email": {
            "account_id": None,
            "folder": "all",
            "unread_only": False,
            "limit": 500
        },
        "classification": {
            "enabled": True,
            "mode": "ai",
            "categories": {
                "work": ["meeting", "project", "deadline", "review", "report"],
                "personal": ["family", "friend", "birthday"],
                "finance": ["invoice", "payment", "bank", "receipt"],
                "urgent": ["urgent", "asap", "immediately"],
                "marketing": ["sale", "discount", "promo", "offer"],
                "newsletter": ["newsletter", "digest", "update"],
                "system": ["alert", "notification", "security", "login"],
                "spam": ["lottery", "winner", "crypto", "loan"]
            },
            "important_categories": ["urgent", "work", "finance"],
            "important_keywords": ["urgent", "important", "asap", "deadline"],
            "ai": {
                "model": "gpt-3.5-turbo",
                "api_key": None,
                "api_key_env": "OPENAI_API_KEY",
                "base_url": None,
                "max_emails": 80,
                "max_body_length": 200
            }
        },
        "summary_ai": {
            "enabled": True,
            "model": "gpt-3.5-turbo",
            "api_key": None,
            "api_key_env": "OPENAI_API_KEY",
            "base_url": None,
            "language": "zh",
            "max_emails": 40
        },
        "debug": {
            "dump_ai_input": False,
            "dump_ai_output": False,
            "path": "data/daily_digest_debug.jsonl",
            "max_preview_length": 400
        },
        "lark": {
            "enabled": True,
            "webhook_url": "",
            "secret": None,
            "title": "Daily Email Digest",
            "max_highlights": 10
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": "",
            "api_base": "https://api.telegram.org",
            "parse_mode": "HTML",
            "webhook_url": None,
            "webhook_secret": None,
            "title": "Daily Email Digest",
            "max_highlights": 10
        }
    }

    def __init__(self, config_file: Optional[str] = None):
        self.config_file = Path(config_file or DIGEST_CONFIG_JSON)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if self.config_file.exists():
            try:
                with self.config_file.open("r", encoding="utf-8") as file:
                    user_config = json.load(file)
                return self._deep_merge(self.DEFAULT_CONFIG.copy(), user_config)
            except Exception as exc:
                logger.error("Failed to load digest config from %s: %s", self.config_file, exc)

        self._ensure_parent_dir()
        self.save_config(self.DEFAULT_CONFIG)
        return self.DEFAULT_CONFIG.copy()

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or self.config
        payload = {
            "_metadata": {
                "version": "1.0",
                "updated_at": datetime.now().isoformat(),
                "description": "Daily email digest configuration"
            },
            **config
        }
        self._ensure_parent_dir()
        with self.config_file.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, ensure_ascii=False)

    def _ensure_parent_dir(self) -> None:
        self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
