"""
SQLite数据库同步模块 - 多邮箱邮件同步
"""
import sqlite3
import logging
import hashlib
import threading
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import json
import email
from email.header import decode_header
import email.utils

from ..config.paths import EMAIL_SYNC_DB

logger = logging.getLogger(__name__)

class EmailSyncDatabase:
    """邮件同步数据库管理器"""
    
    def __init__(self, db_path: str = None):
        """初始化数据库连接"""
        if db_path is None:
            db_path = EMAIL_SYNC_DB
        self.db_path = Path(db_path)
        self.conn = None
        self._lock = threading.RLock()  # 添加线程锁
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库和表结构"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # 返回字典格式结果
        
        # 创建表结构
        self._create_tables()
        
        # 启用WAL模式提高并发性能
        self.conn.execute("PRAGMA journal_mode=WAL")
        # 控制 WAL 增长，尽早触发 checkpoint 并设置大小上限（默认 512MB）
        self.conn.execute("PRAGMA wal_autocheckpoint=500")
        self.conn.execute("PRAGMA journal_size_limit=536870912")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA cache_size=10000")
        # 如果存在遗留的超大 WAL，初始化时立即收缩一次
        try:
            self.checkpoint_wal(truncate=True, wal_size_mb_threshold=512)
        except Exception as e:
            logger.warning(f"Initial WAL checkpoint skipped: {e}")
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def _create_tables(self):
        """创建数据库表"""
        
        # 账户表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                provider TEXT NOT NULL,
                last_sync TIMESTAMP,
                total_emails INTEGER DEFAULT 0,
                sync_status TEXT DEFAULT 'never',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 文件夹表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                name TEXT NOT NULL,
                display_name TEXT,
                message_count INTEGER DEFAULT 0,
                unread_count INTEGER DEFAULT 0,
                last_sync TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts (id),
                UNIQUE(account_id, name)
            )
        """)
        
        # 邮件表 - 主要邮件元数据
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                folder_id INTEGER NOT NULL,
                uid TEXT NOT NULL,
                message_id TEXT,
                subject TEXT,
                sender TEXT,
                sender_email TEXT,
                recipients TEXT, -- JSON格式存储
                date_sent TIMESTAMP,
                date_received TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE,
                is_flagged BOOLEAN DEFAULT FALSE,
                is_deleted BOOLEAN DEFAULT FALSE,
                has_attachments BOOLEAN DEFAULT FALSE,
                size_bytes INTEGER DEFAULT 0,
                content_hash TEXT, -- 邮件内容hash，用于去重
                sync_status TEXT DEFAULT 'synced',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES accounts (id),
                FOREIGN KEY (folder_id) REFERENCES folders (id),
                UNIQUE(account_id, folder_id, uid)
            )
        """)
        
        # 邮件内容表 - 存储邮件正文（可选，按需加载）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS email_content (
                email_id INTEGER PRIMARY KEY,
                plain_text TEXT,
                html_text TEXT,
                headers TEXT, -- JSON格式存储完整头部
                raw_size INTEGER,
                content_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails (id) ON DELETE CASCADE
            )
        """)
        
        # 附件表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                filename TEXT,
                content_type TEXT,
                size_bytes INTEGER DEFAULT 0,
                content_id TEXT,
                is_inline BOOLEAN DEFAULT FALSE,
                data BLOB, -- 可选：存储小附件数据
                file_path TEXT, -- 可选：存储大附件到文件系统
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails (id) ON DELETE CASCADE
            )
        """)
        
        # 同步历史表
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                folder_name TEXT,
                sync_type TEXT, -- 'full', 'incremental'
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                emails_added INTEGER DEFAULT 0,
                emails_updated INTEGER DEFAULT 0,
                emails_deleted INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed'
                error_message TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts (id)
            )
        """)
        
        # 创建索引提高查询性能
        self._create_indexes()
        
        self.conn.commit()
    
    def _create_indexes(self):
        """创建数据库索引"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_emails_account_folder ON emails (account_id, folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_emails_uid ON emails (uid)",
            "CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails (message_id)",
            "CREATE INDEX IF NOT EXISTS idx_emails_date_sent ON emails (date_sent)",
            "CREATE INDEX IF NOT EXISTS idx_emails_is_read ON emails (is_read)",
            "CREATE INDEX IF NOT EXISTS idx_emails_is_flagged ON emails (is_flagged)",
            "CREATE INDEX IF NOT EXISTS idx_emails_subject ON emails (subject)",
            "CREATE INDEX IF NOT EXISTS idx_emails_sender_email ON emails (sender_email)",
            "CREATE INDEX IF NOT EXISTS idx_folders_account ON folders (account_id)",
            "CREATE INDEX IF NOT EXISTS idx_sync_history_account ON sync_history (account_id)",
            "CREATE INDEX IF NOT EXISTS idx_attachments_email ON attachments (email_id)",
            # Unique index to prevent duplicate emails per account/folder/uid
            "CREATE UNIQUE INDEX IF NOT EXISTS uniq_emails_account_folder_uid ON emails (account_id, folder_id, uid)"
        ]
        
        for index_sql in indexes:
            try:
                self.conn.execute(index_sql)
            except sqlite3.Error as e:
                logger.warning(f"Failed to create index: {e}")
    
    def add_or_update_account(self, account_id: str, email: str, provider: str) -> bool:
        """添加或更新账户信息"""
        with self._lock:
            try:
                self.conn.execute("""
                    INSERT OR REPLACE INTO accounts (id, email, provider, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (account_id, email, provider))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Failed to add/update account {account_id}: {e}")
                return False
    
    def add_or_update_folder(self, account_id: str, folder_name: str, 
                           display_name: str = None, message_count: int = 0, 
                           unread_count: int = 0, last_sync: Optional[str] = None) -> int:
        """添加或更新文件夹，返回文件夹ID"""
        with self._lock:
            try:
                last_sync_value = last_sync or datetime.now().isoformat()
                # IMPORTANT: Avoid INSERT OR REPLACE here.
                # REPLACE deletes the existing row and inserts a new one, which changes the
                # folder id and breaks foreign keys from emails.folder_id -> folders.id.
                self.conn.execute(
                    """
                    INSERT INTO folders (
                        account_id,
                        name,
                        display_name,
                        message_count,
                        unread_count,
                        last_sync
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, name) DO UPDATE SET
                        display_name = excluded.display_name,
                        message_count = excluded.message_count,
                        unread_count = excluded.unread_count,
                        last_sync = excluded.last_sync
                    """,
                    (
                        account_id,
                        folder_name,
                        display_name or folder_name,
                        message_count,
                        unread_count,
                        last_sync_value,
                    ),
                )
                
                self.conn.commit()
                
                # 获取文件夹ID
                result = self.conn.execute("""
                    SELECT id FROM folders WHERE account_id = ? AND name = ?
                """, (account_id, folder_name)).fetchone()
                
                return result['id'] if result else None
                
            except sqlite3.Error as e:
                logger.error(f"Failed to add/update folder {folder_name}: {e}")
                return None
    
    def add_or_update_email(self, email_data: Dict[str, Any]) -> Tuple[int, bool]:
        """
        添加或更新邮件
        返回: (email_id, is_new)
        """
        with self._lock:
            try:
                # 检查邮件是否已存在
                existing = self.conn.execute("""
                    SELECT id, content_hash FROM emails 
                    WHERE account_id = ? AND folder_id = ? AND uid = ?
                """, (email_data['account_id'], email_data['folder_id'], email_data['uid'])).fetchone()
                
                # 计算内容hash用于去重
                content_hash = self._calculate_content_hash(email_data)
                
                if existing:
                    email_id = existing['id']
                    # 如果内容没有变化，只更新时间戳
                    if existing['content_hash'] == content_hash:
                        self.conn.execute("""
                            UPDATE emails SET updated_at = CURRENT_TIMESTAMP 
                            WHERE id = ?
                        """, (email_id,))
                        self.conn.commit()
                        return email_id, False
                    else:
                        # 内容有变化，更新邮件
                        self._update_email(email_id, email_data, content_hash)
                        return email_id, False
                else:
                    # 新邮件，插入
                    email_id = self._insert_email(email_data, content_hash)
                    return email_id, True
                    
            except sqlite3.Error as e:
                logger.error(f"Failed to add/update email: {e}")
                return None, False

    def has_email_content(self, email_id: int) -> bool:
        """Return True when email_content exists for the given email row id."""
        with self._lock:
            try:
                row = self.conn.execute(
                    """
                    SELECT 1
                    FROM email_content
                    WHERE email_id = ?
                      AND (plain_text IS NOT NULL OR html_text IS NOT NULL)
                    LIMIT 1
                    """,
                    (int(email_id),),
                ).fetchone()
                return row is not None
            except Exception:
                return False

    def upsert_email_content(
        self,
        email_id: int,
        plain_text: Optional[str],
        html_text: Optional[str],
        headers: Optional[Dict[str, Any]] = None,
        raw_size: Optional[int] = None,
    ) -> bool:
        """Insert or update cached email body in email_content (best-effort)."""
        with self._lock:
            try:
                headers_json: Optional[str]
                if headers is None:
                    headers_json = None
                else:
                    try:
                        headers_json = json.dumps(headers, ensure_ascii=False)
                    except Exception:
                        headers_json = str(headers)

                self.conn.execute(
                    """
                    INSERT INTO email_content(email_id, plain_text, html_text, headers, raw_size)
                    VALUES(?, ?, ?, ?, ?)
                    ON CONFLICT(email_id) DO UPDATE SET
                        plain_text = excluded.plain_text,
                        html_text = excluded.html_text,
                        headers = excluded.headers,
                        raw_size = excluded.raw_size,
                        content_loaded_at = CURRENT_TIMESTAMP
                    """,
                    (
                        int(email_id),
                        plain_text,
                        html_text,
                        headers_json,
                        int(raw_size) if raw_size is not None else None,
                    ),
                )
                self.conn.commit()
                return True
            except Exception as e:
                logger.debug(f"Failed to upsert email_content for {email_id}: {e}")
                return False
    
    def _insert_email(self, email_data: Dict[str, Any], content_hash: str) -> int:
        """插入新邮件"""
        with self._lock:
            cursor = self.conn.execute("""
                INSERT INTO emails (
                    account_id, folder_id, uid, message_id, subject, sender, sender_email,
                    recipients, date_sent, is_read, is_flagged, has_attachments,
                    size_bytes, content_hash, sync_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
                ON CONFLICT(account_id, folder_id, uid) DO UPDATE SET
                    message_id=excluded.message_id,
                    subject=excluded.subject,
                    sender=excluded.sender,
                    sender_email=excluded.sender_email,
                    recipients=excluded.recipients,
                    date_sent=excluded.date_sent,
                    is_read=excluded.is_read,
                    is_flagged=excluded.is_flagged,
                    has_attachments=excluded.has_attachments,
                    size_bytes=excluded.size_bytes,
                    content_hash=excluded.content_hash,
                    updated_at=CURRENT_TIMESTAMP
            """, (
                email_data['account_id'],
                email_data['folder_id'],
                email_data['uid'],
                email_data.get('message_id'),
                email_data.get('subject'),
                email_data.get('sender'),
                email_data.get('sender_email'),
                json.dumps(email_data.get('recipients', [])),
                email_data.get('date_sent'),
                email_data.get('is_read', False),
                email_data.get('is_flagged', False),
                email_data.get('has_attachments', False),
                email_data.get('size_bytes', 0),
                content_hash
            ))
            
            self.conn.commit()
            return cursor.lastrowid
    
    def _update_email(self, email_id: int, email_data: Dict[str, Any], content_hash: str):
        """更新现有邮件"""
        with self._lock:
            self.conn.execute("""
                UPDATE emails SET
                    subject = ?, sender = ?, sender_email = ?, recipients = ?,
                    date_sent = ?, is_read = ?, is_flagged = ?, has_attachments = ?,
                    size_bytes = ?, content_hash = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                email_data.get('subject'),
                email_data.get('sender'),
                email_data.get('sender_email'),
                json.dumps(email_data.get('recipients', [])),
                email_data.get('date_sent'),
                email_data.get('is_read', False),
                email_data.get('is_flagged', False),
                email_data.get('has_attachments', False),
                email_data.get('size_bytes', 0),
                content_hash,
                email_id
            ))
            self.conn.commit()
    
    def _calculate_content_hash(self, email_data: Dict[str, Any]) -> str:
        """计算邮件内容hash"""
        content = f"{email_data.get('message_id', '')}{email_data.get('subject', '')}{email_data.get('sender', '')}{email_data.get('date_sent', '')}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def update_account_sync_status(self, account_id: str, status: str, total_emails: int) -> bool:
        """更新账户同步状态"""
        with self._lock:
            try:
                self.conn.execute("""
                    UPDATE accounts SET 
                        last_sync = CURRENT_TIMESTAMP,
                        sync_status = ?,
                        total_emails = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, total_emails, account_id))
                self.conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Failed to update account sync status for {account_id}: {e}")
                return False
    
    def get_last_sync_time(self, account_id: str) -> Optional[datetime]:
        """获取账户最后同步时间"""
        try:
            cursor = self.conn.execute(
                "SELECT last_sync FROM accounts WHERE id = ?",
                (account_id,)
            )
            row = cursor.fetchone()
            if row and row['last_sync']:
                return datetime.fromisoformat(row['last_sync'])
        except Exception as e:
            logger.warning(f"Failed to fetch last_sync for {account_id}: {e}")
        return None
    
    def get_email_count_for_account(self, account_id: str) -> Optional[int]:
        """获取账户的邮件数量"""
        with self._lock:
            try:
                cursor = self.conn.execute(
                    "SELECT COUNT(*) FROM emails WHERE account_id = ?",
                    (account_id,)
                )
                result = cursor.fetchone()
                return result[0] if result else 0
            except sqlite3.Error as e:
                logger.warning(f"Failed to fetch email count for {account_id}: {e}")
                return None
    
    def get_sync_status(self, account_id: str = None) -> Dict[str, Any]:
        """获取同步状态"""
        if account_id:
            # 单个账户状态
            account = self.conn.execute("""
                SELECT * FROM accounts WHERE id = ?
            """, (account_id,)).fetchone()
            
            if not account:
                return {'error': 'Account not found'}
            
            folders = self.conn.execute("""
                SELECT name, message_count, unread_count, last_sync
                FROM folders WHERE account_id = ?
            """, (account_id,)).fetchall()
            
            return {
                'account': dict(account),
                'folders': [dict(f) for f in folders]
            }
        else:
            # 所有账户状态
            accounts = self.conn.execute("""
                SELECT id, email, provider, last_sync, total_emails, sync_status
                FROM accounts ORDER BY email
            """).fetchall()
            
            total_emails = self.conn.execute("""
                SELECT COUNT(*) as count FROM emails WHERE is_deleted = FALSE
            """).fetchone()['count']
            
            return {
                'accounts': [dict(a) for a in accounts],
                'total_emails': total_emails,
                'database_size': self.db_path.stat().st_size if self.db_path.exists() else 0
            }
    
    def search_emails(self, query: str, account_id: str = None, 
                     folder_name: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """搜索邮件"""
        sql = """
            SELECT e.*, f.name as folder_name, a.email as account_email
            FROM emails e
            JOIN folders f ON e.folder_id = f.id
            JOIN accounts a ON e.account_id = a.id
            WHERE e.is_deleted = FALSE
        """
        params = []
        
        if query:
            sql += " AND (e.subject LIKE ? OR e.sender LIKE ? OR e.sender_email LIKE ?)"
            like_query = f"%{query}%"
            params.extend([like_query, like_query, like_query])
        
        if account_id:
            sql += " AND e.account_id = ?"
            params.append(account_id)
        
        if folder_name:
            sql += " AND f.name = ?"
            params.append(folder_name)
        
        sql += " ORDER BY e.date_sent DESC LIMIT ?"
        params.append(limit)
        
        results = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in results]
    
    def get_recent_emails(self, account_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近邮件"""
        sql = """
            SELECT e.*, f.name as folder_name, a.email as account_email
            FROM emails e
            JOIN folders f ON e.folder_id = f.id
            JOIN accounts a ON e.account_id = a.id
            WHERE e.is_deleted = FALSE
        """
        params = []
        
        if account_id:
            sql += " AND e.account_id = ?"
            params.append(account_id)
        
        sql += " ORDER BY e.date_sent DESC LIMIT ?"
        params.append(limit)
        
        results = self.conn.execute(sql, params).fetchall()
        return [dict(row) for row in results]
    
    def mark_email_read(self, email_id: int, is_read: bool = True) -> bool:
        """标记邮件读取状态"""
        try:
            self.conn.execute("""
                UPDATE emails SET is_read = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (is_read, email_id))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to mark email read: {e}")
            return False
    
    def delete_email(self, email_id: int, soft_delete: bool = True) -> bool:
        """删除邮件"""
        try:
            if soft_delete:
                self.conn.execute("""
                    UPDATE emails SET is_deleted = TRUE, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (email_id,))
            else:
                self.conn.execute("DELETE FROM emails WHERE id = ?", (email_id,))
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to delete email: {e}")
            return False

    def checkpoint_wal(self, truncate: bool = False, wal_size_mb_threshold: int = 512) -> Optional[Dict[str, Any]]:
        """
        对 WAL 进行 checkpoint，防止 email_sync.db-wal 无限制增长。

        Args:
            truncate: 使用 TRUNCATE 模式强制收缩 WAL。
            wal_size_mb_threshold: 仅当 WAL 大于该阈值时触发（MB），force 时忽略。
        """
        wal_path = Path(f"{self.db_path}-wal")
        if not wal_path.exists():
            return None

        wal_mb = wal_path.stat().st_size / (1024 * 1024)
        if not truncate and wal_mb < wal_size_mb_threshold:
            return None

        mode = "TRUNCATE" if truncate or wal_mb >= wal_size_mb_threshold else "PASSIVE"
        with self._lock:
            try:
                result = self.conn.execute(f"PRAGMA wal_checkpoint({mode})").fetchone()
                # WAL checkpoint 后顺便优化索引页
                self.conn.execute("PRAGMA optimize")
                logger.info(
                    f"WAL checkpoint ({mode}) executed: wal_size_mb={wal_mb:.1f}, result={result}"
                )
                return {
                    "mode": mode,
                    "wal_size_mb": wal_mb,
                    "result": tuple(result) if result else None
                }
            except sqlite3.Error as e:
                logger.warning(f"Failed to checkpoint WAL ({mode}): {e}")
                return None
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            # 尝试在关闭前收缩 WAL，防止下次启动看到巨大的 -wal 文件
            try:
                self.checkpoint_wal(truncate=True, wal_size_mb_threshold=0)
            except Exception:
                logger.debug("WAL checkpoint on close skipped due to error", exc_info=True)
            self.conn.close()
            self.conn = None
    
    def __del__(self):
        """析构函数，确保连接关闭"""
        self.close()
