"""
SQLite数据库同步模块 - 修复版本，支持连接池
"""
import sqlite3
import logging
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import json
import email
from email.header import decode_header
import email.utils

logger = logging.getLogger(__name__)

class EmailSyncDatabase:
    """邮件同步数据库管理器 - 支持连接池"""
    
    def __init__(self, db_path: str = "email_sync.db", use_pool: bool = True):
        """初始化数据库连接"""
        self.db_path = Path(db_path)
        self.use_pool = use_pool
        self._pool = None
        self._conn = None
        self._initialize_database()
    
    def _initialize_database(self):
        """初始化数据库和表结构"""
        if self.use_pool:
            # 使用连接池
            from database.db_pool import get_db_pool
            self._pool = get_db_pool(str(self.db_path))
            # 使用临时连接创建表
            with self._pool.get_connection() as conn:
                self._create_tables(conn)
        else:
            # 直接连接
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row  # 返回字典格式结果
            
            # 启用WAL模式提高并发性能
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=10000")
            self._conn.execute("PRAGMA busy_timeout=30000")  # 30秒忙等待
            
            # 创建表结构
            self._create_tables(self._conn)
        
        logger.info(f"Database initialized at {self.db_path} (pool={self.use_pool})")
    
    @property
    def conn(self):
        """获取数据库连接（兼容旧代码）"""
        if self.use_pool:
            raise RuntimeError("Cannot access conn directly when using pool. Use execute() method instead.")
        return self._conn
    
    def execute(self, query: str, params: tuple = (), commit: bool = None) -> Any:
        """
        执行SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            commit: 是否提交（None=自动判断）
            
        Returns:
            查询结果
        """
        # 自动判断是否需要提交
        if commit is None:
            query_type = query.strip().upper().split()[0]
            commit = query_type in ('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')
        
        if self.use_pool:
            if commit:
                return self._pool.execute(query, params, commit=True)
            else:
                # SELECT查询
                results = self._pool.execute(query, params, commit=False)
                return results
        else:
            cursor = self._conn.execute(query, params)
            if commit:
                self._conn.commit()
                if query.strip().upper().startswith('INSERT'):
                    return cursor.lastrowid
                else:
                    return cursor.rowcount
            else:
                return cursor
    
    def execute_many(self, query: str, params_list: list, commit: bool = True) -> int:
        """批量执行SQL"""
        if self.use_pool:
            return self._pool.execute_many(query, params_list, commit)
        else:
            cursor = self._conn.executemany(query, params_list)
            if commit:
                self._conn.commit()
            return cursor.rowcount
    
    def _create_tables(self, conn):
        """创建数据库表（使用传入的连接）"""
        # 账户表
        conn.execute("""
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
        conn.execute("""
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
        conn.execute("""
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
        
        # 邮件内容表 - 分离存储大文本
        conn.execute("""
            CREATE TABLE IF NOT EXISTS email_content (
                email_id INTEGER PRIMARY KEY,
                body_text TEXT,
                body_html TEXT,
                headers TEXT, -- JSON格式存储所有邮件头
                raw_size INTEGER,
                FOREIGN KEY (email_id) REFERENCES emails (id) ON DELETE CASCADE
            )
        """)
        
        # 附件表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                filename TEXT,
                content_type TEXT,
                size_bytes INTEGER,
                content_id TEXT,
                is_inline BOOLEAN DEFAULT FALSE,
                file_path TEXT, -- 本地存储路径
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails (id) ON DELETE CASCADE
            )
        """)
        
        # 同步历史表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                sync_type TEXT NOT NULL, -- 'full', 'incremental', 'manual'
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                emails_synced INTEGER DEFAULT 0,
                emails_added INTEGER DEFAULT 0,
                emails_updated INTEGER DEFAULT 0,
                emails_deleted INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed'
                error_message TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts (id)
            )
        """)
        
        # 创建索引以提高查询性能
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_emails_account_id ON emails(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_emails_folder_id ON emails(folder_id)",
            "CREATE INDEX IF NOT EXISTS idx_emails_date_sent ON emails(date_sent)",
            "CREATE INDEX IF NOT EXISTS idx_emails_is_read ON emails(is_read)",
            "CREATE INDEX IF NOT EXISTS idx_emails_is_deleted ON emails(is_deleted)",
            "CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id)",
            "CREATE INDEX IF NOT EXISTS idx_folders_account_id ON folders(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_attachments_email_id ON attachments(email_id)",
            "CREATE INDEX IF NOT EXISTS idx_sync_history_account_id ON sync_history(account_id)",
            "CREATE INDEX IF NOT EXISTS idx_sync_history_status ON sync_history(status)",
            "CREATE INDEX IF NOT EXISTS idx_emails_search ON emails(subject, sender, sender_email)"
        ]
        
        for index_sql in indexes:
            conn.execute(index_sql)
        
        conn.commit()
    
    def add_or_update_account(self, account_id: str, email: str, provider: str) -> bool:
        """添加或更新账户信息"""
        try:
            self.execute("""
                INSERT OR REPLACE INTO accounts (id, email, provider, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (account_id, email, provider))
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to add/update account: {e}")
            return False
    
    def add_or_update_folder(self, account_id: str, folder_name: str, 
                           display_name: str = None, message_count: int = 0,
                           unread_count: int = 0) -> Optional[int]:
        """添加或更新文件夹"""
        try:
            # 先检查是否存在
            cursor = self.execute("""
                SELECT id FROM folders WHERE account_id = ? AND name = ?
            """, (account_id, folder_name), commit=False)
            
            existing = cursor.fetchone() if not self.use_pool else (cursor[0] if cursor else None)
            
            if existing:
                # 更新现有文件夹
                folder_id = existing['id'] if not self.use_pool else existing['id']
                self.execute("""
                    UPDATE folders SET 
                        display_name = COALESCE(?, display_name),
                        message_count = ?,
                        unread_count = ?,
                        last_sync = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (display_name, message_count, unread_count, folder_id))
            else:
                # 插入新文件夹
                folder_id = self.execute("""
                    INSERT INTO folders (account_id, name, display_name, message_count, unread_count)
                    VALUES (?, ?, ?, ?, ?)
                """, (account_id, folder_name, display_name or folder_name, 
                      message_count, unread_count))
            
            return folder_id
            
        except sqlite3.Error as e:
            logger.error(f"Failed to add/update folder {folder_name}: {e}")
            return None
    
    def search_emails(self, query: str, account_id: str = None, 
                     limit: int = 50, folder_name: str = None) -> List[Dict[str, Any]]:
        """搜索邮件（去重）"""
        # 使用子查询去重
        sql = """
            WITH unique_emails AS (
                SELECT 
                    e.id, e.uid, e.message_id, e.subject, e.sender, e.sender_email,
                    e.recipients, e.date_sent, e.is_read, e.is_flagged,
                    e.has_attachments, e.size_bytes, e.account_id,
                    f.name as folder_name, a.email as account_email,
                    ROW_NUMBER() OVER (PARTITION BY e.message_id, e.account_id ORDER BY e.date_sent DESC) as rn
                FROM emails e
                JOIN folders f ON e.folder_id = f.id
                JOIN accounts a ON e.account_id = a.id
                WHERE e.is_deleted = FALSE
                AND (e.subject LIKE ? OR e.sender LIKE ? OR e.sender_email LIKE ?)
            )
            SELECT * FROM unique_emails
            WHERE rn = 1
        """
        
        search_pattern = f"%{query}%"
        params = [search_pattern, search_pattern, search_pattern]
        
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        
        if folder_name:
            sql += " AND folder_name = ?"
            params.append(folder_name)
        
        sql += " ORDER BY date_sent DESC LIMIT ?"
        params.append(limit)
        
        results = self.execute(sql, tuple(params), commit=False)
        if self.use_pool:
            return [dict(row) for row in results]
        else:
            return [dict(row) for row in results.fetchall()]
    
    def get_recent_emails(self, account_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近邮件（去重）"""
        # 使用子查询先去重，选择每个message_id和account_id组合中date_sent最新的记录
        sql = """
            WITH unique_emails AS (
                SELECT e.*, 
                       f.name as folder_name, 
                       a.email as account_email,
                       ROW_NUMBER() OVER (PARTITION BY e.message_id, e.account_id ORDER BY e.date_sent DESC) as rn
                FROM emails e
                JOIN folders f ON e.folder_id = f.id
                JOIN accounts a ON e.account_id = a.id
                WHERE e.is_deleted = FALSE
            )
            SELECT * FROM unique_emails
            WHERE rn = 1
        """
        params = []
        
        if account_id:
            sql += " AND account_id = ?"
            params.append(account_id)
        
        sql += " ORDER BY date_sent DESC LIMIT ?"
        params.append(limit)
        
        results = self.execute(sql, tuple(params), commit=False)
        if self.use_pool:
            return [dict(row) for row in results]
        else:
            return [dict(row) for row in results.fetchall()]
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        # 获取账户信息
        accounts_sql = """
            SELECT id, email, provider, last_sync, total_emails, sync_status
            FROM accounts
            ORDER BY email
        """
        accounts = self.execute(accounts_sql, commit=False)
        if self.use_pool:
            accounts_list = [dict(row) for row in accounts]
        else:
            accounts_list = [dict(row) for row in accounts.fetchall()]
        
        # 获取总邮件数
        total_emails = self.execute(
            "SELECT COUNT(*) as count FROM emails WHERE is_deleted = FALSE",
            commit=False
        )
        if self.use_pool:
            total_count = total_emails[0]['count'] if total_emails else 0
        else:
            total_count = total_emails.fetchone()['count']
        
        # 获取数据库大小
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        
        return {
            'accounts': accounts_list,
            'total_emails': total_count,
            'database_size': db_size
        }
    
    def get_folder_last_sync(self, account_id: str, folder_name: str) -> Optional[datetime]:
        """获取文件夹的最后同步时间"""
        try:
            result = self.execute("""
                SELECT last_sync FROM folders 
                WHERE account_id = ? AND name = ?
            """, (account_id, folder_name), commit=False)
            
            if self.use_pool:
                row = result[0] if result else None
            else:
                row = result.fetchone()
            
            if row and row['last_sync']:
                return datetime.fromisoformat(row['last_sync'])
            return None
            
        except sqlite3.Error as e:
            logger.error(f"Failed to get folder last sync: {e}")
            return None
    
    def update_folder_sync_time(self, account_id: str, folder_name: str):
        """更新文件夹的同步时间"""
        try:
            self.execute("""
                UPDATE folders 
                SET last_sync = CURRENT_TIMESTAMP 
                WHERE account_id = ? AND name = ?
            """, (account_id, folder_name))
        except sqlite3.Error as e:
            logger.error(f"Failed to update folder sync time: {e}")
    
    def close(self):
        """关闭数据库连接"""
        if self.use_pool and self._pool:
            # 连接池会自动管理连接
            pass
        elif self._conn:
            self._conn.close()
            self._conn = None
    
    def __del__(self):
        """析构函数，确保连接关闭"""
        self.close()
    
    # 其他方法保持不变，但需要使用 execute() 替代 self.conn.execute()
    def add_or_update_email(self, email_data: Dict[str, Any]) -> Tuple[int, bool]:
        """添加或更新邮件"""
        try:
            # 检查邮件是否已存在
            existing = self.execute("""
                SELECT id, content_hash FROM emails 
                WHERE account_id = ? AND folder_id = ? AND uid = ?
            """, (email_data['account_id'], email_data['folder_id'], email_data['uid']), 
            commit=False)
            
            if self.use_pool:
                existing_row = existing[0] if existing else None
            else:
                existing_row = existing.fetchone()
            
            # 计算内容hash用于去重
            content_hash = self._calculate_content_hash(email_data)
            
            if existing_row:
                email_id = existing_row['id']
                # 如果内容没有变化，只更新时间戳
                if existing_row['content_hash'] == content_hash:
                    self.execute("""
                        UPDATE emails SET updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (email_id,))
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
    
    def _insert_email(self, email_data: Dict[str, Any], content_hash: str) -> int:
        """插入新邮件"""
        email_id = self.execute("""
            INSERT INTO emails (
                account_id, folder_id, uid, message_id, subject, sender, sender_email,
                recipients, date_sent, is_read, is_flagged, has_attachments,
                size_bytes, content_hash, sync_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'synced')
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
        
        return email_id
    
    def _update_email(self, email_id: int, email_data: Dict[str, Any], content_hash: str):
        """更新现有邮件"""
        self.execute("""
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
    
    def _calculate_content_hash(self, email_data: Dict[str, Any]) -> str:
        """计算邮件内容hash"""
        content = f"{email_data.get('message_id', '')}{email_data.get('subject', '')}{email_data.get('sender_email', '')}{email_data.get('date_sent', '')}"
        return hashlib.sha256(content.encode()).hexdigest()