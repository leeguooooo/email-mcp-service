"""
缓存邮件操作 - 从数据目录的 email_sync.db 读取缓存数据

提供比 IMAP 实时查询快 100-500x 的缓存读取能力
"""
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import os

from ..config.paths import EMAIL_SYNC_DB

logger = logging.getLogger(__name__)

class CachedEmailOperations:
    """从同步数据库缓存读取邮件"""
    
    def __init__(self, db_path=None):
        """
        初始化缓存操作
        
        Args:
            db_path: SQLite 数据库路径（默认使用 data/email_sync.db）
        """
        if db_path is None:
            db_path = EMAIL_SYNC_DB
        self.db_path = db_path
        
        # Don't cache DB existence - check dynamically
        # Service may start before sync creates the DB
        if not os.path.exists(db_path):
            logger.info(f"Sync database not found yet: {db_path}")
            logger.info("Will be created automatically by background sync")
    
    def is_available(self) -> bool:
        """检查缓存是否可用 (动态检查，不依赖缓存状态)"""
        # CRITICAL: Always check filesystem, don't rely on cached state
        # The DB may be created after service starts
        return os.path.exists(self.db_path)
    
    def list_emails_cached(self, 
                          limit: int = 50,
                          unread_only: bool = False,
                          folder: str = 'INBOX',
                          account_id: Optional[str] = None,
                          max_age_minutes: int = 10) -> Optional[Dict[str, Any]]:
        """
        从缓存读取邮件列表
        
        Args:
            limit: 邮件数量限制
            unread_only: 只显示未读邮件
            folder: 文件夹名称
            account_id: 账户ID（None 表示所有账户）
            max_age_minutes: 缓存最大有效期（分钟）
            
        Returns:
            邮件列表字典，如果缓存不可用或过期返回 None
        """
        if not self.is_available():
            logger.debug("Cache not available, falling back to live fetch")
            return None
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 返回字典式结果
            cursor = conn.cursor()
            
            # 先获取 folder_id（需要匹配 account_id）
            if account_id:
                cursor.execute("""
                    SELECT id FROM folders WHERE name = ? AND account_id = ?
                """, (folder, account_id))
            else:
                cursor.execute("""
                    SELECT id FROM folders WHERE name = ?
                """, (folder,))
            
            folder_row = cursor.fetchone()
            
            if not folder_row:
                logger.debug(f"Folder {folder} not found for account_id={account_id} in sync database")
                conn.close()
                return None
            
            folder_id = folder_row['id']
            
            # 检查缓存新鲜度
            if account_id:
                cursor.execute("""
                    SELECT MAX(last_synced) as last_sync
                    FROM emails 
                    WHERE account_id = ? AND folder_id = ?
                """, (account_id, folder_id))
            else:
                cursor.execute("""
                    SELECT MAX(last_synced) as last_sync
                    FROM emails 
                    WHERE folder_id = ?
                """, (folder_id,))
            
            row = cursor.fetchone()
            last_sync_str = row['last_sync'] if row else None
            
            if not last_sync_str:
                logger.debug(f"No sync data for account_id={account_id}, folder={folder}")
                conn.close()
                return None
            
            # 解析同步时间
            try:
                last_sync = datetime.fromisoformat(last_sync_str)
                age_minutes = (datetime.now() - last_sync).total_seconds() / 60
                
                if age_minutes > max_age_minutes:
                    logger.debug(f"Cache expired ({age_minutes:.1f} min > {max_age_minutes} min)")
                    conn.close()
                    return None
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse last_sync time: {e}")
                conn.close()
                return None
            
            # 从缓存读取邮件（folder_id 已经在上面获取）
            query = """
                SELECT 
                    uid,
                    sender_email,
                    subject,
                    date_sent,
                    is_read,
                    message_id,
                    account_id,
                    size_bytes
                FROM emails
                WHERE folder_id = ?
            """
            params = [folder_id]
            
            if account_id:
                query += " AND account_id = ?"
                params.append(account_id)
            
            if unread_only:
                query += " AND is_read = 0"
            
            query += " ORDER BY date_sent DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            # 转换为邮件列表
            emails = []
            for row in rows:
                # 格式化日期
                date_str = row['date_sent'] if row['date_sent'] else ""
                
                emails.append({
                    'id': row['uid'],
                    'uid': row['uid'],  # 明确的 UID 字段
                    'from': row['sender_email'] or '',
                    'subject': row['subject'] or 'No Subject',
                    'date': date_str,
                    'unread': not row['is_read'],
                    'message_id': row['message_id'] or '',
                    'account_id': row['account_id'],
                    'size': row['size_bytes'] or 0
                })
            
            # 获取统计信息
            if account_id:
                cursor.execute("""
                    SELECT COUNT(*) as total FROM emails 
                    WHERE account_id = ? AND folder_id = ?
                """, (account_id, folder_id))
                total = cursor.fetchone()['total']
                
                cursor.execute("""
                    SELECT COUNT(*) as unread FROM emails 
                    WHERE account_id = ? AND folder_id = ? AND is_read = 0
                """, (account_id, folder_id))
                unread_count = cursor.fetchone()['unread']
            else:
                cursor.execute("""
                    SELECT COUNT(*) as total FROM emails 
                    WHERE folder_id = ?
                """, (folder_id,))
                total = cursor.fetchone()['total']
                
                cursor.execute("""
                    SELECT COUNT(*) as unread FROM emails 
                    WHERE folder_id = ? AND is_read = 0
                """, (folder_id,))
                unread_count = cursor.fetchone()['unread']
            
            conn.close()
            
            logger.info(f"Loaded {len(emails)} emails from cache (age: {age_minutes:.1f} min)")
            
            return {
                "emails": emails,
                "total_in_folder": total,
                "unread_count": unread_count,
                "folder": folder,
                "from_cache": True,
                "cache_age_minutes": age_minutes,
                "account_id": account_id
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error reading cache: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading cached emails: {e}")
            return None
    
    def get_sync_status(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        获取同步状态
        
        Args:
            account_id: 账户ID（None 表示所有账户）
            
        Returns:
            同步状态字典
        """
        if not self.is_available():
            return {
                "available": False,
                "message": "Sync database not found"
            }
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if account_id:
                cursor.execute("""
                    SELECT 
                        account_id,
                        COUNT(*) as email_count,
                        MAX(last_synced) as last_sync,
                        MIN(last_synced) as oldest_sync
                    FROM emails
                    WHERE account_id = ?
                    GROUP BY account_id
                """, (account_id,))
            else:
                cursor.execute("""
                    SELECT 
                        account_id,
                        COUNT(*) as email_count,
                        MAX(last_synced) as last_sync,
                        MIN(last_synced) as oldest_sync
                    FROM emails
                    GROUP BY account_id
                """)
            
            accounts = []
            for row in cursor.fetchall():
                last_sync = datetime.fromisoformat(row['last_sync']) if row['last_sync'] else None
                age_minutes = (datetime.now() - last_sync).total_seconds() / 60 if last_sync else None
                
                accounts.append({
                    'account_id': row['account_id'],
                    'email_count': row['email_count'],
                    'last_sync': row['last_sync'],
                    'age_minutes': age_minutes,
                    'is_fresh': age_minutes < 10 if age_minutes else False
                })
            
            conn.close()
            
            return {
                "available": True,
                "accounts": accounts,
                "total_emails": sum(a['email_count'] for a in accounts)
            }
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return {
                "available": False,
                "error": str(e)
            }

