"""
混合查询管理器 - 结合本地数据库和远程IMAP的智能查询
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from account_manager import AccountManager
from connection_manager import ConnectionManager
from database.email_sync_db import EmailSyncDatabase
from operations.email_operations import EmailOperations
from operations.email_sync import EmailSyncManager

logger = logging.getLogger(__name__)

class HybridEmailManager:
    """混合邮件管理器 - 智能结合本地缓存和远程查询"""
    
    def __init__(self, freshness_threshold_minutes: int = 5):
        """
        初始化混合管理器
        
        Args:
            freshness_threshold_minutes: 数据新鲜度阈值（分钟）
        """
        self.account_manager = AccountManager()
        self.db = EmailSyncDatabase()
        self.sync_manager = EmailSyncManager()
        self.freshness_threshold = timedelta(minutes=freshness_threshold_minutes)
        self._sync_locks = {}  # 每个账户的同步锁
        
    def list_emails(self, 
                   account_id: str = None,
                   folder: str = "INBOX",
                   limit: int = 50,
                   unread_only: bool = True,
                   freshness_required: bool = None) -> List[Dict[str, Any]]:
        """
        混合列表邮件 - 优先本地，按需远程
        
        Args:
            account_id: 账户ID
            folder: 文件夹名称
            limit: 返回数量限制
            unread_only: 只返回未读邮件
            freshness_required: 是否需要最新数据
                - None: 自动判断（默认）
                - True: 强制从远程获取
                - False: 只使用本地缓存
        """
        try:
            # 1. 检查是否需要新鲜数据
            if freshness_required is None:
                freshness_required = self._should_fetch_fresh(account_id, folder)
            
            # 2. 如果不需要新鲜数据，直接返回本地
            if not freshness_required:
                logger.info(f"Using cached emails for {account_id}/{folder}")
                return self._get_local_emails(account_id, folder, limit, unread_only)
            
            # 3. 需要新鲜数据，执行快速同步
            logger.info(f"Fetching fresh emails for {account_id}/{folder}")
            
            # 快速检查远程是否有新邮件
            if self._quick_sync_if_needed(account_id, folder):
                # 同步完成，返回本地数据
                return self._get_local_emails(account_id, folder, limit, unread_only)
            else:
                # 同步失败或超时，返回本地数据 + 警告
                emails = self._get_local_emails(account_id, folder, limit, unread_only)
                if emails:
                    emails[0]['_warning'] = 'Data might not be up-to-date'
                return emails
                
        except Exception as e:
            logger.error(f"Hybrid list emails failed: {e}")
            # 降级到纯远程查询
            return self._fallback_to_remote(account_id, folder, limit, unread_only)
    
    def search_emails(self,
                     query: str,
                     account_id: str = None,
                     search_in: str = "all",
                     date_from: str = None,
                     date_to: str = None,
                     limit: int = 50,
                     freshness_required: bool = None) -> List[Dict[str, Any]]:
        """
        混合搜索邮件
        """
        try:
            # 1. 先从本地搜索
            local_results = self._search_local(
                query, account_id, search_in, date_from, date_to, limit
            )
            
            # 2. 判断是否需要远程搜索
            if freshness_required is False:
                return local_results
            
            if freshness_required or self._should_search_remote(
                query, date_from, date_to, len(local_results)
            ):
                # 3. 触发快速同步
                accounts = [account_id] if account_id else [
                    acc['id'] for acc in self.account_manager.list_accounts()
                ]
                
                for acc_id in accounts:
                    self._quick_sync_if_needed(acc_id, search_folder=True)
                
                # 4. 重新搜索本地
                return self._search_local(
                    query, account_id, search_in, date_from, date_to, limit
                )
            
            return local_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    def mark_emails(self, email_ids: List[str], mark_as: str = "read",
                   account_id: str = None) -> Dict[str, Any]:
        """
        标记邮件 - 写透式更新
        """
        try:
            # 1. 先更新远程
            remote_result = self._mark_remote(email_ids, mark_as, account_id)
            
            if not remote_result.get('success'):
                return remote_result
            
            # 2. 更新本地数据库
            self._mark_local(email_ids, mark_as, account_id)
            
            return remote_result
            
        except Exception as e:
            logger.error(f"Hybrid mark emails failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_emails(self, email_ids: List[str], account_id: str = None,
                     permanent: bool = False) -> Dict[str, Any]:
        """
        删除邮件 - 写透式更新
        """
        try:
            # 1. 先删除远程
            remote_result = self._delete_remote(email_ids, account_id, permanent)
            
            if not remote_result.get('success'):
                return remote_result
            
            # 2. 更新本地数据库
            self._delete_local(email_ids, account_id, permanent)
            
            return remote_result
            
        except Exception as e:
            logger.error(f"Hybrid delete emails failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _should_fetch_fresh(self, account_id: str, folder: str) -> bool:
        """判断是否需要获取新鲜数据"""
        try:
            # 检查最后同步时间
            last_sync = self.db.get_folder_last_sync(account_id, folder)
            if not last_sync:
                return True
            
            # 如果超过阈值，需要新鲜数据
            time_since_sync = datetime.now() - last_sync
            return time_since_sync > self.freshness_threshold
            
        except:
            return True
    
    def _should_search_remote(self, query: str, date_from: str, 
                            date_to: str, local_count: int) -> bool:
        """判断是否需要远程搜索"""
        # 如果搜索最近的邮件，需要确保数据新鲜
        if date_from or date_to:
            try:
                if date_to:
                    to_date = datetime.strptime(date_to, "%Y-%m-%d")
                    if (datetime.now() - to_date).days < 7:
                        return True
            except:
                pass
        
        # 如果本地结果太少，可能需要远程搜索
        if local_count < 5 and len(query) > 3:
            return True
        
        return False
    
    def _quick_sync_if_needed(self, account_id: str, folder: str = None,
                            search_folder: bool = False) -> bool:
        """
        快速同步检查 - 只同步最新的邮件
        
        Returns:
            bool: 同步是否成功
        """
        # 如果没有指定账户，获取默认账户
        if not account_id:
            account = self.account_manager.get_account()  # 获取默认账户
            if not account:
                logger.warning("No accounts configured for quick sync")
                return False
            account_id = account['id']
        else:
            account = self.account_manager.get_account(account_id)
            if not account:
                return False
        
        # 获取或创建账户锁
        if account_id not in self._sync_locks:
            self._sync_locks[account_id] = threading.Lock()
        
        # 尝试获取锁，如果已在同步则跳过
        if not self._sync_locks[account_id].acquire(blocking=False):
            logger.info(f"Sync already in progress for {account_id}")
            return False
        
        try:
            
            # 连接IMAP
            conn_mgr = ConnectionManager(account)
            mail = conn_mgr.connect_imap()
            
            try:
                if search_folder:
                    # 搜索模式：同步多个重要文件夹
                    folders = ['INBOX', 'Sent', 'Drafts']
                else:
                    folders = [folder] if folder else ['INBOX']
                
                for folder_name in folders:
                    # 检查远程是否有新邮件
                    result, data = mail.select(folder_name)
                    if result != 'OK':
                        continue
                    
                    # 获取最新的邮件UID
                    result, data = mail.search(None, 'ALL')
                    if result != 'OK' or not data[0]:
                        continue
                    
                    latest_uids = data[0].split()[-10:]  # 最新的10封
                    
                    # 快速同步这些邮件
                    self._sync_specific_emails(
                        mail, account_id, folder_name, latest_uids
                    )
                
                return True
                
            finally:
                conn_mgr.close_imap(mail)
                
        except Exception as e:
            logger.error(f"Quick sync failed for {account_id}: {e}")
            return False
        finally:
            self._sync_locks[account_id].release()
    
    def _sync_specific_emails(self, mail, account_id: str, 
                            folder_name: str, uids: List[bytes]):
        """同步特定的邮件"""
        try:
            # 获取文件夹ID
            folder_id = self.db.add_or_update_folder(
                account_id, folder_name, folder_name, len(uids)
            )
            
            if not folder_id:
                return
            
            # 批量获取邮件
            for uid in uids:
                try:
                    # 获取邮件信息
                    result, data = mail.fetch(uid, '(RFC822.HEADER FLAGS UID)')
                    if result != 'OK':
                        continue
                    
                    # 解析邮件数据（复用sync_manager的方法）
                    email_data = self.sync_manager._parse_email_data(
                        data, account_id, folder_id
                    )
                    
                    if email_data:
                        # 存储到数据库
                        self.db.add_or_update_email(email_data)
                        
                except Exception as e:
                    logger.warning(f"Failed to sync email {uid}: {e}")
                    continue
            
            # 更新文件夹同步时间
            self.db.update_folder_sync_time(account_id, folder_name)
            
        except Exception as e:
            logger.error(f"Failed to sync specific emails: {e}")
    
    def _get_local_emails(self, account_id: str, folder: str,
                         limit: int, unread_only: bool) -> List[Dict[str, Any]]:
        """从本地数据库获取邮件"""
        try:
            # 构建查询条件
            conditions = []
            params = []
            
            if account_id:
                conditions.append("e.account_id = ?")
                params.append(account_id)
            
            if folder and folder != "ALL":
                conditions.append("f.name = ?")
                params.append(folder)
            
            if unread_only:
                conditions.append("e.is_read = 0")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            # 查询数据库
            sql = f"""
                SELECT 
                    e.id, e.uid, e.message_id, e.subject,
                    e.sender, e.sender_email, e.recipients,
                    e.date_sent, e.is_read, e.is_flagged,
                    e.has_attachments, e.size_bytes,
                    f.name as folder_name,
                    a.email as account_email
                FROM emails e
                JOIN folders f ON e.folder_id = f.id
                JOIN accounts a ON e.account_id = a.id
                WHERE {where_clause}
                ORDER BY e.date_sent DESC
                LIMIT ?
            """
            
            # 使用 execute 方法而不是直接访问 conn
            results = self.db.execute(sql, tuple(params + [limit]), commit=False)
            
            emails = []
            if self.db.use_pool:
                # 连接池返回的是列表
                for row in results:
                    email_dict = dict(row)
                    # 解析收件人JSON
                    if email_dict.get('recipients'):
                        import json
                        email_dict['recipients'] = json.loads(email_dict['recipients'])
                    emails.append(email_dict)
            else:
                # 直接连接返回的是游标
                for row in results.fetchall():
                    email_dict = dict(row)
                    # 解析收件人JSON
                    if email_dict.get('recipients'):
                        import json
                        email_dict['recipients'] = json.loads(email_dict['recipients'])
                    emails.append(email_dict)
            
            return emails
            
        except Exception as e:
            logger.error(f"Failed to get local emails: {e}")
            return []
    
    def _search_local(self, query: str, account_id: str, search_in: str,
                     date_from: str, date_to: str, limit: int) -> List[Dict[str, Any]]:
        """从本地数据库搜索邮件"""
        # 注意：当前的search_emails方法不支持date_from和date_to参数
        # 暂时只使用基本搜索
        return self.db.search_emails(query, account_id, limit)
    
    def _mark_remote(self, email_ids: List[str], mark_as: str,
                    account_id: str) -> Dict[str, Any]:
        """在远程标记邮件"""
        try:
            # 获取账户信息
            account = self.account_manager.get_account(account_id) if account_id else None
            if not account:
                # 如果没有指定账户，使用第一个
                accounts = self.account_manager.list_accounts()
                if not accounts:
                    return {'success': False, 'error': 'No accounts configured'}
                account = accounts[0]
            
            # 创建连接管理器
            conn_mgr = ConnectionManager(account)
            email_ops = EmailOperations(conn_mgr)
            
            # 执行标记操作
            marked_count = 0
            for email_id in email_ids:
                try:
                    if mark_as == "read":
                        result = email_ops.mark_email_read(email_id)
                    else:
                        result = email_ops.mark_email_unread(email_id)
                    
                    if result.get('success'):
                        marked_count += 1
                except:
                    continue
            
            return {
                'success': marked_count > 0,
                'marked_count': marked_count,
                'total': len(email_ids)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _mark_local(self, email_ids: List[str], mark_as: str, account_id: str):
        """在本地数据库标记邮件"""
        try:
            is_read = 1 if mark_as == "read" else 0
            
            for email_id in email_ids:
                self.db.conn.execute("""
                    UPDATE emails 
                    SET is_read = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE uid = ? OR message_id = ?
                """, (is_read, email_id, email_id))
            
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Failed to mark local emails: {e}")
    
    def _delete_remote(self, email_ids: List[str], account_id: str,
                      permanent: bool) -> Dict[str, Any]:
        """在远程删除邮件"""
        try:
            # 获取账户信息
            account = self.account_manager.get_account(account_id) if account_id else None
            if not account:
                accounts = self.account_manager.list_accounts()
                if not accounts:
                    return {'success': False, 'error': 'No accounts configured'}
                account = accounts[0]
            
            # 创建连接管理器
            conn_mgr = ConnectionManager(account)
            email_ops = EmailOperations(conn_mgr)
            
            # 执行删除操作
            deleted_count = 0
            for email_id in email_ids:
                try:
                    if permanent:
                        result = email_ops.delete_email_permanently(email_id)
                    else:
                        result = email_ops.move_to_trash(email_id)
                    
                    if result.get('success'):
                        deleted_count += 1
                except:
                    continue
            
            return {
                'success': deleted_count > 0,
                'deleted_count': deleted_count,
                'total': len(email_ids)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _delete_local(self, email_ids: List[str], account_id: str,
                     permanent: bool):
        """在本地数据库删除邮件"""
        try:
            if permanent:
                # 硬删除
                for email_id in email_ids:
                    self.db.conn.execute("""
                        DELETE FROM emails 
                        WHERE uid = ? OR message_id = ?
                    """, (email_id, email_id))
            else:
                # 软删除
                for email_id in email_ids:
                    self.db.conn.execute("""
                        UPDATE emails 
                        SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP
                        WHERE uid = ? OR message_id = ?
                    """, (email_id, email_id))
            
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete local emails: {e}")
    
    def _fallback_to_remote(self, account_id: str, folder: str,
                          limit: int, unread_only: bool) -> List[Dict[str, Any]]:
        """降级到远程查询"""
        try:
            email_ops = EmailOperations()
            return email_ops.list_emails(account_id, folder, limit, unread_only)
        except Exception as e:
            logger.error(f"Fallback to remote failed: {e}")
            return []
    
    def get_freshness_status(self) -> Dict[str, Any]:
        """获取数据新鲜度状态"""
        try:
            status = {}
            accounts = self.account_manager.list_accounts()
            
            for account in accounts:
                account_id = account['id']
                account_status = {
                    'email': account['email'],
                    'folders': {}
                }
                
                # 获取该账户的所有文件夹
                cursor = self.db.conn.execute("""
                    SELECT name, last_sync FROM folders
                    WHERE account_id = ?
                """, (account_id,))
                
                for row in cursor:
                    folder_name = row['name']
                    last_sync = row['last_sync']
                    
                    if last_sync:
                        last_sync_time = datetime.fromisoformat(last_sync)
                        age = datetime.now() - last_sync_time
                        is_fresh = age < self.freshness_threshold
                        
                        account_status['folders'][folder_name] = {
                            'last_sync': last_sync,
                            'age_minutes': int(age.total_seconds() / 60),
                            'is_fresh': is_fresh
                        }
                
                status[account_id] = account_status
            
            return status
            
        except Exception as e:
            logger.error(f"Failed to get freshness status: {e}")
            return {}