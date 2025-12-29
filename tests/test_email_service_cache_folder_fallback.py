"""
Regression test for cache folder filtering.

Cached emails may lack a resolved folder_id; filtering for INBOX should still
return those rows.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.email_service import EmailService


class _DummyAccountManager:
    def list_accounts(self):
        return []

    def get_account(self, account_id=None):
        return None


class TestEmailServiceCacheFolderFallback(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "email_sync.db"

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE emails (
                uid TEXT,
                message_id TEXT,
                subject TEXT,
                sender_email TEXT,
                date_sent TEXT,
                is_read INTEGER,
                has_attachments INTEGER,
                account_id TEXT,
                folder_id INTEGER,
                is_deleted INTEGER
            );
            CREATE TABLE accounts (id TEXT, email TEXT);
            CREATE TABLE folders (id INTEGER, name TEXT);
            """
        )

        cur.execute("INSERT INTO folders(id, name) VALUES(1, 'INBOX')")
        cur.execute("INSERT INTO accounts(id, email) VALUES('acc1', 'a@test.com')")
        # Email with NULL folder_id should be treated as INBOX by filter.
        cur.execute(
            """
            INSERT INTO emails(
                uid, message_id, subject, sender_email, date_sent, is_read, has_attachments,
                account_id, folder_id, is_deleted
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "1",
                "<m1@test>",
                "sub",
                "from@test.com",
                "2025-01-01 00:00:00",
                0,
                0,
                "acc1",
                None,
                0,
            ),
        )
        conn.commit()
        conn.close()

        self.service = EmailService(_DummyAccountManager())
        self.service._sync_db_path = self.db_path

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_inbox_filter_includes_null_folder_rows(self) -> None:
        result = self.service.list_emails(
            limit=10,
            unread_only=True,
            folder="INBOX",
            use_cache=True,
        )
        self.assertTrue(result.get("success"))
        self.assertEqual(len(result.get("emails", [])), 1)


if __name__ == "__main__":
    unittest.main()
