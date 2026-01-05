"""
Daily email digest service.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import quopri
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from email import utils as email_utils
from typing import Any, Dict, List, Optional, Tuple

import requests

from ..config.digest_config import DigestConfigManager
from ..config.paths import DIGEST_CONFIG_JSON
from .telegram_interactive import (
    TelegramSessionStore,
    build_inline_keyboard,
    build_menu_text
)

logger = logging.getLogger(__name__)

DEFAULT_TELEGRAM_SESSION_PATH = "data/telegram_sessions.json"
DEFAULT_TELEGRAM_SESSION_TTL_HOURS = 48
DEFAULT_TELEGRAM_PAGE_SIZE = 8
DEFAULT_TELEGRAM_MAX_ITEMS = 40


class DailyDigestService:
    """Daily digest workflow for yesterday's emails."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        config_manager: Optional[DigestConfigManager] = None
    ):
        if config_manager:
            self.config_manager = config_manager
        else:
            self.config_manager = DigestConfigManager(config_path or DIGEST_CONFIG_JSON)
        self.config = self.config_manager.config
        self._debug_config: Dict[str, Any] = {}
        self._telegram_session_store: Optional[TelegramSessionStore] = None
        self._telegram_webhook_checked = False
        self._telegram_webhook_url: Optional[str] = None

    def _resolve_repo_path(self, path_str: str) -> Path:
        path = Path(path_str)
        if path.is_absolute():
            return path
        repo_root = Path(__file__).resolve().parents[2]
        return (repo_root / path).resolve()

    def _get_session_store(self) -> Optional[TelegramSessionStore]:
        if not self._telegram_interactive_enabled():
            return None
        session_path = os.getenv("TELEGRAM_SESSION_PATH", DEFAULT_TELEGRAM_SESSION_PATH)
        ttl_env = os.getenv("TELEGRAM_SESSION_TTL_HOURS")
        ttl_hours = int(ttl_env) if ttl_env else DEFAULT_TELEGRAM_SESSION_TTL_HOURS
        resolved_path = self._resolve_repo_path(session_path)
        if not self._telegram_session_store:
            self._telegram_session_store = TelegramSessionStore(
                path=str(resolved_path),
                ttl_hours=ttl_hours
            )
        return self._telegram_session_store

    def _telegram_interactive_enabled(self) -> bool:
        telegram_cfg = self.config.get("telegram", {})
        if not telegram_cfg.get("enabled", False):
            return False
        env_value = os.getenv("TELEGRAM_INTERACTIVE", "").strip().lower()
        if env_value in {"1", "true", "yes", "on"}:
            return True
        if env_value in {"0", "false", "no", "off"}:
            return False
        webhook_url = telegram_cfg.get("webhook_url") or self._get_telegram_webhook_url()
        return bool(webhook_url)

    def _get_telegram_webhook_url(self) -> Optional[str]:
        if self._telegram_webhook_checked:
            return self._telegram_webhook_url
        self._telegram_webhook_checked = True
        telegram_cfg = self.config.get("telegram", {})
        bot_token = telegram_cfg.get("bot_token")
        if not bot_token:
            return None
        configured = telegram_cfg.get("webhook_url")
        if configured:
            self._telegram_webhook_url = configured
            return configured
        api_base = telegram_cfg.get("api_base", "https://api.telegram.org").rstrip("/")
        try:
            response = requests.post(
                f"{api_base}/bot{bot_token}/getWebhookInfo",
                json={},
                timeout=8
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("ok"):
                url = payload.get("result", {}).get("url")
                if url:
                    self._telegram_webhook_url = url
        except Exception as exc:
            logger.debug("Failed to check Telegram webhook: %s", exc)
        return self._telegram_webhook_url

    def _resolve_debug_config(self, override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        base = self.config.get("debug", {})
        if not isinstance(base, dict):
            base = {}
        if not override:
            return dict(base)
        merged = dict(base)
        merged.update(override)
        return merged

    def _debug_enabled(self, key: str) -> bool:
        return bool(self._debug_config.get(key))

    def _resolve_debug_path(self) -> Path:
        override = self._debug_config.get("path")
        if override:
            return Path(override)
        return self.config_manager.config_file.parent / "daily_digest_debug.jsonl"

    def _write_debug_event(self, event: str, payload: Dict[str, Any]) -> None:
        path = self._resolve_debug_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(),
            "event": event,
            **payload
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _debug_snapshot(
        self,
        emails: List[Dict[str, Any]],
        max_len: int
    ) -> List[Dict[str, Any]]:
        snapshots = []
        for email in emails:
            preview = self._get_preview(email, max_len=max_len)
            snapshots.append({
                "id": email.get("id"),
                "subject": email.get("subject"),
                "from": email.get("from"),
                "account": email.get("account") or email.get("account_id"),
                "date": email.get("date"),
                "preview_len": len(preview),
                "preview": preview,
                "body_len": len(email.get("body") or ""),
                "html_len": len(email.get("html_body") or ""),
                "has_html": bool(email.get("has_html"))
            })
        return snapshots

    def _last_24_hours_range(self) -> Tuple[str, str, datetime, datetime, str]:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(hours=24)
        date_from = start_dt.strftime("%Y-%m-%d")
        date_to = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        label = f"{start_dt:%Y-%m-%d %H:%M} ~ {end_dt:%Y-%m-%d %H:%M}"
        return date_from, date_to, start_dt, end_dt, label

    def _fetch_yesterday_emails(self) -> Dict[str, Any]:
        from src.account_manager import AccountManager
        from src.services.email_service import EmailService

        date_from, date_to, start_dt, end_dt, date_label = self._last_24_hours_range()
        email_cfg = self.config.get("email", {})
        limit = int(email_cfg.get("limit", 500))
        if limit <= 0:
            limit = 1000

        account_manager = AccountManager()
        svc = EmailService(account_manager)
        result = svc.search_emails(
            query=None,
            search_in="all",
            date_from=date_from,
            date_to=date_to,
            folder=email_cfg.get("folder", "all"),
            unread_only=email_cfg.get("unread_only", False),
            has_attachments=None,
            limit=limit,
            account_id=email_cfg.get("account_id"),
        )

        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Failed to fetch emails"),
                "emails": [],
                "date_from": date_from,
                "date_to": date_to
            }

        emails = result.get("emails", [])
        pre_filter_count = len(emails)
        accounts_info = result.get("accounts_info") or []
        failed_accounts = result.get("failed_accounts") or result.get("failed_searches") or []
        accounts_searched = result.get("accounts_searched") or result.get("accounts_count")

        total_found = result.get("total_found")
        if total_found is None:
            if accounts_info:
                total_found = sum(info.get("total_found", 0) for info in accounts_info)
            else:
                total_found = result.get("total_emails")
        if total_found is None:
            total_found = len(emails)

        truncated = total_found > pre_filter_count if total_found is not None else False

        emails, filtered_out = self._filter_recent_emails(emails, start_dt, end_dt)
        if not truncated:
            if total_found is None:
                total_found = len(emails)
            else:
                total_found = max(0, total_found - filtered_out)

        use_account_totals = filtered_out == 0 and not truncated

        account_lookup = {
            acc.get("id"): acc.get("email")
            for acc in account_manager.list_accounts()
            if acc.get("id") and acc.get("email")
        }
        for email in emails:
            if not email.get("account") and email.get("account_id"):
                email["account"] = account_lookup.get(email["account_id"], email["account_id"])

        detail_limit = int(self.config.get("summary_ai", {}).get("max_emails", 40))
        if detail_limit > 0:
            folder_default = email_cfg.get("folder", "INBOX")
            if folder_default == "all":
                folder_default = "INBOX"
            self._hydrate_missing_emails(emails, svc, folder_default, detail_limit)

        return {
            "success": True,
            "emails": emails,
            "total_found": total_found,
            "truncated": truncated,
            "accounts_info": accounts_info,
            "failed_accounts": failed_accounts,
            "accounts_searched": accounts_searched,
            "filtered_out": filtered_out,
            "use_account_totals": use_account_totals,
            "date_from": date_from,
            "date_to": date_to,
            "date_label": date_label
        }

    def _hydrate_missing_emails(
        self,
        emails: List[Dict[str, Any]],
        email_service: Any,
        folder_default: str,
        limit: int
    ) -> None:
        updated = 0
        for email in emails:
            if updated >= limit:
                break
            subject = (email.get("subject") or "").strip()
            sender = (email.get("from") or "").strip()
            date_str = (email.get("date") or "").strip()
            preview = self._get_preview(email)
            needs_detail = not preview or not subject or not sender or not date_str
            if not needs_detail:
                continue
            email_id = email.get("id") or email.get("uid")
            account_id = email.get("account_id")
            if not email_id or not account_id:
                continue
            folder = email.get("folder") or folder_default
            if folder == "all":
                folder = "INBOX"
            detail = email_service.get_email_detail(
                email_id=str(email_id),
                folder=folder,
                account_id=account_id,
                message_id=email.get("message_id")
            )
            if not detail.get("success"):
                continue
            self._merge_email_detail(email, detail)
            updated += 1

    def _merge_email_detail(self, email: Dict[str, Any], detail: Dict[str, Any]) -> None:
        for key in ("subject", "from", "date", "account", "account_id", "folder", "message_id"):
            if not email.get(key) and detail.get(key):
                email[key] = detail.get(key)
        if detail.get("html_body") and not email.get("html_body"):
            email["html_body"] = detail.get("html_body")
        if detail.get("has_html") is not None and "has_html" not in email:
            email["has_html"] = detail.get("has_html")
        body = detail.get("body") or detail.get("html_body")
        if body and not email.get("body"):
            email["body"] = body

    def _resolve_categories(self) -> Dict[str, List[str]]:
        cfg = self.config.get("classification", {})
        categories = cfg.get("categories", {})
        return categories if isinstance(categories, dict) else {}

    def _classify_rule_based(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cfg = self.config.get("classification", {})
        categories = self._resolve_categories()
        important_categories = {c.lower() for c in cfg.get("important_categories", [])}
        important_keywords = [k.lower() for k in cfg.get("important_keywords", [])]

        results = []
        for email in emails:
            subject = email.get("subject", "")
            sender = email.get("from", "")
            preview = self._get_preview(email)
            text = f"{subject} {sender} {preview}".lower()

            category = "general"
            for name, keywords in categories.items():
                if any(keyword.lower() in text for keyword in keywords):
                    category = name
                    break

            is_important = category.lower() in important_categories or any(
                keyword in text for keyword in important_keywords
            )

            results.append({
                "email_id": email.get("id", ""),
                "category": category,
                "is_important": is_important
            })

        return results

    def _parse_json_response(self, content: str) -> Optional[List[Dict[str, Any]]]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("[")
            end = content.rfind("]")
            if start == -1 or end == -1 or end <= start:
                return None
            try:
                parsed = json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                return None
        return parsed if isinstance(parsed, list) else None

    def _classify_with_openai(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cfg = self.config.get("classification", {})
        ai_cfg = cfg.get("ai", {})
        api_key = ai_cfg.get("api_key") or os.getenv(ai_cfg.get("api_key_env", "OPENAI_API_KEY"))
        if not api_key:
            raise ValueError("OpenAI API key not found for classification")

        try:
            import openai
        except ImportError as exc:
            raise ImportError("OpenAI library not installed for classification") from exc

        categories = self._resolve_categories()
        category_names = list(categories.keys()) or ["general"]
        important_categories = cfg.get("important_categories", [])
        important_keywords = cfg.get("important_keywords", [])

        max_emails = int(ai_cfg.get("max_emails", 80))
        if max_emails <= 0:
            max_emails = len(emails)
        target_emails = emails[:max_emails]

        max_body_length = int(ai_cfg.get("max_body_length", 200))
        payload = []
        for email in target_emails:
            preview = self._get_preview(email, max_len=max_body_length)
            payload.append({
                "email_id": email.get("id", ""),
                "subject": email.get("subject", ""),
                "sender": email.get("from", ""),
                "date": email.get("date", ""),
                "preview": preview
            })

        prompt = (
            "You are an email triage assistant. "
            "Classify each email into one category from the list. "
            "Mark is_important when the category is in the important list or "
            "the email content suggests urgency.\n\n"
            f"Categories: {', '.join(category_names)}\n"
            f"Important categories: {', '.join(important_categories)}\n"
            f"Important keywords: {', '.join(important_keywords)}\n\n"
            "Return a JSON array only. Each item:\n"
            "{"
            "\"email_id\": \"...\", "
            "\"category\": \"one of categories or general\", "
            "\"is_important\": true/false"
            "}\n\n"
            f"Emails: {json.dumps(payload, ensure_ascii=False)}"
        )

        if self._debug_enabled("dump_ai_input"):
            debug_max = int(self._debug_config.get("max_preview_length", max_body_length))
            self._write_debug_event("classification_input", {
                "max_emails": max_emails,
                "max_body_length": max_body_length,
                "prompt": prompt,
                "emails": self._debug_snapshot(target_emails, debug_max)
            })

        client = openai.OpenAI(api_key=api_key, base_url=ai_cfg.get("base_url"))
        response = client.chat.completions.create(
            model=ai_cfg.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=600
        )

        content = response.choices[0].message.content.strip()
        if self._debug_enabled("dump_ai_output"):
            self._write_debug_event("classification_output", {
                "response": content
            })
        parsed = self._parse_json_response(content)
        if parsed is None:
            raise ValueError("AI classification response is not valid JSON")

        rule_based_map = {
            item["email_id"]: item for item in self._classify_rule_based(target_emails)
        }
        ai_map = {
            item.get("email_id"): item for item in parsed if isinstance(item, dict)
        }

        output: List[Dict[str, Any]] = []
        for email in target_emails:
            email_id = email.get("id", "")
            fallback = rule_based_map.get(
                email_id,
                {"email_id": email_id, "category": "general", "is_important": False}
            )
            item = ai_map.get(email_id)
            if not isinstance(item, dict):
                output.append(fallback)
                continue
            category = item.get("category") or fallback.get("category", "general")
            is_important = item.get("is_important")
            if not isinstance(is_important, bool):
                is_important = fallback.get("is_important", False)
            output.append({
                "email_id": email_id,
                "category": category,
                "is_important": is_important
            })

        if max_emails < len(emails):
            output.extend(self._classify_rule_based(emails[max_emails:]))

        return output

    def _classify_emails(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cfg = self.config.get("classification", {})
        if not cfg.get("enabled", True):
            return [
                {"email_id": email.get("id", ""), "category": "general", "is_important": False}
                for email in emails
            ]

        mode = cfg.get("mode", "ai")
        if mode == "ai":
            try:
                return self._classify_with_openai(emails)
            except Exception as exc:
                logger.warning("AI classification failed, fallback to rule-based: %s", exc)
                return self._classify_rule_based(emails)
        return self._classify_rule_based(emails)

    def _summarize_with_openai(
        self,
        emails: List[Dict[str, Any]],
        category_counts: Dict[str, int],
        date_label: str,
        total_found: int,
        displayed: int,
        missing_details: int
    ) -> Optional[str]:
        cfg = self.config.get("summary_ai", {})
        if not cfg.get("enabled", True):
            return None

        api_key = cfg.get("api_key") or os.getenv(cfg.get("api_key_env", "OPENAI_API_KEY"))
        if not api_key:
            logger.warning("OpenAI API key not found; skipping AI summary")
            return None

        try:
            import openai
        except ImportError:
            logger.warning("OpenAI library not installed; skipping AI summary")
            return None

        client = openai.OpenAI(
            api_key=api_key,
            base_url=cfg.get("base_url")
        )

        max_emails = int(cfg.get("max_emails", 40))
        if max_emails <= 0:
            max_emails = min(40, len(emails))
        sampled = emails[:max_emails]

        category_summary = ", ".join(f"{name}: {count}" for name, count in category_counts.items())
        email_lines = []
        for email in sampled:
            subject = email.get("subject", "")
            sender = email.get("from", "")
            date_str = email.get("date", "")
            account = email.get("account") or email.get("account_id") or ""
            preview = self._get_preview(email, max_len=120)
            if not (subject or sender or date_str or preview):
                continue
            email_lines.append(f"- {subject} | {sender} | {account} | {date_str} | {preview}")

        language = cfg.get("language", "en")
        response_lang = "Chinese" if language == "zh" else "English"

        prompt = (
            "Summarize yesterday's emails for a daily digest.\n\n"
            f"Date: {date_label}\n"
            f"Total emails: {total_found} (shown {displayed})\n"
            f"Missing details: {missing_details}\n"
            f"Categories: {category_summary}\n\n"
            "Emails:\n"
            + "\n".join(email_lines)
            + "\n\n"
            f"Respond in {response_lang} using Markdown. Provide 3-5 bullet points and a short action list if needed."
        )

        if self._debug_enabled("dump_ai_input"):
            debug_max = int(self._debug_config.get("max_preview_length", 200))
            self._write_debug_event("summary_input", {
                "max_emails": max_emails,
                "prompt": prompt,
                "emails": self._debug_snapshot(sampled, debug_max)
            })

        response = client.chat.completions.create(
            model=cfg.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "You are a concise email digest assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=400
        )
        content = response.choices[0].message.content.strip()
        if self._debug_enabled("dump_ai_output"):
            self._write_debug_event("summary_output", {
                "response": content
            })
        return content

    def _build_ai_telegram_message(
        self,
        emails: List[Dict[str, Any]],
        parse_mode: Optional[str],
        date_label: str,
        total_found: int,
        displayed: int,
        important_count: int,
        category_counts: Dict[str, int],
        highlights: List[Dict[str, Any]],
        account_stats: List[Dict[str, Any]],
        failed_accounts: List[Dict[str, Any]],
        truncated: bool,
        missing_details: int
    ) -> Optional[Tuple[str, Optional[str]]]:
        cfg = self.config.get("summary_ai", {})
        if not cfg.get("enabled", True):
            return None

        api_key = cfg.get("api_key") or os.getenv(cfg.get("api_key_env", "OPENAI_API_KEY"))
        if not api_key:
            logger.warning("OpenAI API key not found; skipping AI Telegram message")
            return None

        try:
            import openai
        except ImportError:
            logger.warning("OpenAI library not installed; skipping AI Telegram message")
            return None

        normalized = (parse_mode or "").strip()
        if not normalized:
            normalized = "HTML"
        if normalized.lower() == "html":
            format_label = "HTML"
            format_hint = (
                "输出 HTML，允许标签: <b>, <i>, <code>, <pre>, <a href=\"url\">。"
                "不要使用其他标签，不要用 Markdown，不要用代码块。"
            )
        elif normalized.lower() in {"markdownv2", "markdown"}:
            format_label = "MarkdownV2"
            format_hint = (
                "输出 MarkdownV2（注意转义特殊字符），不要使用 HTML 标签，不要用代码块。"
            )
            normalized = "MarkdownV2"
        else:
            format_label = "PlainText"
            format_hint = "输出纯文本，不要使用 HTML/Markdown。"
            normalized = None

        client = openai.OpenAI(
            api_key=api_key,
            base_url=cfg.get("base_url")
        )

        telegram_cfg = self.config.get("telegram", {})
        title = (telegram_cfg.get("title") or "邮件日报").strip()
        if title.lower() == "daily email digest":
            title = "邮件日报"

        max_emails = int(cfg.get("max_emails", 40))
        if max_emails <= 0:
            max_emails = min(40, len(emails))
        max_emails = min(max_emails, 25)
        sampled = emails[:max_emails]

        email_lines = []
        for email in sampled:
            subject = email.get("subject", "")
            sender = email.get("from", "")
            date_str = email.get("date", "")
            account = email.get("account") or email.get("account_id") or ""
            preview = self._get_preview(email, max_len=80)
            if not (subject or sender or date_str or preview):
                continue
            email_lines.append(
                f"- 主题: {subject} | 发件人: {sender} | 账号: {account} | 时间: {date_str} | 预览: {preview}"
            )

        highlight_lines = []
        for email in highlights:
            subject = email.get("subject", "")
            sender = email.get("from", "")
            date_str = email.get("date", "")
            account = email.get("account") or email.get("account_id") or ""
            preview = self._get_preview(email, max_len=100)
            if not (subject or sender or date_str or preview):
                continue
            highlight_lines.append(
                f"- 主题: {subject} | 发件人: {sender} | 账号: {account} | 时间: {date_str} | 预览: {preview}"
            )

        account_parts = []
        for item in account_stats:
            account = item.get("account", "unknown")
            total = item.get("total_found")
            displayed_count = item.get("displayed", 0)
            if total is not None and total != displayed_count:
                account_parts.append(f"{account} {displayed_count}/{total}")
            else:
                account_parts.append(f"{account} {displayed_count}")

        account_summary = "；".join(account_parts) if account_parts else "无"

        sorted_categories = sorted(category_counts.items(), key=lambda kv: kv[1], reverse=True)
        if sorted_categories:
            top_categories = sorted_categories[:6]
            rest_categories = sorted_categories[6:]
            category_parts = [f"{name} {count}" for name, count in top_categories]
            if rest_categories:
                rest_count = sum(count for _, count in rest_categories)
                if rest_count:
                    category_parts.append(f"其他 {rest_count}")
            category_summary = " / ".join(category_parts)
        else:
            category_summary = "无"
        failed_names = ", ".join(item.get("account", "unknown") for item in failed_accounts)

        if format_label == "HTML":
            title_line = f"<b>{title}</b>（{date_label}）"
            overview_header = "<b>概览</b>"
            highlight_header = "<b>重点</b>"
        elif format_label == "MarkdownV2":
            title_line = f"**{title}**（{date_label}）"
            overview_header = "**概览**"
            highlight_header = "**重点**"
        else:
            title_line = f"{title}（{date_label}）"
            overview_header = "概览"
            highlight_header = "重点"

        prompt = (
            "你是邮件日报写手，请基于以下数据生成一条 Telegram 日报消息。\n"
            f"格式要求: {format_label}. {format_hint}\n"
            "写作要求:\n"
            "- 风格像日报：短句、分行、结构固定。\n"
            "- 必须包含账号来源与分类汇总。\n"
            "- 重点最多 5 条，每条格式：序号 + 标题（分类）｜账号｜一句话摘要。\n"
            "- 若有行动清单才输出待办部分，否则不要输出。\n"
            "- 不要输出“详情索引/页码/按钮”等字样。\n"
            "- 不要杜撰未提供的信息。\n"
            "- 仅输出消息正文，不要额外解释。\n\n"
            "输出结构（按顺序）：\n"
            f"{title_line}\n"
            f"{overview_header}\n"
            f"- 总数: {total_found}（显示 {displayed}）\n"
            f"- 重要: {important_count}\n"
            f"- 账号: {account_summary}\n"
            f"- 分类: {category_summary}\n"
            + (f"- 失败账号: {failed_names}\n" if failed_names else "")
            + f"{highlight_header}\n\n"
            "重点邮件:\n"
            + ("\n".join(highlight_lines) if highlight_lines else "(无)")
            + "\n\n邮件样本:\n"
            + ("\n".join(email_lines) if email_lines else "(无)")
        )

        if self._debug_enabled("dump_ai_input"):
            debug_max = int(self._debug_config.get("max_preview_length", 200))
            self._write_debug_event("telegram_input", {
                "format": format_label,
                "prompt": prompt,
                "emails": self._debug_snapshot(sampled, debug_max)
            })

        response = client.chat.completions.create(
            model=cfg.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "你是一个严谨的日报生成器。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=600
        )
        content = response.choices[0].message.content.strip()
        if self._debug_enabled("dump_ai_output"):
            self._write_debug_event("telegram_output", {
                "response": content
            })
        if not content:
            return None
        return content, normalized

    def _build_fallback_summary(
        self,
        total_found: int,
        displayed: int,
        category_counts: Dict[str, int],
        missing_details: int
    ) -> str:
        category_summary = ", ".join(f"{name}: {count}" for name, count in category_counts.items())
        lines = [
            f"Total emails: {total_found} (shown {displayed})",
            f"Categories: {category_summary}"
        ]
        if missing_details:
            lines.append(f"Missing details: {missing_details}")
        return "\n".join(lines)

    def _aggregate_categories(self, classifications: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for item in classifications:
            category = item.get("category", "general") or "general"
            counts[category] = counts.get(category, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[0]))

    def _parse_email_timestamp(self, email: Dict[str, Any]) -> Optional[float]:
        timestamp = email.get("timestamp")
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            return float(timestamp)

        date_str = (email.get("date") or "").strip()
        if not date_str:
            return None

        try:
            parsed = email_utils.parsedate_to_datetime(date_str)
            if parsed:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.timestamp()
        except Exception:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                return parsed.timestamp()
            except Exception:
                continue

        return None

    def _filter_recent_emails(
        self,
        emails: List[Dict[str, Any]],
        start_dt: datetime,
        end_dt: datetime
    ) -> Tuple[List[Dict[str, Any]], int]:
        start_ts = start_dt.timestamp()
        end_ts = end_dt.timestamp()
        filtered: List[Dict[str, Any]] = []
        for email in emails:
            ts = self._parse_email_timestamp(email)
            if ts is None or start_ts <= ts <= end_ts:
                filtered.append(email)
        return filtered, len(emails) - len(filtered)

    def _select_highlights(
        self,
        emails: List[Dict[str, Any]],
        classifications: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        classification_map = {
            item.get("email_id"): item for item in classifications
        }

        important = []
        for email in emails:
            item = classification_map.get(email.get("id"))
            if item and item.get("is_important"):
                important.append(email)

        return important if important else emails

    def _strip_markdown(self, text: str) -> str:
        return text.replace("**", "").replace("`", "")

    def _split_summary_sections(self, summary_text: str) -> Tuple[List[str], List[str]]:
        if not summary_text:
            return [], []
        cleaned = self._strip_markdown(summary_text)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        action_idx = None
        for idx, line in enumerate(lines):
            if re.search(r"(行动清单|行动建议|Action\s*List|Actions?)", line, re.IGNORECASE):
                action_idx = idx
                break

        if action_idx is not None:
            summary_lines = lines[:action_idx]
            action_lines = lines[action_idx + 1:]
        else:
            summary_lines = lines
            action_lines = []

        def strip_bullet(text: str) -> str:
            text = re.sub(r"^[-*•]\s+", "", text)
            text = re.sub(r"^\d+[\.\、]\s+", "", text)
            return text.strip()

        summary = []
        for line in summary_lines:
            if re.search(r"(行动清单|行动建议|Action\s*List|Actions?)", line, re.IGNORECASE):
                continue
            line = strip_bullet(line)
            if line:
                summary.append(line)

        actions = []
        for line in action_lines:
            line = strip_bullet(line)
            if line:
                actions.append(line)

        return summary, actions

    def _escape_telegram_html(self, text: str) -> str:
        return html.escape(text or "")

    def _escape_markdown_v2(self, text: str) -> str:
        if not text:
            return ""
        escaped = text.replace("\\", "\\\\")
        return re.sub(r"([_\*\[\]\(\)~`>#+\-=|{}\.!])", r"\\\1", escaped)

    def _strip_html(self, text: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r"(?is)<(script|style).*?>.*?(</\\1>)", " ", text)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _decode_quoted_printable(self, text: str) -> str:
        if not text:
            return ""
        try:
            decoded = quopri.decodestring(text.encode("utf-8", errors="ignore"))
            return decoded.decode("utf-8", errors="ignore")
        except Exception:
            return text

    def _is_noise_line(self, line: str) -> bool:
        lowered = line.lower()
        if lowered.startswith("content-type:"):
            return True
        if lowered.startswith("content-transfer-encoding:"):
            return True
        if lowered.startswith("mime-version:"):
            return True
        if lowered.startswith("charset=") or lowered.startswith("boundary="):
            return True
        if line.startswith("--") and len(line) > 8:
            return True
        if line.startswith("------=_Part_") or line.startswith("----==_mimepart"):
            return True
        if line.startswith("--_----"):
            return True
        if re.match(r"^--[0-9a-f]{8,}", line, re.IGNORECASE):
            return True
        if re.match(r"^[-=]{5,}$", line):
            return True
        return False

    def _clean_preview(self, text: str) -> str:
        if not text:
            return ""
        if "quoted-printable" in text.lower() or "=3d" in text.lower() or "=\n" in text:
            text = self._decode_quoted_printable(text)

        text = text.replace("\r", "\n")
        text = self._strip_html(text)

        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if self._is_noise_line(stripped):
                continue
            lines.append(stripped)

        cleaned = " ".join(lines)
        return re.sub(r"\s+", " ", cleaned).strip()

    def extract_email_text(self, detail: Dict[str, Any]) -> str:
        text = detail.get("body") or detail.get("html_body") or ""
        if detail.get("html_body") and not detail.get("body"):
            text = detail.get("html_body") or text
        if detail.get("has_html") or detail.get("html_body"):
            text = self._strip_html(text)
        return self._clean_preview(text)

    def summarize_single_email(
        self,
        subject: str,
        sender: str,
        date_str: str,
        account: str,
        content: str,
        max_chars: int
    ) -> Optional[str]:
        cfg = self.config.get("summary_ai", {})
        if not cfg.get("enabled", True):
            return None

        api_key = cfg.get("api_key") or os.getenv(cfg.get("api_key_env", "OPENAI_API_KEY"))
        if not api_key:
            logger.warning("OpenAI API key not found; skipping single email summary")
            return None

        try:
            import openai
        except ImportError:
            logger.warning("OpenAI library not installed; skipping single email summary")
            return None

        client = openai.OpenAI(
            api_key=api_key,
            base_url=cfg.get("base_url")
        )
        trimmed = content[:max_chars] if max_chars > 0 else content
        prompt = (
            "请用中文总结下面这封邮件，输出纯文本（不要 Markdown/HTML）。\n"
            "格式要求：\n"
            "1) 一句话概述\n"
            "2) 2-4条要点（以短句分行）\n"
            "3) 若需要行动，请附上“行动建议：”后跟1-3条\n"
            "不要杜撰未提供的信息。\n\n"
            f"主题: {subject}\n"
            f"发件人: {sender}\n"
            f"账号: {account}\n"
            f"时间: {date_str}\n"
            "正文:\n"
            f"{trimmed}"
        )

        if self._debug_enabled("dump_ai_input"):
            self._write_debug_event("single_email_input", {
                "prompt": prompt,
                "content_len": len(trimmed)
            })

        response = client.chat.completions.create(
            model=cfg.get("model", "gpt-3.5-turbo"),
            messages=[
                {"role": "system", "content": "你是邮件摘要助手。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=300
        )
        content_out = response.choices[0].message.content.strip()
        if self._debug_enabled("dump_ai_output"):
            self._write_debug_event("single_email_output", {
                "response": content_out
            })
        return content_out or None

    def _truncate_text(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."

    def _build_account_stats(
        self,
        emails: List[Dict[str, Any]],
        accounts_info: List[Dict[str, Any]],
        use_totals: bool = True
    ) -> List[Dict[str, Any]]:
        displayed_counts: Dict[str, int] = {}
        for email in emails:
            account = email.get("account") or email.get("account_id") or "unknown"
            displayed_counts[account] = displayed_counts.get(account, 0) + 1

        total_counts: Dict[str, int] = {}
        if use_totals:
            for info in accounts_info:
                account = info.get("account") or info.get("account_id")
                if not account:
                    continue
                total_found = info.get("total_found")
                if total_found is None:
                    total_found = info.get("fetched")
                if total_found is not None:
                    total_counts[account] = total_found

        stats: List[Dict[str, Any]] = []
        for account in sorted(set(displayed_counts) | set(total_counts)):
            stats.append({
                "account": account,
                "displayed": displayed_counts.get(account, 0),
                "total_found": total_counts.get(account)
            })
        return stats

    def _is_empty_email(self, email: Dict[str, Any]) -> bool:
        subject = (email.get("subject") or "").strip()
        sender = (email.get("from") or "").strip()
        date_str = (email.get("date") or "").strip()
        preview = self._get_preview(email)
        return not (subject or sender or date_str or preview)

    def _get_preview(self, email: Dict[str, Any], max_len: Optional[int] = None) -> str:
        preview = (
            email.get("body_preview")
            or email.get("preview")
            or email.get("body")
            or ""
        )
        if email.get("html_body") and not email.get("body"):
            preview = email.get("html_body") or preview
        if email.get("has_html") or email.get("html_body"):
            preview = self._strip_html(preview)
        preview = self._clean_preview(preview)
        if max_len and len(preview) > max_len:
            return preview[: max_len - 3] + "..."
        return preview

    def _build_markdown(
        self,
        date_label: str,
        displayed: int,
        total_found: int,
        important_count: int,
        summary_text: str,
        category_counts: Dict[str, int],
        highlights: List[Dict[str, Any]],
        account_stats: List[Dict[str, Any]],
        failed_accounts: List[Dict[str, Any]],
        truncated: bool,
        missing_details: int
    ) -> str:
        title = self.config.get("lark", {}).get("title", "Daily Email Digest")
        lines = [
            f"**{title}**",
            f"Date: {date_label}",
            f"Total: {total_found} (shown {displayed}) | Important: {important_count}",
            ""
        ]

        if summary_text:
            lines.append(summary_text)
            lines.append("")

        if account_stats:
            lines.append("**Accounts**")
            for item in account_stats:
                account = item.get("account", "unknown")
                total = item.get("total_found")
                displayed_count = item.get("displayed", 0)
                if total is None:
                    lines.append(f"- {account}: {displayed_count}")
                else:
                    lines.append(f"- {account}: {displayed_count}/{total}")
            lines.append("")

        lines.append("**Categories**")
        if category_counts:
            for name, count in category_counts.items():
                lines.append(f"- {name}: {count}")
        else:
            lines.append("- general: 0")

        if highlights:
            lines.append("")
            lines.append("**Highlights**")
            for email in highlights:
                subject = email.get("subject", "")
                sender = email.get("from", "")
                date_str = email.get("date", "")
                account = email.get("account") or email.get("account_id") or "unknown"
                lines.append(f"- {subject} | {sender} | {account} | {date_str}")

        if truncated or failed_accounts or missing_details:
            lines.append("")
            lines.append("**Notes**")
            if truncated:
                lines.append("- Digest shows only a subset (limit applied).")
            if failed_accounts:
                failed_names = ", ".join(
                    item.get("account", "unknown") for item in failed_accounts
                )
                lines.append(f"- Failed accounts: {failed_names}")
            if missing_details:
                lines.append(f"- Missing details: {missing_details}")

        return "\n".join(lines).strip()

    def _build_telegram_text(
        self,
        date_label: str,
        displayed: int,
        total_found: int,
        important_count: int,
        summary_text: str,
        category_counts: Dict[str, int],
        highlights: List[Dict[str, Any]],
        account_stats: List[Dict[str, Any]],
        failed_accounts: List[Dict[str, Any]],
        truncated: bool,
        missing_details: int
    ) -> str:
        title = self.config.get("telegram", {}).get(
            "title",
            self.config.get("lark", {}).get("title", "Daily Email Digest")
        )
        summary_text = self._strip_markdown(summary_text) if summary_text else ""

        lines = [
            title,
            f"时间: {date_label}",
            f"总数: {total_found} (显示 {displayed}) | 重要: {important_count}"
        ]

        if summary_text:
            lines.append("")
            lines.append("摘要:")
            lines.append(summary_text)

        if account_stats:
            lines.append("")
            lines.append("账号:")
            for item in account_stats:
                account = item.get("account", "unknown")
                total = item.get("total_found")
                displayed_count = item.get("displayed", 0)
                if total is None:
                    lines.append(f"- {account}: {displayed_count}")
                else:
                    lines.append(f"- {account}: {displayed_count}/{total}")

        if highlights:
            lines.append("")
            lines.append("重点邮件:")
            for email in highlights:
                subject = email.get("subject") or "(无主题)"
                sender = email.get("from") or "unknown"
                date_str = email.get("date") or ""
                account = email.get("account") or email.get("account_id") or "unknown"
                meta_parts = [part for part in (sender, account, date_str) if part]
                lines.append(f"- {subject}")
                if meta_parts:
                    lines.append("  " + " | ".join(meta_parts))

        lines.append("")
        lines.append("分类:")
        if category_counts:
            for name, count in category_counts.items():
                lines.append(f"- {name}: {count}")
        else:
            lines.append("- general: 0")

        if truncated or failed_accounts or missing_details:
            lines.append("")
            lines.append("备注:")
            if truncated:
                lines.append("- 仅展示部分邮件（命中展示上限）。")
            if failed_accounts:
                failed_names = ", ".join(
                    item.get("account", "unknown") for item in failed_accounts
                )
                lines.append(f"- 失败账号: {failed_names}")
            if missing_details:
                lines.append(f"- 缺失详情: {missing_details}")

        return self._truncate_text("\n".join(lines).strip(), 4000)

    def _build_telegram_html(
        self,
        date_label: str,
        displayed: int,
        total_found: int,
        important_count: int,
        summary_text: str,
        category_counts: Dict[str, int],
        highlights: List[Dict[str, Any]],
        account_stats: List[Dict[str, Any]],
        failed_accounts: List[Dict[str, Any]],
        truncated: bool,
        missing_details: int
    ) -> str:
        title = self.config.get("telegram", {}).get(
            "title",
            self.config.get("lark", {}).get("title", "Daily Email Digest")
        )
        summary_points, action_points = self._split_summary_sections(summary_text)
        esc = self._escape_telegram_html

        lines = [
            f"<b>{esc(title)}</b>",
            f"时间: {esc(date_label)}",
            f"总数: {total_found} (显示 {displayed}) | 重要: {important_count}"
        ]

        if summary_points:
            lines.append("")
            lines.append("<b>今日要点</b>")
            for line in summary_points[:5]:
                lines.append(f"• {esc(line)}")

        if account_stats:
            lines.append("")
            lines.append("<b>账号概况</b>")
            for item in account_stats:
                account = esc(item.get("account", "unknown"))
                total = item.get("total_found")
                displayed_count = item.get("displayed", 0)
                if total is None:
                    lines.append(f"• {account}: {displayed_count}")
                else:
                    lines.append(f"• {account}: {displayed_count}/{total}")

        if highlights:
            lines.append("")
            lines.append("<b>重点邮件</b>")
            for email in highlights:
                subject = esc(email.get("subject") or "(无主题)")
                sender = email.get("from") or "unknown"
                account = email.get("account") or email.get("account_id") or "unknown"
                date_str = email.get("date") or ""
                meta_parts = [
                    esc(part) for part in (sender, account, date_str) if part
                ]
                lines.append(f"• {subject}")
                if meta_parts:
                    lines.append(f"  <i>{' | '.join(meta_parts)}</i>")

        if action_points:
            lines.append("")
            lines.append("<b>行动清单</b>")
            for line in action_points[:5]:
                lines.append(f"• {esc(line)}")

        lines.append("")
        lines.append("<b>分类分布</b>")
        if category_counts:
            for name, count in category_counts.items():
                lines.append(f"• {esc(name)}: {count}")
        else:
            lines.append("• general: 0")

        if truncated or failed_accounts or missing_details:
            lines.append("")
            lines.append("<b>备注</b>")
            if truncated:
                lines.append("• 仅展示部分邮件（命中展示上限）。")
            if failed_accounts:
                failed_names = ", ".join(
                    item.get("account", "unknown") for item in failed_accounts
                )
                lines.append(f"• 失败账号: {esc(failed_names)}")
            if missing_details:
                lines.append(f"• 缺失详情: {missing_details}")

        return self._truncate_text("\n".join(lines).strip(), 4000)

    def _build_telegram_markdown_v2(
        self,
        date_label: str,
        displayed: int,
        total_found: int,
        important_count: int,
        summary_text: str,
        category_counts: Dict[str, int],
        highlights: List[Dict[str, Any]],
        account_stats: List[Dict[str, Any]],
        failed_accounts: List[Dict[str, Any]],
        truncated: bool,
        missing_details: int
    ) -> str:
        text = self._build_telegram_text(
            date_label=date_label,
            displayed=displayed,
            total_found=total_found,
            important_count=important_count,
            summary_text=summary_text,
            category_counts=category_counts,
            highlights=highlights,
            account_stats=account_stats,
            failed_accounts=failed_accounts,
            truncated=truncated,
            missing_details=missing_details
        )
        return self._escape_markdown_v2(text)

    def _build_telegram_message(
        self,
        parse_mode: Optional[str],
        date_label: str,
        displayed: int,
        total_found: int,
        important_count: int,
        summary_text: str,
        category_counts: Dict[str, int],
        highlights: List[Dict[str, Any]],
        account_stats: List[Dict[str, Any]],
        failed_accounts: List[Dict[str, Any]],
        truncated: bool,
        missing_details: int,
        emails: List[Dict[str, Any]]
    ) -> Tuple[str, Optional[str]]:
        ai_message = self._build_ai_telegram_message(
            emails=emails,
            parse_mode=parse_mode,
            date_label=date_label,
            total_found=total_found,
            displayed=displayed,
            important_count=important_count,
            category_counts=category_counts,
            highlights=highlights,
            account_stats=account_stats,
            failed_accounts=failed_accounts,
            truncated=truncated,
            missing_details=missing_details
        )
        if ai_message is not None:
            return ai_message

        normalized = (parse_mode or "").strip()
        if not normalized:
            normalized = "HTML"
        if normalized.lower() == "html":
            return (
                self._build_telegram_html(
                    date_label=date_label,
                    displayed=displayed,
                    total_found=total_found,
                    important_count=important_count,
                    summary_text=summary_text,
                    category_counts=category_counts,
                    highlights=highlights,
                    account_stats=account_stats,
                    failed_accounts=failed_accounts,
                    truncated=truncated,
                    missing_details=missing_details
                ),
                "HTML"
            )
        if normalized.lower() in {"markdownv2", "markdown"}:
            return (
                self._build_telegram_markdown_v2(
                    date_label=date_label,
                    displayed=displayed,
                    total_found=total_found,
                    important_count=important_count,
                    summary_text=summary_text,
                    category_counts=category_counts,
                    highlights=highlights,
                    account_stats=account_stats,
                    failed_accounts=failed_accounts,
                    truncated=truncated,
                    missing_details=missing_details
                ),
                "MarkdownV2"
            )
        return (
            self._build_telegram_text(
                date_label=date_label,
                displayed=displayed,
                total_found=total_found,
                important_count=important_count,
                summary_text=summary_text,
                category_counts=category_counts,
                highlights=highlights,
                account_stats=account_stats,
                failed_accounts=failed_accounts,
                truncated=truncated,
                missing_details=missing_details
            ),
            None
        )

    def _build_telegram_interactive_items(
        self,
        emails: List[Dict[str, Any]],
        max_items: int
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for email in emails:
            email_id = email.get("id") or email.get("uid")
            account_id = email.get("account_id") or email.get("account")
            if not email_id or not account_id:
                continue
            items.append({
                "id": str(email_id),
                "account_id": account_id,
                "folder": email.get("folder") or "INBOX",
                "message_id": email.get("message_id"),
                "subject": email.get("subject") or "",
                "from": email.get("from") or "",
                "date": email.get("date") or ""
            })
            if len(items) >= max_items:
                break
        return items

    def _build_lark_elements(
        self,
        date_label: str,
        displayed: int,
        total_found: int,
        important_count: int,
        summary_text: str,
        category_counts: Dict[str, int],
        highlights: List[Dict[str, Any]],
        account_stats: List[Dict[str, Any]],
        failed_accounts: List[Dict[str, Any]],
        truncated: bool,
        missing_details: int
    ) -> List[Dict[str, Any]]:
        elements: List[Dict[str, Any]] = []

        elements.append({
            "tag": "div",
            "fields": [
                {
                    "is_short": True,
                    "text": {"tag": "lark_md", "content": f"**Date**\n{date_label}"}
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**Total**\n{total_found} (shown {displayed})"
                    }
                },
                {
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**Important**\n{important_count}"
                    }
                }
            ]
        })

        if account_stats:
            account_lines = []
            for item in account_stats:
                account = item.get("account", "unknown")
                total = item.get("total_found")
                displayed_count = item.get("displayed", 0)
                if total is None:
                    account_lines.append(f"- {account}: {displayed_count}")
                else:
                    account_lines.append(f"- {account}: {displayed_count}/{total}")
            elements.append({
                "tag": "markdown",
                "content": "**Accounts**\n" + "\n".join(account_lines)
            })

        if summary_text:
            elements.append({"tag": "markdown", "content": "**Summary**\n" + summary_text})

        if category_counts:
            category_lines = [f"- {name}: {count}" for name, count in category_counts.items()]
        else:
            category_lines = ["- general: 0"]
        elements.append({"tag": "markdown", "content": "**Categories**\n" + "\n".join(category_lines)})

        if highlights:
            highlight_lines = []
            for email in highlights:
                subject = email.get("subject", "")
                sender = email.get("from", "")
                date_str = email.get("date", "")
                account = email.get("account") or email.get("account_id") or "unknown"
                highlight_lines.append(f"- {subject} | {sender} | {account} | {date_str}")
            elements.append({"tag": "markdown", "content": "**Highlights**\n" + "\n".join(highlight_lines)})

        if truncated or failed_accounts or missing_details:
            notes = []
            if truncated:
                notes.append("- Digest shows only a subset (limit applied).")
            if failed_accounts:
                failed_names = ", ".join(
                    item.get("account", "unknown") for item in failed_accounts
                )
                notes.append(f"- Failed accounts: {failed_names}")
            if missing_details:
                notes.append(f"- Missing details: {missing_details}")
            elements.append({"tag": "markdown", "content": "**Notes**\n" + "\n".join(notes)})

        return elements

    def _build_lark_card_v2(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        title = self.config.get("lark", {}).get("title", "Daily Email Digest")
        return {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": title
                    }
                },
                "elements": elements
            }
        }

    def _send_lark_notification(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        lark_cfg = self.config.get("lark", {})
        webhook_url = lark_cfg.get("webhook_url")
        if not webhook_url:
            return {"success": False, "error": "Missing Lark webhook_url"}

        secret = lark_cfg.get("secret")
        if secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\n{secret}"
            sign = hashlib.sha256(string_to_sign.encode("utf-8")).hexdigest()
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            return {"success": True, "status_code": response.status_code, "response": response.text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _send_telegram_notification(
        self,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        telegram_cfg = self.config.get("telegram", {})
        bot_token = telegram_cfg.get("bot_token")
        chat_id = telegram_cfg.get("chat_id")
        if not bot_token or not chat_id:
            return {"success": False, "error": "Missing Telegram bot_token or chat_id"}

        api_base = telegram_cfg.get("api_base", "https://api.telegram.org").rstrip("/")
        payload = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            response = requests.post(
                f"{api_base}/bot{bot_token}/sendMessage",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return {"success": True, "status_code": response.status_code, "response": response.text}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def run(
        self,
        dry_run: bool = False,
        debug: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        self._debug_config = self._resolve_debug_config(debug)
        fetch_result = self._fetch_yesterday_emails()
        if not fetch_result.get("success"):
            return fetch_result

        emails = fetch_result.get("emails", [])
        date_label = fetch_result.get("date_label") or fetch_result.get("date_from")
        total_found = int(fetch_result.get("total_found", len(emails)))
        missing_details = sum(1 for email in emails if self._is_empty_email(email))
        emails = [email for email in emails if not self._is_empty_email(email)]
        displayed = len(emails)
        truncated = bool(fetch_result.get("truncated", total_found > displayed))
        accounts_info = fetch_result.get("accounts_info", [])
        failed_accounts = fetch_result.get("failed_accounts", [])
        use_account_totals = bool(fetch_result.get("use_account_totals", True))

        classifications = self._classify_emails(emails)
        category_counts = self._aggregate_categories(classifications)
        important_count = sum(1 for item in classifications if item.get("is_important"))

        summary_text = self._summarize_with_openai(
            emails,
            category_counts,
            date_label,
            total_found,
            displayed,
            missing_details
        )
        if summary_text is None:
            summary_text = self._build_fallback_summary(
                total_found,
                displayed,
                category_counts,
                missing_details
            )

        highlight_candidates = self._select_highlights(emails, classifications)
        account_stats = self._build_account_stats(emails, accounts_info, use_account_totals)

        lark_cfg = self.config.get("lark", {})
        lark_max = int(lark_cfg.get("max_highlights", 10))
        lark_highlights = highlight_candidates[:lark_max] if lark_max > 0 else []

        lark_elements = self._build_lark_elements(
            date_label=date_label,
            displayed=displayed,
            total_found=total_found,
            important_count=important_count,
            summary_text=summary_text,
            category_counts=category_counts,
            highlights=lark_highlights,
            account_stats=account_stats,
            failed_accounts=failed_accounts,
            truncated=truncated,
            missing_details=missing_details
        )
        payload = self._build_lark_card_v2(lark_elements)

        telegram_cfg = self.config.get("telegram", {})
        telegram_max = int(telegram_cfg.get("max_highlights", 10))
        telegram_highlights = highlight_candidates[:telegram_max] if telegram_max > 0 else []
        telegram_text, telegram_parse_mode = self._build_telegram_message(
            telegram_cfg.get("parse_mode"),
            date_label=date_label,
            displayed=displayed,
            total_found=total_found,
            important_count=important_count,
            summary_text=summary_text,
            category_counts=category_counts,
            highlights=telegram_highlights,
            account_stats=account_stats,
            failed_accounts=failed_accounts,
            truncated=truncated,
            missing_details=missing_details,
            emails=emails
        )
        telegram_reply_markup = None
        telegram_session_id = None
        session_store = self._get_session_store()
        if session_store:
            max_items_env = os.getenv("TELEGRAM_MAX_ITEMS")
            page_size_env = os.getenv("TELEGRAM_PAGE_SIZE")
            max_items = int(max_items_env) if max_items_env else DEFAULT_TELEGRAM_MAX_ITEMS
            page_size = int(page_size_env) if page_size_env else DEFAULT_TELEGRAM_PAGE_SIZE
            items = self._build_telegram_interactive_items(emails, max_items=max_items)
            if items:
                session_store.cleanup()
                telegram_session_id = secrets.token_urlsafe(8)
                base_text = telegram_text
                telegram_text = build_menu_text(
                    base_text=base_text,
                    items=items,
                    page=1,
                    page_size=page_size,
                    parse_mode=telegram_parse_mode
                )
                telegram_reply_markup = build_inline_keyboard(
                    session_id=telegram_session_id,
                    page=1,
                    total_items=len(items),
                    page_size=page_size
                )
                session_store.save_session(telegram_session_id, {
                    "created_at": datetime.now().isoformat(),
                    "base_text": base_text,
                    "parse_mode": telegram_parse_mode or "HTML",
                    "page_size": page_size,
                    "current_page": 1,
                    "items": items
                })

        lark_result = None
        telegram_result = None
        if not dry_run:
            if lark_cfg.get("enabled", True):
                lark_result = self._send_lark_notification(payload)
            if telegram_cfg.get("enabled", False):
                telegram_result = self._send_telegram_notification(
                    telegram_text,
                    telegram_parse_mode,
                    telegram_reply_markup
                )
                if telegram_session_id and telegram_result and telegram_result.get("success"):
                    try:
                        response_payload = json.loads(telegram_result.get("response", "{}"))
                    except json.JSONDecodeError:
                        response_payload = {}
                    message_info = response_payload.get("result", {})
                    session_store = self._get_session_store()
                    if session_store and message_info:
                        session_store.update_session(
                            telegram_session_id,
                            {
                                "chat_id": message_info.get("chat", {}).get("id"),
                                "message_id": message_info.get("message_id")
                            }
                        )

        return {
            "success": True,
            "date": date_label,
            "total_emails": len(emails),
            "displayed": displayed,
            "total_found": total_found,
            "important_emails": important_count,
            "categories": category_counts,
            "truncated": truncated,
            "summary": summary_text,
            "missing_details": missing_details,
            "dry_run": dry_run,
            "debug_log": str(self._resolve_debug_path())
            if self._debug_enabled("dump_ai_input") or self._debug_enabled("dump_ai_output")
            else None,
            "lark_payload": payload,
            "telegram_message": telegram_text,
            "telegram_session_id": telegram_session_id,
            "notification": lark_result,
            "notifications": {
                "lark": lark_result,
                "telegram": telegram_result
            }
        }
