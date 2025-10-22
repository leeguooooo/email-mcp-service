"""Unit tests for the standalone mailbox client."""
from __future__ import annotations

import io
import json
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from clients.mailbox_client.client import MailboxClient
import clients.mailbox_client.cli as mailbox_cli


class TestMailboxClient(unittest.TestCase):
    """Tests for the data access wrapper."""

    def setUp(self) -> None:
        self.mock_account_manager = MagicMock()
        self.mock_email_service = MagicMock()

    def test_list_emails_normalizes_success(self) -> None:
        """Email listing should include a success flag even if missing."""
        self.mock_email_service.list_emails.return_value = {
            "emails": [],
            "accounts_info": [],
        }

        client = MailboxClient(
            account_manager=self.mock_account_manager,
            email_service=self.mock_email_service,
        )
        result = client.list_emails(limit=5, unread_only=True)

        self.assertTrue(result.get("success"))
        self.assertEqual(result.get("limit"), 5)
        self.assertTrue(result.get("unread_only"))
        self.mock_email_service.list_emails.assert_called_once()

    def test_get_email_detail_requires_id(self) -> None:
        """Missing email ID should return an error structure."""
        client = MailboxClient(
            account_manager=self.mock_account_manager,
            email_service=self.mock_email_service,
        )
        result = client.get_email_detail("")
        self.assertFalse(result.get("success"))
        self.assertIn("email_id", result.get("error"))

    def test_list_accounts_handles_exception(self) -> None:
        """Account manager errors should be surfaced gracefully."""
        self.mock_account_manager.list_accounts.side_effect = RuntimeError("boom")

        client = MailboxClient(
            account_manager=self.mock_account_manager,
            email_service=self.mock_email_service,
        )
        result = client.list_accounts()
        self.assertFalse(result.get("success"))
        self.assertEqual(result.get("error"), "boom")


class TestMailboxClientCLI(unittest.TestCase):
    """Tests for the CLI presentation logic."""

    def test_cli_list_accounts_text_output(self) -> None:
        """Text output should contain a summary and table headers."""
        with patch.object(mailbox_cli, "MailboxClient") as mock_client_cls:
            instance = mock_client_cls.return_value
            instance.list_accounts.return_value = {
                "success": True,
                "accounts": [
                    {
                        "id": "acc1",
                        "email": "user@example.com",
                        "provider": "imap",
                        "description": "主账户",
                        "is_default": True,
                    },
                    {
                        "id": "acc2",
                        "email": "someone@else.com",
                        "provider": "imap",
                        "description": "次账户",
                        "is_default": False,
                    },
                ],
            }

            stdout_buffer = io.StringIO()
            with patch("sys.stdout", stdout_buffer):
                exit_code = mailbox_cli.main(["list-accounts"])

        output = stdout_buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("📬 共 2 个账户", output)
        self.assertIn("邮箱地址", output)
        self.assertIn("user@example.com", output)

    def test_cli_list_emails_json_output(self) -> None:
        """JSON flag should produce valid JSON payload."""
        with patch.object(mailbox_cli, "MailboxClient") as mock_client_cls:
            instance = mock_client_cls.return_value
            instance.list_emails.return_value = {
                "success": True,
                "emails": [],
                "accounts_info": [],
            }

            stdout_buffer = io.StringIO()
            with patch("sys.stdout", stdout_buffer):
                exit_code = mailbox_cli.main(["list-emails", "--json"])

        payload = stdout_buffer.getvalue()
        self.assertEqual(exit_code, 0)
        data: Dict[str, Any] = json.loads(payload)
        self.assertTrue(data.get("success"))
        self.assertIn("emails", data)

    def test_cli_show_email_error(self) -> None:
        """Errors should be reported to stderr with non-zero exit code."""
        with patch.object(mailbox_cli, "MailboxClient") as mock_client_cls:
            instance = mock_client_cls.return_value
            instance.get_email_detail.return_value = {
                "success": False,
                "error": "not found",
            }

            stderr_buffer = io.StringIO()
            with patch("sys.stderr", stderr_buffer):
                exit_code = mailbox_cli.main(["show-email", "123", "--account-id", "acc1"])

        self.assertEqual(exit_code, 1)
        self.assertIn("操作失败", stderr_buffer.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
