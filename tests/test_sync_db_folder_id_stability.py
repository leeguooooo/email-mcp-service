"""
Regression test: folders.id must remain stable across updates.

Using SQLite "INSERT OR REPLACE" would delete+insert rows and change the
autoincremented id, breaking foreign keys from emails.folder_id -> folders.id.
"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.email_sync_db import EmailSyncDatabase


class TestSyncDbFolderIdStability(unittest.TestCase):
    def test_add_or_update_folder_keeps_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "email_sync.db"
            db = EmailSyncDatabase(str(db_path))
            self.assertTrue(db.add_or_update_account("acc1", "a@test.com", "imap"))

            first_id = db.add_or_update_folder("acc1", "INBOX", "INBOX", message_count=1)
            second_id = db.add_or_update_folder("acc1", "INBOX", "INBOX", message_count=2)

            self.assertIsNotNone(first_id)
            self.assertEqual(first_id, second_id)

            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM folders WHERE account_id=? AND name=?", ("acc1", "INBOX"))
            self.assertEqual(cur.fetchone()[0], 1)
            conn.close()


if __name__ == "__main__":
    unittest.main()

