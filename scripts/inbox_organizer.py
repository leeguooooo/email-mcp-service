#!/usr/bin/env python3
"""
Inbox organization assistant.

分析最近邮件，基于规则给出垃圾邮件/营销邮件/低优先级通知的整理建议，
并对需要关注的邮件生成中文摘要。
"""
import argparse
import json
import logging
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure repository root on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.account_manager import AccountManager  # noqa: E402
from src.services.email_service import EmailService  # noqa: E402

from scripts.email_translator import EmailTranslator  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Rule-based filter result."""
    email_id: str
    is_important: bool
    priority_score: float
    reason: str
    category: str = "general"
    suggested_action: str = "none"


class InboxOrganizer:
    """High level helper that classifies and summarizes recent emails."""

    ACTION_DELETE_SPAM = "delete_spam"
    ACTION_DELETE_MARKETING = "delete_marketing"
    ACTION_MARK_AS_READ = "mark_as_read"
    ACTION_ATTENTION = "needs_attention"

    ACTION_TO_SUGGESTED = {
        ACTION_DELETE_SPAM: "delete",
        ACTION_DELETE_MARKETING: "delete",
        ACTION_MARK_AS_READ: "mark_read",
        ACTION_ATTENTION: "review",
    }

    SPAM_CATEGORIES = {"spam", "junk"}
    MARKETING_CATEGORIES = {"marketing", "promotion", "ads", "advertisement"}
    NEWSLETTER_CATEGORIES = {"newsletter", "newsletters", "digest"}
    SYSTEM_CATEGORIES = {"system", "notification", "alert"}
    IMPORTANT_CATEGORIES = {"urgent", "work", "finance"}
    IMPORTANT_KEYWORDS = ["urgent", "important", "asap", "deadline", "紧急", "重要", "截止"]
    CATEGORY_KEYWORDS = {
        "spam": ["lottery", "winner", "bitcoin", "crypto", "中奖", "恭喜", "免费", "借款"],
        "marketing": ["sale", "discount", "promo", "offer", "促销", "优惠", "活动", "推广"],
        "newsletter": ["newsletter", "digest", "update", "周报", "月报", "周刊"],
        "system": ["alert", "notification", "security", "login", "系统", "登录", "安全"],
        "urgent": ["urgent", "asap", "immediately", "紧急", "立即", "尽快"],
        "finance": ["invoice", "payment", "bank", "receipt", "发票", "付款", "银行", "账单"],
        "work": ["meeting", "project", "deadline", "review", "report", "会议", "项目", "报告"],
        "personal": ["family", "friend", "birthday", "家人", "朋友", "生日"]
    }
    CATEGORY_PRIORITY = [
        "spam",
        "marketing",
        "newsletter",
        "system",
        "urgent",
        "finance",
        "work",
        "personal"
    ]
    CATEGORY_SCORE = {
        "spam": 0.1,
        "marketing": 0.2,
        "newsletter": 0.3,
        "system": 0.4,
        "urgent": 0.9,
        "finance": 0.8,
        "work": 0.7,
        "personal": 0.6,
        "general": 0.5
    }

    def __init__(
        self,
        limit: int = 15,
        folder: str = "INBOX",
        unread_only: bool = False,
        account_id: Optional[str] = None,
    ):
        self.limit = limit
        self.folder = folder
        self.unread_only = unread_only
        self.account_id = account_id

        self.account_manager = AccountManager()
        self.email_service = EmailService(self.account_manager)
        self.priority_threshold = 0.7

    # Public API ---------------------------------------------------------

    def organize(self) -> Dict[str, Any]:
        """Fetch, classify, and summarize recent emails."""
        fetch_result = self._fetch_recent_emails()
        if not fetch_result.get("success"):
            return fetch_result

        enriched_emails = fetch_result["emails"]
        if not enriched_emails:
            return {
                "success": True,
                "processed": 0,
                "actions": self._empty_actions(),
                "important_summaries": [],
                "summary_text": "📭 暂无邮件需要处理",
                "stats": {
                    "total_emails": 0,
                    "delete_spam": 0,
                    "delete_marketing": 0,
                    "mark_as_read": 0,
                    "needs_attention": 0,
                },
                "generated_at": datetime.utcnow().isoformat() + "Z",
            }

        filter_results = self._classify_emails(enriched_emails)
        actions, important_details = self._categorize_actions(
            enriched_emails, filter_results
        )

        important_summaries, translator_note = self._summarize_important(
            important_details
        )

        summary_text = self._compose_summary(
            len(enriched_emails), actions, important_summaries, translator_note
        )

        stats = {
            "total_emails": len(enriched_emails),
            "delete_spam": len(actions[self.ACTION_DELETE_SPAM]),
            "delete_marketing": len(actions[self.ACTION_DELETE_MARKETING]),
            "mark_as_read": len(actions[self.ACTION_MARK_AS_READ]),
            "needs_attention": len(actions[self.ACTION_ATTENTION]),
        }

        # Remove internal-only fields before returning
        for bucket in important_details:
            bucket["email"].pop("full_body", None)
        for email in enriched_emails:
            email.pop("full_body", None)

        return {
            "success": True,
            "processed": len(enriched_emails),
            "actions": actions,
            "important_summaries": important_summaries,
            "summary_text": summary_text,
            "stats": stats,
            "duplicates": self._find_duplicates(enriched_emails),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    # Internal helpers ---------------------------------------------------

    def _fetch_recent_emails(self) -> Dict[str, Any]:
        """Fetch latest emails and enrich with body preview."""
        try:
            result = self.email_service.list_emails(
                limit=self.limit,
                unread_only=self.unread_only,
                folder=self.folder,
                account_id=self.account_id,
            )
        except Exception as exc:
            logger.error("Failed to list emails: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

        if result.get("error"):
            return {"success": False, "error": result["error"]}

        emails = result.get("emails", [])
        enriched: List[Dict[str, Any]] = []

        for email in emails:
            detail = self._safe_get_detail(email)

            body_text = ""
            if detail and "error" not in detail:
                body_text = detail.get("body") or detail.get("html_body") or ""
            preview = self._sanitize_preview(body_text)

            enriched_email = {
                **email,
                "folder": email.get("folder", detail.get("folder", self.folder) if detail else self.folder),
                "account_id": email.get(
                    "account_id",
                    detail.get("account_id") if detail else email.get("account"),
                ),
                "has_attachments": bool(
                    detail and detail.get("attachments")
                ),
                "body_preview": preview,
                "full_body": body_text,
            }
            enriched.append(enriched_email)

        return {"success": True, "emails": enriched}

    def _safe_get_detail(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve email detail with graceful error handling."""
        account_ref = email.get("account_id") or email.get("account")
        try:
            return self.email_service.get_email_detail(
                email_id=email["id"],
                folder=email.get("folder", self.folder),
                account_id=account_ref,
            )
        except Exception as exc:
            logger.warning(
                "Failed to fetch detail for email %s: %s",
                email.get("id"),
                exc,
            )
            return {"error": str(exc)}

    def _classify_emails(
        self, emails: List[Dict[str, Any]]
    ) -> Dict[str, FilterResult]:
        """Run rule-based classification and return mapping of email_id -> FilterResult."""
        result_map: Dict[str, FilterResult] = {}

        for email in emails:
            email_id = email.get("id", "")
            subject = email.get("subject", "")
            sender = email.get("from", "")
            preview = email.get("body_preview", "")
            text = f"{subject} {sender} {preview}".lower()

            category = "general"
            matched_keyword = None
            for name in self.CATEGORY_PRIORITY:
                keywords = self.CATEGORY_KEYWORDS.get(name, [])
                for keyword in keywords:
                    if keyword.lower() in text:
                        category = name
                        matched_keyword = keyword
                        break
                if matched_keyword:
                    break

            is_important = category in self.IMPORTANT_CATEGORIES or any(
                keyword.lower() in text for keyword in self.IMPORTANT_KEYWORDS
            )
            score = self.CATEGORY_SCORE.get(category, 0.5)
            if is_important:
                score = max(score, 0.8)

            reason_parts = [f"规则匹配: {category}"]
            if matched_keyword:
                reason_parts.append(f"关键词:{matched_keyword}")
            reason = "；".join(reason_parts)

            result_map[email_id] = FilterResult(
                email_id=email_id,
                is_important=is_important,
                priority_score=score,
                reason=reason,
                category=category,
                suggested_action="none",
            )

        return result_map

    def _categorize_actions(
        self,
        emails: List[Dict[str, Any]],
        filter_results: Dict[str, FilterResult],
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
        """Determine suggested action for each email."""
        actions = self._empty_actions()
        important_details: List[Dict[str, Any]] = []

        for email in emails:
            filter_result = filter_results.get(email["id"])
            if not filter_result:
                filter_result = FilterResult(
                    email_id=email["id"],
                    is_important=False,
                    priority_score=0.5,
                    reason="无过滤结果，视为一般邮件",
                    category="general",
                    suggested_action="mark_read",
                )

            action_key, custom_reason = self._determine_action(
                email, filter_result
            )
            reason = filter_result.reason or custom_reason
            if custom_reason and custom_reason not in reason:
                reason = f"{filter_result.reason}；{custom_reason}".strip("；")

            action_item = {
                "id": email.get("id"),
                "subject": email.get("subject", ""),
                "from": email.get("from", ""),
                "date": email.get("date", ""),
                "folder": email.get("folder", self.folder),
                "priority_score": round(
                    float(filter_result.priority_score or 0.0), 3
                ),
                "category": (filter_result.category or "general").lower(),
                "reason": reason,
                "suggested_action": filter_result.suggested_action
                or self.ACTION_TO_SUGGESTED.get(action_key, "none"),
                "account_id": email.get("account_id"),
            }
            actions[action_key].append(action_item)

            if action_key == self.ACTION_ATTENTION:
                important_details.append(
                    {"email": email.copy(), "classification": filter_result}
                )

        # Sort buckets for readability
        actions[self.ACTION_DELETE_SPAM].sort(
            key=lambda item: item["priority_score"]
        )
        actions[self.ACTION_DELETE_MARKETING].sort(
            key=lambda item: item["priority_score"]
        )
        actions[self.ACTION_MARK_AS_READ].sort(
            key=lambda item: item["priority_score"]
        )
        actions[self.ACTION_ATTENTION].sort(
            key=lambda item: item["priority_score"], reverse=True
        )

        return actions, important_details

    def _determine_action(
        self, email: Dict[str, Any], filter_result: FilterResult
    ) -> Tuple[str, Optional[str]]:
        """Heuristic mapping from classification to suggested action."""
        category = (filter_result.category or "general").lower()
        score = float(filter_result.priority_score or 0.0)
        subject_lower = (email.get("subject") or "").lower()

        if category in self.SPAM_CATEGORIES or score <= 0.2:
            return self.ACTION_DELETE_SPAM, "识别为垃圾邮件"

        if category in self.MARKETING_CATEGORIES or "unsubscribe" in subject_lower:
            return self.ACTION_DELETE_MARKETING, "识别为营销邮件"

        if category in self.NEWSLETTER_CATEGORIES:
            return self.ACTION_MARK_AS_READ, "例行订阅更新"

        if category in self.SYSTEM_CATEGORIES and score < 0.6:
            return self.ACTION_MARK_AS_READ, "系统/安全通知"

        if not filter_result.is_important and score < self.priority_threshold:
            return self.ACTION_MARK_AS_READ, "规则判断重要性较低"

        return self.ACTION_ATTENTION, None

    def _summarize_important(
        self, important_details: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Generate Chinese summaries for important emails."""
        if not important_details:
            return [], None

        translator = EmailTranslator()
        payload = []
        for item in important_details:
            email = item["email"]
            payload.append(
                {
                    "id": email.get("id"),
                    "from": email.get("from", ""),
                    "subject": email.get("subject", ""),
                    "body": email.get("full_body") or email.get("body_preview", ""),
                }
            )

        translation_note = None
        summary_map: Dict[str, Dict[str, Any]] = {}
        try:
            translation_result = translator.translate_and_summarize(payload)
            if translation_result.get("success"):
                summary_map = {
                    entry.get("id"): entry
                    for entry in translation_result.get("emails", [])
                }
            else:
                translation_note = translation_result.get(
                    "summary", translation_result.get("error")
                )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Summaries failed: %s", exc, exc_info=True)
            translation_note = str(exc)

        summaries: List[Dict[str, Any]] = []
        for item in important_details:
            email = item["email"]
            classification = item["classification"]
            translated = summary_map.get(email.get("id"), {})

            subject_display = translated.get("subject_zh") or email.get("subject", "")
            summary_text = translated.get("summary_zh") or email.get(
                "body_preview", ""
            )

            summaries.append(
                {
                    "id": email.get("id"),
                    "subject": subject_display.strip(),
                    "from": email.get("from", ""),
                    "summary": summary_text.strip(),
                    "priority_score": round(
                        float(classification.priority_score or 0.0), 3
                    ),
                    "category": (classification.category or "general").lower(),
                    "reason": classification.reason,
                    "folder": email.get("folder", self.folder),
                    "account_id": email.get("account_id"),
                }
            )

        summaries.sort(key=lambda item: item["priority_score"], reverse=True)
        return summaries, translation_note

    def _compose_summary(
        self,
        total_emails: int,
        actions: Dict[str, List[Dict[str, Any]]],
        important_summaries: List[Dict[str, Any]],
        translation_note: Optional[str],
    ) -> str:
        """Build human-readable Chinese summary."""
        def join_subjects(items: List[Dict[str, Any]], limit: int = 3) -> str:
            subjects = [itm["subject"] or "(无主题)" for itm in items[:limit]]
            return "，".join(subjects)

        lines: List[str] = []
        lines.append(
            f"已分析「{self.folder}」中最近 {total_emails} 封邮件，整理建议如下："
        )

        spam_items = actions[self.ACTION_DELETE_SPAM]
        if spam_items:
            lines.append(
                f"1、删除垃圾邮件 {len(spam_items)} 封，例如：{join_subjects(spam_items)}"
            )
        else:
            lines.append("1、未发现明显垃圾邮件。")

        marketing_items = actions[self.ACTION_DELETE_MARKETING]
        if marketing_items:
            lines.append(
                f"2、删除营销/过期推广邮件 {len(marketing_items)} 封，例如：{join_subjects(marketing_items)}"
            )
        else:
            lines.append("2、暂无需要清理的营销邮件。")

        mark_read_items = actions[self.ACTION_MARK_AS_READ]
        if mark_read_items:
            lines.append(
                f"3、建议直接标记为已读的日常通知 {len(mark_read_items)} 封，例如：{join_subjects(mark_read_items)}"
            )
        else:
            lines.append("3、未发现需要直接标为已读的通知邮件。")

        if important_summaries:
            lines.append("4、以下邮件需要优先关注：")
            for idx, summary in enumerate(important_summaries, 1):
                lines.append(
                    f"   {idx}. {summary['subject']}（{summary['from']}）"
                )
                if summary["summary"]:
                    lines.append(f"      摘要：{summary['summary']}")
        else:
            lines.append("4、暂无需要特别关注的邮件。")

        if translation_note:
            lines.append(f"⚠️ 摘要生成提示：{translation_note}")

        return "\n".join(lines)

    def _find_duplicates(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Identify duplicate subjects for context."""
        subjects = [email.get("subject", "").strip() for email in emails if email.get("subject")]
        counts = Counter(subjects)
        duplicates = {subject: count for subject, count in counts.items() if count > 1}
        return duplicates

    def _sanitize_preview(self, text: str) -> str:
        """Condense whitespace and limit preview length."""
        if not text:
            return ""
        cleaned = " ".join(text.strip().split())
        return cleaned[:400]

    def _empty_actions(self) -> Dict[str, List[Dict[str, Any]]]:
        """Utility to create empty action buckets."""
        return {
            self.ACTION_DELETE_SPAM: [],
            self.ACTION_DELETE_MARKETING: [],
            self.ACTION_MARK_AS_READ: [],
            self.ACTION_ATTENTION: [],
        }


def main():
    parser = argparse.ArgumentParser(description="整理最近邮件并给出操作建议")
    parser.add_argument("--limit", type=int, default=15, help="分析的邮件数量")
    parser.add_argument("--folder", default="INBOX", help="要分析的邮箱文件夹")
    parser.add_argument(
        "--unread-only", action="store_true", help="仅分析未读邮件"
    )
    parser.add_argument("--account-id", help="指定账号 ID 或邮箱地址")
    parser.add_argument(
        "--text", action="store_true", help="以纯文本形式输出摘要"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="输出调试日志"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    organizer = InboxOrganizer(
        limit=args.limit,
        folder=args.folder,
        unread_only=args.unread_only,
        account_id=args.account_id,
    )
    result = organizer.organize()

    if args.text:
        print(result.get("summary_text", ""))
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
