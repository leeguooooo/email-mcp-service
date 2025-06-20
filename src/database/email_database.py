"""
Email database management for local caching
"""
import os
import sqlite3
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)

class EmailDatabase:
    """SQLite database for email caching and offline support"""
    
    def __init__(self, db_path: str = "~/.mcp-email/emails.db"):
        self.db_path = os.path.expanduser(db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        
        # Create directory if needed
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize database
        self.init_database()
    
    @property
    def conn(self) -> sqlite3.Connection:
        """Thread-local database connection"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        return self._local.conn
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
    
    def init_database(self):
        """Initialize database schema"""
        with self.transaction() as conn:
            # Accounts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    provider TEXT NOT NULL,
                    is_default BOOLEAN DEFAULT 0,
                    last_sync_time DATETIME,
                    sync_status TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Folders table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    folder_name TEXT NOT NULL,
                    display_name TEXT,
                    parent_folder TEXT,
                    level INTEGER DEFAULT 0,
                    message_count INTEGER DEFAULT 0,
                    unread_count INTEGER DEFAULT 0,
                    last_sync_uid INTEGER,
                    FOREIGN KEY (account_id) REFERENCES accounts(id),
                    UNIQUE(account_id, folder_name)
                )
            """)
            
            # Emails table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    folder_id INTEGER NOT NULL,
                    uid INTEGER NOT NULL,
                    message_id TEXT,
                    subject TEXT,
                    from_address TEXT,
                    from_name TEXT,
                    to_addresses TEXT,
                    cc_addresses TEXT,
                    date DATETIME,
                    size INTEGER,
                    is_read BOOLEAN DEFAULT 0,
                    is_flagged BOOLEAN DEFAULT 0,
                    is_deleted BOOLEAN DEFAULT 0,
                    has_attachments BOOLEAN DEFAULT 0,
                    preview TEXT,
                    labels TEXT,
                    sync_status TEXT DEFAULT 'meta',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (account_id) REFERENCES accounts(id),
                    FOREIGN KEY (folder_id) REFERENCES folders(id),
                    UNIQUE(account_id, folder_id, uid)
                )
            """)
            
            # Email contents table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS email_contents (
                    email_id INTEGER PRIMARY KEY,
                    body_text TEXT,
                    body_html TEXT,
                    headers TEXT,
                    raw_size INTEGER,
                    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
                )
            """)
            
            # Attachments table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    content_type TEXT,
                    size INTEGER,
                    content_id TEXT,
                    is_inline BOOLEAN DEFAULT 0,
                    file_path TEXT,
                    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
                )
            """)
            
            # Sync log table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id TEXT NOT NULL,
                    folder_id INTEGER,
                    sync_type TEXT,
                    start_time DATETIME,
                    end_time DATETIME,
                    emails_synced INTEGER DEFAULT 0,
                    emails_deleted INTEGER DEFAULT 0,
                    status TEXT,
                    error_message TEXT,
                    FOREIGN KEY (account_id) REFERENCES accounts(id),
                    FOREIGN KEY (folder_id) REFERENCES folders(id)
                )
            """)
            
            # Create indexes
            self._create_indexes(conn)
            
            # Create FTS5 table for search
            self._create_search_table(conn)
    
    def _create_indexes(self, conn: sqlite3.Connection):
        """Create database indexes for performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_emails_account_folder ON emails(account_id, folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_emails_from ON emails(from_address)",
            "CREATE INDEX IF NOT EXISTS idx_emails_unread ON emails(is_read, date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_emails_flagged ON emails(is_flagged)",
            "CREATE INDEX IF NOT EXISTS idx_folders_account ON folders(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_sync_log_account ON sync_log(account_id, start_time DESC)"
        ]
        
        for idx in indexes:
            conn.execute(idx)
    
    def _create_search_table(self, conn: sqlite3.Connection):
        """Create FTS5 virtual table for full-text search"""
        try:
            # Check if FTS5 is available
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS email_search USING fts5("
                        "email_id, subject, from_address, from_name, body_text)")
            
            # Create triggers to keep search index in sync
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS emails_ai AFTER INSERT ON emails 
                BEGIN
                    INSERT INTO email_search(email_id, subject, from_address, from_name)
                    VALUES (new.id, new.subject, new.from_address, new.from_name);
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS emails_au AFTER UPDATE ON emails 
                BEGIN
                    UPDATE email_search 
                    SET subject = new.subject, 
                        from_address = new.from_address,
                        from_name = new.from_name
                    WHERE email_id = new.id;
                END
            """)
            
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS emails_ad AFTER DELETE ON emails 
                BEGIN
                    DELETE FROM email_search WHERE email_id = old.id;
                END
            """)
            
            logger.info("FTS5 search table created successfully")
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS5 not available, search will be limited: {e}")
    
    # Account management
    def upsert_account(self, account_data: Dict[str, Any]) -> None:
        """Insert or update account information"""
        with self.transaction() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO accounts 
                (id, email, provider, is_default, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                account_data['id'],
                account_data['email'],
                account_data['provider'],
                account_data.get('is_default', False)
            ))
    
    def get_accounts(self) -> List[Dict[str, Any]]:
        """Get all accounts"""
        cursor = self.conn.execute("SELECT * FROM accounts ORDER BY is_default DESC, email")
        return [dict(row) for row in cursor.fetchall()]
    
    # Folder management
    def upsert_folder(self, account_id: str, folder_data: Dict[str, Any]) -> int:
        """Insert or update folder information, return folder_id"""
        with self.transaction() as conn:
            cursor = conn.execute("""
                INSERT OR REPLACE INTO folders 
                (account_id, folder_name, display_name, parent_folder, level, 
                 message_count, unread_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                account_id,
                folder_data['name'],
                folder_data.get('display_name', folder_data['name']),
                folder_data.get('parent'),
                folder_data.get('level', 0),
                folder_data.get('message_count', 0),
                folder_data.get('unread_count', 0)
            ))
            
            if cursor.lastrowid:
                return cursor.lastrowid
            else:
                # Get existing folder_id
                cursor = conn.execute(
                    "SELECT id FROM folders WHERE account_id = ? AND folder_name = ?",
                    (account_id, folder_data['name'])
                )
                return cursor.fetchone()[0]
    
    def get_folder_id(self, account_id: str, folder_name: str) -> Optional[int]:
        """Get folder ID by account and folder name"""
        cursor = self.conn.execute(
            "SELECT id FROM folders WHERE account_id = ? AND folder_name = ?",
            (account_id, folder_name)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    
    # Email management
    def upsert_email(self, email_data: Dict[str, Any], account_id: str, folder_id: int) -> int:
        """Insert or update email metadata, return email_id"""
        with self.transaction() as conn:
            # Parse email addresses
            to_addresses = json.dumps(email_data.get('to', []))
            cc_addresses = json.dumps(email_data.get('cc', []))
            
            # Extract preview from body
            preview = ""
            if email_data.get('body'):
                preview = email_data['body'][:200].replace('\n', ' ').strip()
            
            cursor = conn.execute("""
                INSERT OR REPLACE INTO emails 
                (account_id, folder_id, uid, message_id, subject, from_address, 
                 from_name, to_addresses, cc_addresses, date, size, is_read, 
                 is_flagged, has_attachments, preview, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                account_id,
                folder_id,
                email_data['uid'],
                email_data.get('message_id'),
                email_data.get('subject', ''),
                email_data.get('from', ''),
                email_data.get('from_name', ''),
                to_addresses,
                cc_addresses,
                email_data.get('date'),
                email_data.get('size', 0),
                not email_data.get('unread', True),
                email_data.get('flagged', False),
                bool(email_data.get('attachments')),
                preview
            ))
            
            email_id = cursor.lastrowid
            if not email_id:
                # Get existing email_id
                cursor = conn.execute(
                    "SELECT id FROM emails WHERE account_id = ? AND folder_id = ? AND uid = ?",
                    (account_id, folder_id, email_data['uid'])
                )
                email_id = cursor.fetchone()[0]
            
            # Store email content if provided
            if email_data.get('body'):
                conn.execute("""
                    INSERT OR REPLACE INTO email_contents 
                    (email_id, body_text, body_html, headers)
                    VALUES (?, ?, ?, ?)
                """, (
                    email_id,
                    email_data.get('body'),
                    email_data.get('body_html'),
                    json.dumps(email_data.get('headers', {}))
                ))
            
            # Store attachments if provided
            if email_data.get('attachments'):
                for att in email_data['attachments']:
                    conn.execute("""
                        INSERT INTO attachments 
                        (email_id, filename, content_type, size)
                        VALUES (?, ?, ?, ?)
                    """, (
                        email_id,
                        att.get('filename', 'unknown'),
                        att.get('content_type'),
                        att.get('size', 0)
                    ))
            
            return email_id
    
    def get_email_list(self, 
                      account_id: Optional[str] = None,
                      folder: Optional[str] = None,
                      unread_only: bool = False,
                      limit: int = 50,
                      offset: int = 0) -> List[Dict[str, Any]]:
        """Get email list from database"""
        query = """
            SELECT e.*, a.email as account_email, f.display_name as folder_name
            FROM emails e
            JOIN accounts a ON e.account_id = a.id
            JOIN folders f ON e.folder_id = f.id
            WHERE 1=1
        """
        params = []
        
        if account_id:
            query += " AND e.account_id = ?"
            params.append(account_id)
        
        if folder:
            query += " AND f.folder_name = ?"
            params.append(folder)
        
        if unread_only:
            query += " AND e.is_read = 0"
        
        query += " ORDER BY e.date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self.conn.execute(query, params)
        emails = []
        
        for row in cursor.fetchall():
            email = dict(row)
            # Parse JSON fields
            email['to'] = json.loads(email.get('to_addresses', '[]'))
            email['cc'] = json.loads(email.get('cc_addresses', '[]'))
            # Convert to expected format
            email['id'] = f"{email['account_id']}_{email['folder_id']}_{email['uid']}"
            email['from'] = email['from_address']
            email['unread'] = not email['is_read']
            email['account'] = email['account_email']
            emails.append(email)
        
        return emails
    
    def get_email_detail(self, email_id: int) -> Optional[Dict[str, Any]]:
        """Get full email details including content"""
        cursor = self.conn.execute("""
            SELECT e.*, ec.body_text, ec.body_html, 
                   a.email as account_email, f.display_name as folder_name
            FROM emails e
            JOIN accounts a ON e.account_id = a.id
            JOIN folders f ON e.folder_id = f.id
            LEFT JOIN email_contents ec ON e.id = ec.email_id
            WHERE e.id = ?
        """, (email_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        email = dict(row)
        
        # Get attachments
        cursor = self.conn.execute(
            "SELECT * FROM attachments WHERE email_id = ?", 
            (email_id,)
        )
        email['attachments'] = [dict(row) for row in cursor.fetchall()]
        
        # Parse JSON fields and format
        email['to'] = json.loads(email.get('to_addresses', '[]'))
        email['cc'] = json.loads(email.get('cc_addresses', '[]'))
        email['from'] = email['from_address']
        email['body'] = email.get('body_text', '')
        email['unread'] = not email['is_read']
        
        return email
    
    def search_emails(self, 
                     query: str,
                     account_id: Optional[str] = None,
                     limit: int = 50) -> List[Dict[str, Any]]:
        """Search emails using FTS5 or fallback to LIKE"""
        try:
            # Try FTS5 search first
            fts_query = f"""
                SELECT e.* FROM emails e
                JOIN email_search es ON e.id = es.email_id
                WHERE email_search MATCH ?
            """
            params = [query]
            
            if account_id:
                fts_query += " AND e.account_id = ?"
                params.append(account_id)
            
            fts_query += " ORDER BY e.date DESC LIMIT ?"
            params.append(limit)
            
            cursor = self.conn.execute(fts_query, params)
            
        except sqlite3.OperationalError:
            # Fallback to LIKE search
            like_query = f"""
                SELECT * FROM emails
                WHERE (subject LIKE ? OR from_address LIKE ? OR from_name LIKE ?)
            """
            search_term = f"%{query}%"
            params = [search_term, search_term, search_term]
            
            if account_id:
                like_query += " AND account_id = ?"
                params.append(account_id)
            
            like_query += " ORDER BY date DESC LIMIT ?"
            params.append(limit)
            
            cursor = self.conn.execute(like_query, params)
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_email_flags(self, email_id: int, is_read: Optional[bool] = None, 
                          is_flagged: Optional[bool] = None) -> None:
        """Update email flags"""
        updates = []
        params = []
        
        if is_read is not None:
            updates.append("is_read = ?")
            params.append(is_read)
        
        if is_flagged is not None:
            updates.append("is_flagged = ?")
            params.append(is_flagged)
        
        if updates:
            params.append(email_id)
            with self.transaction() as conn:
                conn.execute(
                    f"UPDATE emails SET {', '.join(updates)}, "
                    f"updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    params
                )
    
    def log_sync(self, account_id: str, folder_id: Optional[int] = None,
                sync_type: str = 'incremental', **kwargs) -> None:
        """Log synchronization activity"""
        with self.transaction() as conn:
            conn.execute("""
                INSERT INTO sync_log 
                (account_id, folder_id, sync_type, start_time, end_time,
                 emails_synced, emails_deleted, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_id,
                folder_id,
                sync_type,
                kwargs.get('start_time'),
                kwargs.get('end_time'),
                kwargs.get('emails_synced', 0),
                kwargs.get('emails_deleted', 0),
                kwargs.get('status', 'success'),
                kwargs.get('error_message')
            ))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        stats = {}
        
        # Total counts
        cursor = self.conn.execute("SELECT COUNT(*) FROM accounts")
        stats['total_accounts'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM emails")
        stats['total_emails'] = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM emails WHERE is_read = 0")
        stats['total_unread'] = cursor.fetchone()[0]
        
        # Database size
        cursor = self.conn.execute("SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()")
        stats['db_size_bytes'] = cursor.fetchone()[0]
        
        # Last sync times
        cursor = self.conn.execute("""
            SELECT a.email, MAX(s.end_time) as last_sync
            FROM accounts a
            LEFT JOIN sync_log s ON a.id = s.account_id
            WHERE s.status = 'success'
            GROUP BY a.id
        """)
        stats['last_sync_times'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        return stats
    
    def cleanup_old_data(self, days: int = 30) -> int:
        """Clean up old email data, return number of deleted emails"""
        cutoff_date = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
        
        with self.transaction() as conn:
            cursor = conn.execute("""
                DELETE FROM emails 
                WHERE date < ? AND is_flagged = 0 AND is_read = 1
            """, (cutoff_date,))
            
            return cursor.rowcount
    
    def close(self):
        """Close database connection"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            delattr(self._local, 'conn')