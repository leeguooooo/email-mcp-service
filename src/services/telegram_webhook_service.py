"""
Telegram webhook handler for interactive digest callbacks.
"""
from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from .daily_digest_service import DailyDigestService
from .telegram_interactive import TelegramSessionStore, build_inline_keyboard, build_menu_text
from ..account_manager import AccountManager
from .email_service import EmailService
from ..connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

DEFAULT_TELEGRAM_SESSION_PATH = "data/telegram_sessions.json"
DEFAULT_TELEGRAM_SESSION_TTL_HOURS = 48
DEFAULT_DETAIL_MAX_CHARS = 2000
DEFAULT_AI_SUMMARY_MAX_CHARS = 1200
DEFAULT_DETAIL_MESSAGE_MAX_CHARS = 3800
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_SEARCH_MAX_RESULTS = 50
DEFAULT_SEARCH_SUMMARY_COUNT = 5


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
        debug_env = os.getenv("TELEGRAM_DEBUG_LOG")
        if debug_env is None:
            self.debug_log_enabled = True
        else:
            self.debug_log_enabled = debug_env.lower() in {"1", "true", "yes"}
        debug_path = os.getenv("TELEGRAM_DEBUG_LOG_PATH", "data/logs/telegram_debug.jsonl")
        self.debug_log_path = self._resolve_repo_path(debug_path)
        self._folder_cache: Dict[str, Dict[str, Any]] = {}
        cache_ttl_env = os.getenv("TELEGRAM_FOLDER_CACHE_TTL", "300")
        self._folder_cache_ttl = int(cache_ttl_env) if cache_ttl_env.isdigit() else 300
        detail_env = os.getenv("TELEGRAM_DETAIL_MAX_CHARS")
        summary_env = os.getenv("TELEGRAM_AI_SUMMARY_MAX_CHARS")
        message_env = os.getenv("TELEGRAM_DETAIL_MESSAGE_MAX_CHARS")
        self.detail_max_chars = int(detail_env) if detail_env else DEFAULT_DETAIL_MAX_CHARS
        self.ai_summary_max_chars = int(summary_env) if summary_env else DEFAULT_AI_SUMMARY_MAX_CHARS
        self.detail_message_max_chars = (
            int(message_env) if message_env else DEFAULT_DETAIL_MESSAGE_MAX_CHARS
        )

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

    def _write_debug_log(self, event: str, payload: Dict[str, Any]) -> None:
        if not self.debug_log_enabled:
            return
        try:
            log_dir = os.path.dirname(self.debug_log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            record = {
                "ts": datetime.now().isoformat(),
                "event": event,
                **payload
            }
            with open(self.debug_log_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.debug("Failed to write debug log: %s", exc)

    def _telegram_request(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.bot_token:
            return {"success": False, "error": "Missing Telegram bot_token"}
        try:
            self._write_debug_log("telegram_request", {
                "method": method,
                "payload": payload
            })
            response = requests.post(
                f"{self.api_base}/bot{self.bot_token}/{method}",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            result = {"success": True, "response": response.text, "status_code": response.status_code}
            self._write_debug_log("telegram_response", {
                "method": method,
                "status_code": response.status_code,
                "response_text": response.text
            })
            try:
                data = response.json()
            except json.JSONDecodeError:
                return result
            if isinstance(data, dict) and not data.get("ok", True):
                logger.warning("Telegram API error: %s", response.text)
            return result
        except requests.HTTPError as exc:
            response_text = ""
            if exc.response is not None:
                response_text = exc.response.text
            self._write_debug_log("telegram_response_error", {
                "method": method,
                "error": str(exc),
                "response_text": response_text
            })
            logger.warning("Telegram API request failed: %s response=%s", exc, response_text)
            return {"success": False, "error": str(exc), "response": response_text}
        except Exception as exc:
            self._write_debug_log("telegram_response_error", {
                "method": method,
                "error": str(exc)
            })
            logger.warning("Telegram API request failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def _get_ai_client(self) -> Optional[Tuple[Any, Dict[str, Any]]]:
        cfg = self.config.get("summary_ai", {})
        if not cfg.get("enabled", True):
            return None
        api_key = cfg.get("api_key") or os.getenv(cfg.get("api_key_env", "OPENAI_API_KEY"))
        if not api_key:
            return None
        try:
            import openai
        except ImportError:
            return None
        client = openai.OpenAI(
            api_key=api_key,
            base_url=cfg.get("base_url")
        )
        return client, cfg

    def _answer_callback(self, callback_id: str, text: str = "") -> None:
        payload = {"callback_query_id": callback_id}
        if text:
            payload["text"] = text
        self._telegram_request("answerCallbackQuery", payload)

    def _strip_html_markup(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"(?s)<[^>]+>", "", text)
        return html_lib.unescape(cleaned)

    def _send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str],
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> bool:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
        result = self._telegram_request("sendMessage", payload)
        if result.get("success"):
            return True
        logger.warning("Telegram sendMessage failed: %s", result)
        if parse_mode:
            fallback_text = text
            if parse_mode.lower() == "html":
                fallback_text = self._strip_html_markup(text)
            fallback_payload = dict(payload)
            fallback_payload["text"] = fallback_text
            fallback_payload.pop("parse_mode", None)
            retry = self._telegram_request("sendMessage", fallback_payload)
            if not retry.get("success"):
                logger.warning("Telegram sendMessage retry failed: %s", retry)
                return False
            return True
        return False

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
        summary_html = html_lib.escape(summary_text)
        raw_html = html_lib.escape(raw_text or "")
        prefix_lines = [
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
            "<pre>"
        ]
        prefix = "\n".join(prefix_lines)
        suffix = "</pre>"
        max_len = self.detail_message_max_chars
        available = max_len - len(prefix) - len(suffix)
        if available < 0:
            available = 0
        if len(raw_html) > available:
            trimmed = raw_html[: max(0, available - 3)]
            raw_html = f"{trimmed}..."
        return f"{prefix}{raw_html}{suffix}"

    def _send_detail_for_session(
        self,
        session: Dict[str, Any],
        index: int,
        chat_id: Optional[int]
    ) -> bool:
        items = session.get("items", [])
        if index is None or index < 1 or index > len(items):
            logger.info("Telegram detail index invalid: %s (items=%s)", index, len(items))
            return False
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
            logger.info(
                "Telegram detail fetch failed: account=%s email_id=%s folder=%s",
                account_id,
                email_id,
                folder
            )
            return False

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
        if chat_id is not None:
            self._send_message(chat_id, message, "HTML")
            logger.info("Telegram detail sent chat_id=%s index=%s", chat_id, index)
        return True

    def _handle_detail(self, callback: Dict[str, Any], session_id: str, index: int) -> None:
        if not self.session_store:
            self._answer_callback(callback["id"], "交互会话未启用")
            return
        session = self.session_store.get_session(session_id)
        if not session:
            self._answer_callback(callback["id"], "会话已过期，请重新生成日报")
            return
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        if chat_id is None:
            self._answer_callback(callback["id"], "无法获取聊天信息")
            return
        logger.info(
            "Telegram detail requested session=%s index=%s chat_id=%s",
            session_id,
            index,
            chat_id
        )
        self._answer_callback(callback["id"], "处理中，请稍等")

        def _worker() -> None:
            if not self._send_detail_for_session(session, index, chat_id):
                self._send_message(chat_id, "邮件详情获取失败，请稍后重试。", None)

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_page(self, callback: Dict[str, Any], session_id: str, page: int) -> None:
        if not self.session_store:
            self._answer_callback(callback["id"], "交互会话未启用")
            return
        session = self.session_store.get_session(session_id)
        if not session:
            self._answer_callback(callback["id"], "会话已过期，请重新生成日报")
            return
        logger.info("Telegram page requested session=%s page=%s", session_id, page)
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
            self.session_store.update_session(session_id, {
                "current_page": page,
                "chat_id": chat_id,
                "message_id": message_id
            })
        self._answer_callback(callback["id"])

    def _send_menu_for_session(self, chat_id: int, session_id: str, session: Dict[str, Any], page: int) -> None:
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
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        payload["reply_markup"] = reply_markup
        self._telegram_request("sendMessage", payload)
        if self.session_store:
            self.session_store.update_session(session_id, {
                "current_page": page,
                "chat_id": chat_id
            })

    def _build_session_items(self, emails: list[Dict[str, Any]], max_items: int) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        for email in emails:
            email_id = email.get("id") or email.get("uid")
            account_id = email.get("account_id") or email.get("account")
            if not email_id or not account_id:
                continue
            account = email.get("account") or account_id
            items.append({
                "id": str(email_id),
                "account_id": account_id,
                "account": account,
                "folder": email.get("folder") or "INBOX",
                "message_id": email.get("message_id"),
                "subject": email.get("subject") or "",
                "subject_cn": email.get("subject_cn") or "",
                "from": email.get("from") or "",
                "date": email.get("date") or ""
            })
            if len(items) >= max_items:
                break
        return items

    def _execute_search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = (args.get("query") or "").strip()
        search_in = (args.get("search_in") or "all").strip().lower()
        if search_in not in {"subject", "from", "body", "to", "all"}:
            search_in = "all"
        limit = args.get("limit")
        if limit is None:
            limit = DEFAULT_SEARCH_LIMIT
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = DEFAULT_SEARCH_LIMIT
        max_limit = int(os.getenv("TELEGRAM_SEARCH_MAX_RESULTS", str(DEFAULT_SEARCH_MAX_RESULTS)))
        limit = max(1, min(limit, max_limit))
        email_cfg = self.config.get("email", {})
        folder = email_cfg.get("folder", "all")
        raw_text = (args.get("_raw_text") or "").strip()
        tokens, primary_tokens = self._build_search_tokens(query, raw_text)
        tokens_to_use = primary_tokens or tokens
        if len(tokens) <= 1:
            return self.email_service.search_emails(
                query=query or None,
                search_in=search_in,
                date_from=args.get("date_from"),
                date_to=args.get("date_to"),
                folder=folder,
                unread_only=bool(args.get("unread_only", False)),
                has_attachments=args.get("has_attachments"),
                limit=limit,
                account_id=args.get("account_id"),
                offset=0
            )

        combined: Dict[str, Dict[str, Any]] = {}
        failed_accounts = []
        ascii_tokens = [token for token in tokens_to_use if token and all(ord(ch) < 128 for ch in token)]
        imap_tokens = ascii_tokens if ascii_tokens else []
        for token in imap_tokens:
            token_search_in = self._search_scope_for_token(token, search_in)
            result = self.email_service.search_emails(
                query=token,
                search_in=token_search_in,
                date_from=args.get("date_from"),
                date_to=args.get("date_to"),
                folder=folder,
                unread_only=bool(args.get("unread_only", False)),
                has_attachments=args.get("has_attachments"),
                limit=limit,
                account_id=args.get("account_id"),
                offset=0
            )
            if not result.get("success", False):
                failed_accounts.extend(result.get("failed_accounts", []))
                continue
            for email in result.get("emails", []) or []:
                key = f"{email.get('account_id') or ''}:{email.get('id') or email.get('uid') or ''}"
                if key == ":":
                    continue
                combined[key] = email

        if not combined and folder in {"all", "INBOX"}:
            extra_limit = max(limit, int(os.getenv("TELEGRAM_SEARCH_FALLBACK_LIMIT", "200")))
            date_days = self._estimate_date_days(args.get("date_from"), args.get("date_to"))
            if date_days and date_days > 45:
                extra_limit = max(extra_limit, 400)
            extra_result = self._search_extra_folders(
                args=args,
                tokens=imap_tokens,
                search_in=search_in,
                limit=extra_limit
            )
            failed_accounts.extend(extra_result.get("failed_accounts", []))
            for email in extra_result.get("emails", []) or []:
                key = f"{email.get('account_id') or ''}:{email.get('id') or email.get('uid') or ''}"
                if key == ":":
                    continue
                combined[key] = email

        emails = list(combined.values())
        emails.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
        if limit > 0:
            emails = emails[:limit]
        needs_unicode_fallback = any(ord(ch) > 127 for ch in raw_text) or any(
            any(ord(ch) > 127 for ch in token) for token in tokens_to_use
        )
        if not emails and needs_unicode_fallback:
            fallback_limit = int(os.getenv("TELEGRAM_SEARCH_FALLBACK_LIMIT", "200"))
            date_days = self._estimate_date_days(args.get("date_from"), args.get("date_to"))
            if date_days and date_days > 45:
                fallback_limit = max(fallback_limit, 400)
            fallback_limit = max(limit, min(fallback_limit, max_limit * 8))
            fallback_result = self.email_service.search_emails(
                query=None,
                search_in="all",
                date_from=args.get("date_from"),
                date_to=args.get("date_to"),
                folder=folder,
                unread_only=bool(args.get("unread_only", False)),
                has_attachments=args.get("has_attachments"),
                limit=fallback_limit,
                account_id=args.get("account_id"),
                offset=0
            )
            if fallback_result.get("success", False):
                fallback_emails = fallback_result.get("emails", []) or []
                filtered = self._filter_search_results(
                    fallback_emails,
                    query or raw_text,
                    "all",
                    raw_text=raw_text
                )
                if filtered:
                    emails = filtered[:limit]
        return {
            "success": True,
            "emails": emails,
            "total_found": len(emails),
            "failed_accounts": failed_accounts,
            "primary_tokens": primary_tokens,
            "search_tokens": tokens
        }

    def _estimate_date_days(self, date_from: Optional[str], date_to: Optional[str]) -> Optional[int]:
        if not date_from and not date_to:
            return None
        try:
            end = datetime.strptime(date_to, "%Y-%m-%d") if date_to else datetime.now()
            start = datetime.strptime(date_from, "%Y-%m-%d") if date_from else end - timedelta(days=30)
            delta = end - start
            return max(0, delta.days)
        except Exception:
            return None

    def _normalize_folder_name(self, name: str) -> str:
        return "".join(ch.lower() for ch in name if ch.isalnum())

    def _extract_list_folder(self, raw_folder: bytes | str) -> Optional[str]:
        try:
            decoded = raw_folder.decode("utf-8", errors="ignore") if isinstance(raw_folder, bytes) else str(raw_folder)
        except Exception:
            decoded = str(raw_folder)
        matches = re.findall(r"\"([^\"]+)\"", decoded)
        if matches:
            return matches[-1]
        parts = decoded.split()
        if parts:
            return parts[-1].strip('"')
        return None

    def _list_account_folders(self, account_id: str) -> list[str]:
        if not account_id:
            return []
        now = time.time()
        cached = self._folder_cache.get(account_id)
        if cached and now - cached.get("ts", 0) < self._folder_cache_ttl:
            return cached.get("folders", [])
        account = self.account_manager.get_account(account_id)
        if not account:
            return []
        folders: list[str] = []
        conn_mgr = ConnectionManager(account)
        try:
            mail = conn_mgr.connect_imap()
            try:
                status, data = mail.list()
                if status == "OK" and data:
                    for entry in data:
                        name = self._extract_list_folder(entry)
                        if name:
                            folders.append(name)
            finally:
                try:
                    mail.logout()
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("List folders failed for %s: %s", account.get("email"), exc)
        self._folder_cache[account_id] = {"ts": now, "folders": folders}
        return folders

    def _search_extra_folders(
        self,
        args: Dict[str, Any],
        tokens: list[str],
        search_in: str,
        limit: int
    ) -> Dict[str, Any]:
        extra_folders = [
            "[Gmail]/All Mail",
            "All Mail",
            "Archive",
            "Spam",
            "Junk",
            "垃圾邮件",
            "广告邮件",
            "订阅邮件",
            "&V4NXPpCuTvY-",
            "&Xn9USpCuTvY-",
            "&i6KWBZCuTvY-",
            "&ZeB1KJCuTvY-"
        ]
        combined: Dict[str, Dict[str, Any]] = {}
        failed_accounts = []
        account_ids: list[str] = []
        account_id = args.get("account_id") or ""
        if account_id:
            account_ids = [account_id]
        else:
            for account in self.account_manager.list_accounts():
                acc_id = account.get("id")
                if acc_id:
                    account_ids.append(acc_id)

        for acc_id in account_ids:
            available = self._list_account_folders(acc_id)
            if not available:
                continue
            available_map = {self._normalize_folder_name(name): name for name in available}
            valid_folders: list[str] = []
            for candidate in extra_folders:
                key = self._normalize_folder_name(candidate)
                actual = available_map.get(key)
                if actual and actual not in valid_folders:
                    valid_folders.append(actual)
            if not valid_folders:
                continue
            token_list = tokens or [None]
            for folder in valid_folders:
                for token in token_list:
                    token_search_in = self._search_scope_for_token(token or "", search_in)
                    result = self.email_service.search_emails(
                        query=token,
                        search_in=token_search_in,
                        date_from=args.get("date_from"),
                        date_to=args.get("date_to"),
                        folder=folder,
                        unread_only=bool(args.get("unread_only", False)),
                        has_attachments=args.get("has_attachments"),
                        limit=limit,
                        account_id=acc_id,
                        offset=0
                    )
                    if not result.get("success", False):
                        failed_accounts.extend(result.get("failed_accounts", []))
                        continue
                    for email in result.get("emails", []) or []:
                        key = f"{email.get('account_id') or ''}:{email.get('id') or email.get('uid') or ''}"
                        if key == ":":
                            continue
                        combined[key] = email
                if len(combined) >= limit:
                    break
            if len(combined) >= limit:
                break
        emails = list(combined.values())
        emails.sort(key=lambda item: item.get("timestamp", 0), reverse=True)
        if limit > 0:
            emails = emails[:limit]
        return {
            "success": True,
            "emails": emails,
            "failed_accounts": failed_accounts
        }

    def _search_scope_for_token(self, token: str, default_scope: str) -> str:
        if default_scope != "all":
            return default_scope
        token = (token or "").strip()
        if not token:
            return default_scope
        if "@" in token:
            return "from"
        if re.search(r"\b[\w\-]+\.[a-z]{2,}\b", token, re.IGNORECASE):
            return "from"
        return default_scope

    def _parse_chinese_number(self, token: str) -> Optional[int]:
        if not token:
            return None
        if token.isdigit():
            return int(token)
        mapping = {
            "零": 0,
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10
        }
        if token in mapping:
            return mapping[token]
        if "十" in token:
            parts = token.split("十")
            tens = 1 if parts[0] == "" else mapping.get(parts[0], 0)
            ones = 0 if len(parts) == 1 or parts[1] == "" else mapping.get(parts[1], 0)
            return tens * 10 + ones
        return None

    def _extract_search_args(self, text: str) -> Dict[str, Any]:
        lowered = text.lower()
        search_in = "all"
        if "标题" in text or "subject" in lowered:
            search_in = "subject"
        elif "发件人" in text or "from" in lowered:
            search_in = "from"
        elif "正文" in text or "内容" in text or "body" in lowered:
            search_in = "body"

        query = ""
        quoted = re.findall(r"[\"“”‘’']([^\"“”‘’']+)[\"“”‘’']", text)
        if quoted:
            query = quoted[0].strip()
        if not query:
            pattern = r"(?:搜索|查找|找|关于|有关|相关|查)\s*([A-Za-z0-9_\-\u4e00-\u9fff]+)"
            match = re.search(pattern, text)
            if match:
                query = match.group(1).strip()
        if not query:
            query = text.strip()

        date_from = None
        date_to = None
        rel = re.search(r"(最近|过去|近)\s*([0-9一二两三四五六七八九十]+)\s*(天|周|月|年)", text)
        if rel:
            value = self._parse_chinese_number(rel.group(2))
            unit = rel.group(3)
            if value:
                days = value
                if unit == "周":
                    days = value * 7
                elif unit == "月":
                    days = value * 30
                elif unit == "年":
                    days = value * 365
                date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                date_to = datetime.now().strftime("%Y-%m-%d")
        elif "今天" in text:
            date_from = datetime.now().strftime("%Y-%m-%d")
            date_to = date_from
        elif "昨天" in text or "昨日" in text:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            date_from = date
            date_to = date

        return {
            "query": query,
            "search_in": search_in,
            "date_from": date_from,
            "date_to": date_to
        }

    def _build_search_tokens(self, query: str, raw_text: str) -> Tuple[List[str], List[str]]:
        tokens: List[str] = []
        primary_tokens: List[str] = []
        text = raw_text or query or ""
        lowered = text.lower()
        if re.search(r"tokyo\s*gas|東京|东京", text, re.IGNORECASE):
            primary_tokens = [
                "official-enews@mail.tokyo-gas.co.jp",
                "mail.tokyo-gas.co.jp",
                "tokyo-gas.co.jp",
                "tokyo gas",
                "tokyo-gas",
                "東京ガス",
                "东京燃气"
            ]
            tokens.extend(primary_tokens)
            tokens.extend(["天然气", "天然ガス", "ガス料金", "都市ガス"])
        else:
            tokens.append(query or text)

        cleaned: List[str] = []
        for token in tokens:
            token = re.sub(r"[\"'()]", " ", token)
            token = re.sub(r"\bor\b", " ", token, flags=re.IGNORECASE)
            token = re.sub(r"\s+", " ", token).strip()
            if not token:
                continue
            cleaned.append(token)

        primary_set = set()
        if primary_tokens:
            for token in primary_tokens:
                token = re.sub(r"[\"'()]", " ", token)
                token = re.sub(r"\bor\b", " ", token, flags=re.IGNORECASE)
                token = re.sub(r"\s+", " ", token).strip()
                if token:
                    primary_set.add(token)

        priority: List[str] = []
        secondary: List[str] = []
        for token in cleaned:
            has_domain = "@" in token or re.search(r"\b[\w\-]+\.[a-z]{2,}\b", token, re.IGNORECASE)
            if primary_tokens:
                if token in primary_set or has_domain:
                    priority.append(token)
                else:
                    secondary.append(token)
            else:
                if any(ord(ch) > 127 for ch in token) or has_domain:
                    priority.append(token)
                else:
                    secondary.append(token)

        expanded: List[str] = []
        expanded.extend(priority)
        for token in secondary:
            expanded.append(token)
            if " " in token:
                expanded.extend(part for part in token.split() if part)

        deduped: List[str] = []
        for token in expanded:
            if token and token not in deduped:
                deduped.append(token)

        limit = max(6, len(priority))
        limited = deduped[:limit]
        return limited, primary_tokens

    def _render_search_summary(
        self,
        query: str,
        search_in: str,
        total_found: int,
        displayed: int
    ) -> str:
        esc = self.digest_service._escape_telegram_html
        scope_map = {
            "subject": "标题",
            "from": "发件人",
            "body": "正文",
            "to": "收件人",
            "all": "全部"
        }
        scope = scope_map.get(search_in, "全部")
        lines = [
            "<b>搜索结果</b>",
            f"关键词：<code>{esc(query)}</code>",
            f"范围：{scope}",
            f"匹配：<b>{total_found}</b>（展示 {displayed}）"
        ]
        return "\n".join(lines)

    def _extract_search_args_with_ai(
        self,
        text: str,
        client: Any,
        cfg: Dict[str, Any]
    ) -> Dict[str, Any]:
        prompt = (
            "从用户的中文搜索请求中提取检索参数，输出 JSON。\n"
            "字段：query, search_in(subject/from/body/to/all), date_from(YYYY-MM-DD),"
            " date_to(YYYY-MM-DD), limit(1-50)。\n"
            "如果未提及，字段可省略。只输出 JSON，不要解释。\n"
            f"用户请求：{text}"
        )
        response = client.chat.completions.create(
            model=cfg.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "你是检索参数抽取器。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=200
        )
        content = (response.choices[0].message.content or "").strip()
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        return {}

    def _send_search_results(
        self,
        chat_id: int,
        args: Dict[str, Any],
        result: Dict[str, Any]
    ) -> None:
        emails = result.get("emails", []) or []
        query = (args.get("query") or "").strip()
        raw_text = (args.get("_raw_text") or "").strip()
        search_in = (args.get("search_in") or "all").strip().lower()
        filtered = self._filter_search_results(emails, query, search_in, raw_text=raw_text)
        emails = filtered
        total_found = len(emails) if emails else 0
        if emails:
            max_items = int(os.getenv("TELEGRAM_MAX_ITEMS", str(DEFAULT_SEARCH_MAX_RESULTS)))
            self.digest_service._apply_subject_translations(emails, max_items)
        base_text = self._render_search_summary(
            query=query,
            search_in=search_in,
            total_found=total_found,
            displayed=len(emails)
        )
        if total_found == 0:
            base_text = f"{base_text}\n未找到匹配邮件。"
        content = base_text
        reply_markup = None
        if emails and self.session_store:
            items = self._build_session_items(emails, max_items=len(emails))
            if items:
                session_id = os.urandom(6).hex()
                page_size = len(items)
                content = build_menu_text(
                    base_text=base_text,
                    items=items,
                    page=1,
                    page_size=page_size,
                    parse_mode="HTML"
                )
                reply_markup = build_inline_keyboard(
                    session_id=session_id,
                    page=1,
                    total_items=len(items),
                    page_size=page_size
                )
                self.session_store.save_session(session_id, {
                    "created_at": datetime.now().isoformat(),
                    "base_text": base_text,
                    "parse_mode": "HTML",
                    "page_size": page_size,
                    "current_page": 1,
                    "items": items,
                    "chat_id": chat_id
                })
        self._send_message(chat_id, content, "HTML", reply_markup)

    def _filter_search_results(
        self,
        emails: list[Dict[str, Any]],
        query: str,
        search_in: str,
        raw_text: str = ""
    ) -> list[Dict[str, Any]]:
        if not query and raw_text:
            query = raw_text
        if not query:
            return emails
        tokens, primary_tokens = self._build_search_tokens(query, raw_text)
        if primary_tokens:
            tokens = primary_tokens
        if not tokens:
            return emails
        fields = []
        if search_in in {"subject", "from", "to", "body"}:
            fields = [search_in]
        else:
            fields = ["subject", "from", "to", "body"]

        filtered = []
        for email in emails:
            parts = []
            if "subject" in fields:
                parts.append(email.get("subject", ""))
                parts.append(email.get("subject_cn", ""))
            if "from" in fields:
                parts.append(email.get("from", ""))
            if "to" in fields:
                parts.append(email.get("to", ""))
            if "body" in fields:
                parts.append(email.get("preview", ""))
            haystack = " ".join(part for part in parts if part)
            if not haystack:
                continue
            hay_lower = haystack.lower()
            matched = False
            for token in tokens:
                if any(ord(ch) > 127 for ch in token):
                    if token in haystack:
                        matched = True
                        break
                else:
                    if token.lower() in hay_lower:
                        matched = True
                        break
            if matched:
                filtered.append(email)
        return filtered

    def _handle_ai_command(self, chat_id: int, text: str) -> bool:
        client_cfg = self._get_ai_client()
        search_intent = bool(re.search(r"(搜索|查找|找|search)", text, re.IGNORECASE))
        if not search_intent and re.fullmatch(r"[\w\u4e00-\u9fff\-]{1,20}", text):
            search_intent = True
        if search_intent:
            self._send_message(chat_id, "正在搜索，请稍等…", None)
        if not client_cfg:
            if search_intent:
                self._send_message(chat_id, "AI 未配置，无法执行智能搜索。", None)
                return True
            return False
        client, cfg = client_cfg
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_emails",
                    "description": "在所有邮箱中搜索邮件，返回匹配结果。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"},
                            "search_in": {
                                "type": "string",
                                "enum": ["subject", "from", "body", "to", "all"],
                                "description": "搜索范围"
                            },
                            "account_id": {"type": "string", "description": "指定账号 ID（可选）"},
                            "limit": {"type": "integer", "description": "最多返回数量（1-50）"},
                            "date_from": {"type": "string", "description": "开始日期 YYYY-MM-DD（可选）"},
                            "date_to": {"type": "string", "description": "结束日期 YYYY-MM-DD（可选）"},
                            "unread_only": {"type": "boolean", "description": "只搜未读（可选）"},
                            "has_attachments": {"type": "boolean", "description": "只搜有附件（可选）"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
        system_prompt = (
            "你是 Telegram 邮件助手。"
            "若用户输入是关键词、短语或明确提出搜索/查找/找邮件，必须调用 search_emails 工具。"
            "若不是搜索意图，给出简短中文提示，说明可用的搜索方式（例如：搜索 gas）。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]
        must_search = search_intent
        tool_choice = {"type": "function", "function": {"name": "search_emails"}} if must_search else "auto"
        self._write_debug_log("ai_request", {
            "chat_id": chat_id,
            "model": cfg.get("model", "gpt-3.5-turbo"),
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice
        })
        try:
            response = client.chat.completions.create(
                model=cfg.get("model", "gpt-3.5-turbo"),
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                temperature=0.2,
                max_tokens=400
            )
        except Exception as exc:
            self._write_debug_log("ai_request_error", {
                "chat_id": chat_id,
                "error": str(exc)
            })
            logger.warning("Telegram AI tool request failed: %s", exc)
            if search_intent:
                args = self._extract_search_args(text)
                result = self._execute_search(args)
                if not result.get("success", False):
                    self._send_message(chat_id, "搜索失败，请稍后重试。", None)
                    return True
                self._send_search_results(chat_id, args, result)
                return True
            return False
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None) or []
        self._write_debug_log("ai_response", {
            "chat_id": chat_id,
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}"
                }
                for call in tool_calls
            ]
        })
        logger.info(
            "Telegram AI tool_calls=%s content_len=%s",
            len(tool_calls),
            len(message.content or "")
        )
        if not tool_calls:
            if search_intent:
                args = self._extract_search_args(text)
                if client_cfg:
                    ai_args = self._extract_search_args_with_ai(text, client, cfg)
                    if ai_args:
                        for key, value in ai_args.items():
                            if value not in (None, "", []):
                                args[key] = value
                args["_raw_text"] = text
                result = self._execute_search(args)
                self._write_debug_log("ai_search_fallback", {
                    "chat_id": chat_id,
                    "args": args,
                    "result": {
                        "success": result.get("success", False),
                        "total_found": result.get("total_found"),
                        "search_tokens": result.get("search_tokens"),
                        "primary_tokens": result.get("primary_tokens")
                    }
                })
                if not result.get("success", False):
                    self._send_message(chat_id, "搜索失败，请稍后重试。", None)
                    return True
                self._send_search_results(chat_id, args, result)
                return True
            if message.content:
                content = self.digest_service._sanitize_telegram_html(message.content.strip())
                self._send_message(chat_id, content, "HTML")
                return True
            return False

        assistant_payload = {
            "role": "assistant",
            "content": message.content or ""
        }
        assistant_tool_calls = []
        for call in tool_calls:
            assistant_tool_calls.append({
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments or "{}"
                }
            })
        if assistant_tool_calls:
            assistant_payload["tool_calls"] = assistant_tool_calls

        for tool_call in tool_calls:
            if tool_call.function.name != "search_emails":
                continue
            try:
                args = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                self._send_message(chat_id, "搜索参数解析失败，请换个说法。", None)
                return True
            if not (args.get("query") or "").strip():
                fallback_args = self._extract_search_args(text)
                for key, value in fallback_args.items():
                    if value not in (None, "", []):
                        args[key] = value
            if not (args.get("query") or "").strip():
                self._send_message(chat_id, "请提供要搜索的关键词，例如：搜索 gas", None)
                return True
            args["_raw_text"] = text
            result = self._execute_search(args)
            self._write_debug_log("ai_tool_call", {
                "chat_id": chat_id,
                "tool": tool_call.function.name,
                "args": args,
                "result": {
                    "success": result.get("success", False),
                    "total_found": result.get("total_found"),
                    "search_tokens": result.get("search_tokens"),
                    "primary_tokens": result.get("primary_tokens")
                }
            })
            if not result.get("success", False):
                self._send_message(chat_id, "搜索失败，请稍后重试。", None)
                return True
            self._send_search_results(chat_id, args, result)
            return True
        return False

    def _handle_text_command(self, message: Dict[str, Any]) -> None:
        if not self.session_store:
            return
        chat_id = message.get("chat", {}).get("id")
        if chat_id is None:
            return
        text = (message.get("text") or "").strip()
        if not text:
            return
        if text in {"/start", "/help", "帮助", "指令"}:
            help_text = "\n".join([
                "可用指令：",
                "- 今日：生成今日邮件日报",
                "- 昨日：生成昨日邮件日报",
                "- 本周：生成本周邮件日报",
                "- 搜索 关键词：搜索所有邮箱",
                "- 菜单：查看详情索引",
                "- 1/2/3...：查看对应序号邮件详情"
            ])
            self._send_message(chat_id, help_text, None)
            return
        range_map = {
            "今日": "today",
            "今天": "today",
            "昨日": "yesterday",
            "昨天": "yesterday",
            "本周": "week",
            "本週": "week"
        }
        range_key = range_map.get(text)
        if range_key:
            self._send_message(chat_id, "正在生成日报，请稍等…", None)

            def _worker() -> None:
                try:
                    result = self.digest_service.run(dry_run=True, range_key=range_key)
                except Exception as exc:
                    logger.exception("Telegram digest command failed: %s", exc)
                    self._send_message(chat_id, "日报生成失败，请稍后重试。", None)
                    return
                message_text = result.get("telegram_message") or "日报生成失败，请稍后重试。"
                parse_mode = result.get("telegram_parse_mode") or "HTML"
                reply_markup = None
                session_id = result.get("telegram_session_id")
                if session_id and self.session_store:
                    session = self.session_store.get_session(session_id)
                    if session:
                        items = session.get("items", [])
                        page_size = int(session.get("page_size", 8))
                        reply_markup = build_inline_keyboard(
                            session_id=session_id,
                            page=1,
                            total_items=len(items),
                            page_size=page_size
                        )
                self._send_message(chat_id, message_text, parse_mode, reply_markup)

            threading.Thread(target=_worker, daemon=True).start()
            return

        latest = self.session_store.get_latest_session_for_chat(chat_id)
        if not latest:
            if re.fullmatch(r"\d{1,3}", text):
                self._send_message(chat_id, "未找到可用的日报会话，请先发送日报。", None)
                return
            if self._handle_ai_command(chat_id, text):
                return
            self._send_message(chat_id, "未找到可用的日报会话，请先发送日报。", None)
            return
        session_id, session = latest
        lower = text.lower()

        match = re.search(r"(?:查看|详情|detail)?\\s*(\\d+)$", text, re.IGNORECASE)
        if match:
            index = int(match.group(1))
            if not self._send_detail_for_session(session, index, chat_id):
                self._send_message(chat_id, "未找到该序号的邮件。", None)
            return

        if self._handle_ai_command(chat_id, text):
            return

        if lower in {"菜单", "列表", "索引"}:
            page = int(session.get("current_page", 1))
            self._send_menu_for_session(chat_id, session_id, session, page)
            return

        if lower in {"下一页", "下页", "next"}:
            page = int(session.get("current_page", 1)) + 1
            self._send_menu_for_session(chat_id, session_id, session, page)
            return

        if lower in {"上一页", "上页", "prev"}:
            page = int(session.get("current_page", 1)) - 1
            if page < 1:
                page = 1
            self._send_menu_for_session(chat_id, session_id, session, page)
            return

    def handle_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        callback = update.get("callback_query")
        if not callback:
            message = update.get("message")
            if message and message.get("text"):
                self._handle_text_command(message)
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
