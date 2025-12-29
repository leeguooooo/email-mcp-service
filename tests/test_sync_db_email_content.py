"""
Regression test: email_content upsert and presence checks.

Mature clients cache bodies locally. We store extracted plain/html into
email_sync.db.email_content and rely on EmailSyncDatabase helpers.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import sys

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.email_sync_db import EmailSyncDatabase


class TestSyncDbEmailContent(unittest.TestCase):
    def test_upsert_and_has_email_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "email_sync.db"
            db = EmailSyncDatabase(str(db_path))
            self.assertTrue(db.add_or_update_account("acc1", "a@test.com", "imap"))
            folder_id = db.add_or_update_folder("acc1", "INBOX", "INBOX", message_count=1)
            self.assertIsNotNone(folder_id)

            email_db_id, _is_new = db.add_or_update_email(
                {
                    "account_id": "acc1",
                    "folder_id": folder_id,
                    "uid": "1",
                    "message_id": "<m1@test>",
                    "subject": "Hello",
                    "sender": "Alice",
                    "sender_email": "alice@test.com",
                    "recipients": [],
                    "date_sent": datetime.now(),
                    "is_read": False,
                    "is_flagged": False,
                    "has_attachments": False,
                    "size_bytes": 123,
                }
            )
            self.assertIsNotNone(email_db_id)
            self.assertFalse(db.has_email_content(email_db_id))

            ok = db.upsert_email_content(
                email_db_id,
                plain_text="hi",
                html_text=None,
                headers={"Subject": "Hello"},
                raw_size=456,
            )
            self.assertTrue(ok)
            self.assertTrue(db.has_email_content(email_db_id))

            # Updating should overwrite fields.
            ok = db.upsert_email_content(
                email_db_id,
                plain_text="hi2",
                html_text="<p>hi</p>",
                headers=None,
                raw_size=789,
            )
            self.assertTrue(ok)

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT plain_text, html_text, raw_size FROM email_content WHERE email_id=?",
                (email_db_id,),
            ).fetchone()
            conn.close()
            self.assertEqual(row[0], "hi2")
            self.assertEqual(row[1], "<p>hi</p>")
            self.assertEqual(row[2], 789)


if __name__ == "__main__":
    unittest.main()

