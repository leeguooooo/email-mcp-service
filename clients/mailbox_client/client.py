"""High-level client for browsing emails across MCP-managed mailboxes."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure repository root is importable when this module is executed as a script
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class MailboxClient:
    """Convenience client that wraps the MCP email services for browsing."""

    def __init__(
        self,
        account_manager: Optional[Any] = None,
        email_service: Optional[Any] = None,
    ) -> None:
        """Initialise the client and underlying services."""
        if account_manager is None:
            from src.account_manager import AccountManager

            account_manager = AccountManager()

        if email_service is None:
            from src.services.email_service import EmailService

            email_service = EmailService(account_manager)

        self.account_manager = account_manager
        self.email_service = email_service

    def list_accounts(self) -> Dict[str, Any]:
        """Return configured mailbox accounts."""
        try:
            accounts = self.account_manager.list_accounts()
            return {
                "success": True,
                "accounts": accounts,
                "total": len(accounts),
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
            }

    def list_emails(
        self,
        *,
        limit: int = 50,
        unread_only: bool = False,
        folder: str = "INBOX",
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List emails for the given mailbox scope."""
        try:
            result = self.email_service.list_emails(
                limit=limit,
                unread_only=unread_only,
                folder=folder,
                account_id=account_id,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
            }

        normalized = self._ensure_success(result)
        normalized.setdefault("limit", limit)
        normalized.setdefault("unread_only", unread_only)
        normalized.setdefault("folder", folder)
        if account_id:
            normalized.setdefault("account_id", account_id)
        return normalized

    def get_email_detail(
        self,
        email_id: str,
        *,
        folder: str = "INBOX",
        account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch the detailed body and headers for a specific email."""
        if not email_id:
            return {
                "success": False,
                "error": "email_id is required",
            }

        try:
            result = self.email_service.get_email_detail(
                email_id=email_id,
                folder=folder,
                account_id=account_id,
            )
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
            }

        normalized = self._ensure_success(result)
        normalized.setdefault("email_id", email_id)
        if account_id:
            normalized.setdefault("account_id", account_id)
        return normalized

    @staticmethod
    def _ensure_success(result: Any) -> Dict[str, Any]:
        """Ensure responses contain a success flag."""
        if not isinstance(result, dict):
            return {
                "success": False,
                "error": "Unexpected result format",
            }

        if "success" in result:
            return result

        normalized = dict(result)
        normalized["success"] = "error" not in normalized
        return normalized
