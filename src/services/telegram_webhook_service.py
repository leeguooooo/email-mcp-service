"""
Telegram webhook handler for interactive digest callbacks.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from .daily_digest_service import DailyDigestService
from .telegram_interactive import TelegramSessionStore, build_inline_keyboard, build_menu_text
from ..account_manager import AccountManager
from .email_service import EmailService

logger = logging.getLogger(__name__)

DEFAULT_TELEGRAM_SESSION_PATH = "data/telegram_sessions.json"
DEFAULT_TELEGRAM_SESSION_TTL_HOURS = 48
DEFAULT_DETAIL_MAX_CHARS = 2000
DEFAULT_AI_SUMMARY_MAX_CHARS = 1200


class TelegramWebhookService:
    def __init__(
        self,
        config_path: Optional[str] = None
    ) -> None:
        self.digest_service = DailyDigestService(config_path=config_path)
        self.config = self.digest_service.config
        self.telegram_cfg = self.config.get("telegram", {})
        self.bot_token = self.telegram_cfg.get("bot_token")
        self.api_base = self.telegram_cfg.get("api_base", "https://api.telegram.org").rstrip("/")
        self.session_store = self._init_session_store()
        self.account_manager = AccountManager()
        self.email_service = EmailService(self.account_manager)
        detail_env = os.getenv("TELEGRAM_DETAIL_MAX_CHARS")
        summary_env = os.getenv("TELEGRAM_AI_SUMMARY_MAX_CHARS")
        self.detail_max_chars = int(detail_env) if detail_env else DEFAULT_DETAIL_MAX_CHARS
        self.ai_summary_max_chars = int(summary_env) if summary_env else DEFAULT_AI_SUMMARY_MAX_CHARS

    def _resolve_repo_path(self, path_str: str) -> str:
        path = Path(path_str)
        if path.is_absolute():
            return str(path)
        repo_root = Path(__file__).resolve().parents[2]
        return str((repo_root / path).resolve())

    def _init_session_store(self) -> Optional[TelegramSessionStore]:
        session_path = os.getenv("TELEGRAM_SESSION_PATH", DEFAULT_TELEGRAM_SESSION_PATH)
        ttl_env = os.getenv("TELEGRAM_SESSION_TTL_HOURS")
        ttl_hours = int(ttl_env) if ttl_env else DEFAULT_TELEGRAM_SESSION_TTL_HOURS
        resolved_path = self._resolve_repo_path(session_path)
        return TelegramSessionStore(resolved_path, ttl_hours=ttl_hours)

    def _telegram_request(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.bot_token:
            return {"success": False, "error": "Missing Telegram bot_token"}
        try:
            response = requests.post(
                f"{self.api_base}/bot{self.bot_token}/{method}",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return {"success": True, "response": response.text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _answer_callback(self, callback_id: str, text: str = "") -> None:
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        self._telegram_request("answerCallbackQuery", payload)

    def _send_message(self, chat_id: int, text: str, parse_mode: Optional[str]) -> None:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        self._telegram_request("sendMessage", payload)

    def _edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: Optional[str],
        reply_markup: Optional[Dict[str, Any]]
    ) -> None:
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        self._telegram_request("editMessageText", payload)

    def _parse_callback_data(self, data: str) -> Tuple[Optional[str], Optional[str], Optional[int]]:
        parts = data.split(":")
        if len(parts) < 3:
            return None, None, None
        action = parts[0]
        session_id = parts[1]
        try:
            index = int(parts[2])
        except ValueError:
            index = None
        return action, session_id, index

    def _build_detail_message(
        self,
        detail: Dict[str, Any],
        summary: Optional[str],
        raw_text: str,
        detail_max_chars: int
    ) -> str:
        subject = detail.get("subject") or "(无主题)"
        sender = detail.get("from") or "unknown"
        account = detail.get("account") or detail.get("account_id") or "unknown"
        date_str = detail.get("date") or ""
        summary_text = summary or "（未生成摘要）"
        if detail_max_chars > 0:
            raw_text = raw_text[:detail_max_chars]
        summary_html = html_lib.escape(summary_text).replace("\n", "<br>")
        raw_html = html_lib.escape(raw_text or "")
        return "\n".join([
            "<b>邮件详情</b>",
            f"<b>主题</b>: {html_lib.escape(subject)}",
            f"<b>发件人</b>: {html_lib.escape(sender)}",
            f"<b>账号</b>: {html_lib.escape(account)}",
            f"<b>时间</b>: {html_lib.escape(date_str)}",
            "",
            "<b>AI 摘要</b>",
            summary_html,
            "",
            "<b>原文节选</b>",
            f"<pre>{raw_html}</pre>"
        ])

    def _handle_detail(self, callback: Dict[str, Any], session_id: str, index: int) -> None:
        if not self.session_store:
            self._answer_callback(callback["id"], "交互会话未启用")
            return
        session = self.session_store.get_session(session_id)
        if not session:
            self._answer_callback(callback["id"], "会话已过期，请重新生成日报")
            return
        items = session.get("items", [])
        if index is None or index < 1 or index > len(items):
            self._answer_callback(callback["id"], "无效序号")
            return
        item = items[index - 1]
        email_id = item.get("id")
        account_id = item.get("account_id")
        folder = item.get("folder") or "INBOX"
        message_id = item.get("message_id")

        detail = self.email_service.get_email_detail(
            email_id=str(email_id),
            folder=folder,
            account_id=account_id,
            message_id=message_id
        )
        if not detail.get("success", True):
            self._answer_callback(callback["id"], "邮件详情获取失败")
            return

        raw_text = self.digest_service.extract_email_text(detail)
        summary = self.digest_service.summarize_single_email(
            subject=detail.get("subject", ""),
            sender=detail.get("from", ""),
            date_str=detail.get("date", ""),
            account=detail.get("account") or detail.get("account_id") or "",
            content=raw_text,
            max_chars=self.ai_summary_max_chars
        )
        message = self._build_detail_message(detail, summary, raw_text, self.detail_max_chars)
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        if chat_id is not None:
            self._send_message(chat_id, message, "HTML")
        self._answer_callback(callback["id"], "已发送详情")

    def _handle_page(self, callback: Dict[str, Any], session_id: str, page: int) -> None:
        if not self.session_store:
            self._answer_callback(callback["id"], "交互会话未启用")
            return
        session = self.session_store.get_session(session_id)
        if not session:
            self._answer_callback(callback["id"], "会话已过期，请重新生成日报")
            return
        items = session.get("items", [])
        base_text = session.get("base_text") or ""
        parse_mode = session.get("parse_mode") or "HTML"
        page_size = int(session.get("page_size", 8))
        text = build_menu_text(
            base_text=base_text,
            items=items,
            page=page,
            page_size=page_size,
            parse_mode=parse_mode
        )
        reply_markup = build_inline_keyboard(
            session_id=session_id,
            page=page,
            total_items=len(items),
            page_size=page_size
        )
        message = callback.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        message_id = message.get("message_id")
        if chat_id is not None and message_id is not None:
            self._edit_message(chat_id, message_id, text, parse_mode, reply_markup)
        self._answer_callback(callback["id"])

    def handle_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        callback = update.get("callback_query")
        if not callback:
            return {"success": True}
        data = callback.get("data", "")
        action, session_id, index = self._parse_callback_data(data)
        if action == "dg":
            self._handle_detail(callback, session_id, index)
        elif action == "dg_page":
            self._handle_page(callback, session_id, index or 1)
        else:
            self._answer_callback(callback.get("id", ""), "未知操作")
        return {"success": True}
