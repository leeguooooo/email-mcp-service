"""
邮件同步核心逻辑 - 支持多邮箱同步到SQLite
"""
import logging
import email
import email.utils
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

from ..account_manager import AccountManager
from ..connection_manager import ConnectionManager
from ..database.email_sync_db import EmailSyncDatabase
from ..connection_pool import get_connection_pool
from ..background.sync_health_monitor import get_health_monitor

logger = logging.getLogger(__name__)

class EmailSyncManager:
    """邮件同步管理器"""
    
    def __init__(self, db_path: str = "email_sync.db", config: Dict[str, Any] = None):
        """初始化同步管理器"""
        self.account_manager = AccountManager()
        self.db = EmailSyncDatabase(db_path)
        self.sync_lock = threading.Lock()
        self.sync_status = {}
        self.config = config or self._load_config()
        self.connection_pool = get_connection_pool()
        self.health_monitor = get_health_monitor()
        
    def _load_config(self) -> Dict[str, Any]:
        """加载同步配置"""
        try:
            import json
            from pathlib import Path
            config_file = Path("sync_config.json")
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get('sync', {})
        except Exception as e:
            logger.warning(f"Failed to load sync config: {e}")
        
        # 返回默认配置
        return {
            "first_sync_days": 180,
            "incremental_sync_days": 7
        }
        
    def sync_all_accounts(self, full_sync: bool = False, max_workers: int = 3) -> Dict[str, Any]:
        """
        同步所有账户邮件
        
        Args:
            full_sync: 是否执行完全同步（默认增量同步）
            max_workers: 并发同步的最大线程数
        """
        accounts = self.account_manager.list_accounts()
        if not accounts:
            return {'success': False, 'error': 'No accounts configured'}
        
        logger.info(f"Starting sync for {len(accounts)} accounts (full_sync={full_sync})")
        
        results = []
        start_time = datetime.now()
        
        # 并行同步多个账户
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交同步任务
            future_to_account = {
                executor.submit(self.sync_single_account, account['id'], full_sync): account
                for account in accounts
            }
            
            # 收集结果
            for future in as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    result = future.result()
                    result['account_email'] = account['email']
                    results.append(result)
                except Exception as e:
                    logger.error(f"Sync failed for account {account['email']}: {e}")
                    results.append({
                        'success': False,
                        'account_id': account['id'],
                        'account_email': account['email'],
                        'error': str(e)
                    })
        
        # 汇总结果
        total_added = sum(r.get('emails_added', 0) for r in results)
        total_updated = sum(r.get('emails_updated', 0) for r in results)
        successful_accounts = sum(1 for r in results if r.get('success'))
        
        sync_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'success': successful_accounts > 0,
            'accounts_synced': successful_accounts,
            'total_accounts': len(accounts),
            'emails_added': total_added,
            'emails_updated': total_updated,
            'sync_time': sync_time,
            'results': results
        }
    
    def sync_single_account(self, account_id: str, full_sync: bool = False) -> Dict[str, Any]:
        """
        同步单个账户邮件
        
        Args:
            account_id: 账户ID
            full_sync: 是否完全同步
        """
        # 验证账户存在
        account = self.account_manager.get_account(account_id)
        if not account:
            error_msg = f'Account {account_id} not found'
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
        
        logger.info(f"Syncing account {account['email']} (full_sync={full_sync})")
        
        # 记录同步开始
        sync_type = 'full' if full_sync else 'incremental'
        self.health_monitor.record_sync_start(account_id, account['email'], sync_type)
        
        start_time = datetime.now()
        
        try:
            # 更新账户信息到数据库
            self.db.add_or_update_account(account_id, account['email'], account['provider'])
            
            # 使用连接池获取连接
            with self.connection_pool.get_connection(account_id, account) as mail:
                # 获取所有文件夹
                folders = self._get_account_folders(mail, account_id)
                
                total_added = 0
                total_updated = 0
                
                # 同步每个文件夹
                for folder_name in folders:
                    try:
                        added, updated = self._sync_folder(
                            mail, account_id, folder_name, full_sync
                        )
                        total_added += added
                        total_updated += updated
                    except Exception as e:
                        logger.error(f"Failed to sync folder {folder_name}: {e}")
                
                # 更新账户同步状态
                self._update_account_sync_status(account_id, 'completed', total_added + total_updated)
                
                # 记录成功
                duration = (datetime.now() - start_time).total_seconds()
                self.health_monitor.record_sync_result(
                    account_id=account_id,
                    sync_type=sync_type,
                    status='success',
                    emails_synced=total_added + total_updated,
                    duration_seconds=duration
                )
                
                return {
                    'success': True,
                    'account_id': account_id,
                    'folders_synced': len(folders),
                    'emails_added': total_added,
                    'emails_updated': total_updated
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Account sync failed for {account_id}: {error_msg}")
            self._update_account_sync_status(account_id, 'failed', 0)
            
            # 记录失败
            duration = (datetime.now() - start_time).total_seconds()
            self.health_monitor.record_sync_result(
                account_id=account_id,
                sync_type=sync_type,
                status='failed',
                emails_synced=0,
                error_message=error_msg,
                duration_seconds=duration
            )
            
            return {
                'success': False,
                'account_id': account_id,
                'error': error_msg
            }
    
    def _get_account_folders(self, mail, account_id: str) -> List[str]:
        """获取账户的所有文件夹"""
        try:
            result, folders = mail.list()
            if result != 'OK':
                raise Exception(f"Failed to list folders: {folders}")
            
            folder_names = []
            for folder in folders:
                # 解析文件夹名称
                folder_str = folder.decode('utf-8')
                # IMAP LIST响应格式: (flags) delimiter "folder_name"
                parts = folder_str.split('"')
                if len(parts) >= 3:
                    folder_name = parts[-2]  # 取倒数第二个引号内的内容
                    folder_names.append(folder_name)
            
            # 过滤掉一些不需要同步的系统文件夹
            excluded_folders = {'[Gmail]/All Mail', '[Gmail]/Important', '[Gmail]/Chats'}
            folder_names = [f for f in folder_names if f not in excluded_folders]
            
            logger.info(f"Found {len(folder_names)} folders for account {account_id}")
            return folder_names
            
        except Exception as e:
            logger.error(f"Failed to get folders for account {account_id}: {e}")
            return ['INBOX']  # 至少同步收件箱
    
    def _sync_folder(self, mail, account_id: str, folder_name: str, 
                    full_sync: bool = False) -> Tuple[int, int]:
        """
        同步文件夹邮件
        
        Returns:
            Tuple[added_count, updated_count]
        """
        logger.info(f"Syncing folder {folder_name} for account {account_id}")
        
        try:
            # 选择文件夹
            result, data = mail.select(folder_name, readonly=True)
            if result != 'OK':
                raise Exception(f"Cannot select folder {folder_name}: {data}")
            
            total_messages = int(data[0]) if data[0] else 0
            
            # 获取文件夹ID，如果不存在则创建
            folder_id = self.db.add_or_update_folder(
                account_id, folder_name, folder_name, total_messages
            )
            
            if not folder_id:
                raise Exception(f"Failed to create/get folder {folder_name}")
            
            # 确定同步范围
            if full_sync:
                # 完全同步：获取所有邮件
                search_criteria = 'ALL'
                logger.info(f"Full sync: processing all {total_messages} messages")
            else:
                # 检查是否是首次同步（数据库中没有该账户的邮件）
                is_first_sync = self._is_first_sync(account_id)
                
                if is_first_sync:
                    # 首次同步：获取配置的天数范围内的邮件
                    days_back = self.config.get('first_sync_days', 180)  # 默认半年
                    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
                    search_criteria = f'SINCE {date_from}'
                    logger.info(f"First sync: processing messages since {date_from} (last {days_back} days)")
                else:
                    # 增量同步：获取配置的天数范围内的邮件
                    days_back = self.config.get('incremental_sync_days', 7)  # 默认7天
                    date_from = (datetime.now() - timedelta(days=days_back)).strftime("%d-%b-%Y")
                    search_criteria = f'SINCE {date_from}'
                    logger.info(f"Incremental sync: processing messages since {date_from} (last {days_back} days)")
            
            # 搜索邮件
            result, data = mail.search(None, search_criteria)
            if result != 'OK':
                logger.warning(f"Search failed for folder {folder_name}: {data}")
                return 0, 0
            
            email_ids = data[0].split() if data[0] else []
            logger.info(f"Found {len(email_ids)} messages to sync in {folder_name}")
            
            if not email_ids:
                return 0, 0
            
            # 批量获取邮件信息
            return self._fetch_and_store_emails(mail, account_id, folder_id, email_ids)
            
        except Exception as e:
            logger.error(f"Folder sync failed for {folder_name}: {e}")
            return 0, 0
    
    def _fetch_and_store_emails(self, mail, account_id: str, folder_id: int, 
                               email_ids: List[bytes]) -> Tuple[int, int]:
        """
        批量获取并存储邮件
        
        Returns:
            Tuple[added_count, updated_count]
        """
        added_count = 0
        updated_count = 0
        batch_size = 50  # 批量处理大小
        
        # 分批处理邮件
        for i in range(0, len(email_ids), batch_size):
            batch = email_ids[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(email_ids) + batch_size - 1)//batch_size}")
            
            try:
                batch_added, batch_updated = self._process_email_batch(
                    mail, account_id, folder_id, batch
                )
                added_count += batch_added
                updated_count += batch_updated
                
                # 避免过度频繁的IMAP请求
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Failed to process email batch: {e}")
                continue
        
        logger.info(f"Folder sync completed: {added_count} added, {updated_count} updated")
        return added_count, updated_count
    
    def _process_email_batch(self, mail, account_id: str, folder_id: int, 
                           email_ids: List[bytes]) -> Tuple[int, int]:
        """处理邮件批次"""
        added_count = 0
        updated_count = 0
        
        for email_id in email_ids:
            try:
                # 获取邮件头部信息
                result, data = mail.fetch(email_id, '(RFC822.HEADER FLAGS UID)')
                if result != 'OK':
                    continue
                
                # 解析邮件数据
                email_data = self._parse_email_data(data, account_id, folder_id)
                if not email_data:
                    continue
                
                # 存储到数据库
                email_db_id, is_new = self.db.add_or_update_email(email_data)
                if email_db_id:
                    if is_new:
                        added_count += 1
                    else:
                        updated_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to process email {email_id}: {e}")
                continue
        
        return added_count, updated_count
    
    def _parse_email_data(self, fetch_data: List, account_id: str, folder_id: int) -> Optional[Dict[str, Any]]:
        """解析IMAP返回的邮件数据"""
        try:
            # 提取UID
            uid = None
            flags = []
            header_data = None
            
            for response_part in fetch_data:
                if isinstance(response_part, tuple):
                    # 解析flags和UID
                    response_str = response_part[0].decode()
                    if 'UID' in response_str:
                        import re
                        uid_match = re.search(r'UID (\d+)', response_str)
                        if uid_match:
                            uid = uid_match.group(1)
                    
                    if 'FLAGS' in response_str:
                        flags_match = re.search(r'FLAGS \((.*?)\)', response_str)
                        if flags_match:
                            flags = flags_match.group(1).split()
                    
                    header_data = response_part[1]
            
            if not uid or not header_data:
                return None
            
            # 解析邮件头部
            msg = email.message_from_bytes(header_data)
            
            # 解析发件人
            from_header = msg.get('From', '')
            sender, sender_email = self._parse_email_address(from_header)
            
            # 解析收件人
            recipients = []
            for field in ['To', 'Cc', 'Bcc']:
                if msg.get(field):
                    recipients.extend(self._parse_email_addresses(msg.get(field)))
            
            # 解析日期
            date_sent = None
            date_header = msg.get('Date')
            if date_header:
                try:
                    date_tuple = email.utils.parsedate_tz(date_header)
                    if date_tuple:
                        timestamp = email.utils.mktime_tz(date_tuple)
                        date_sent = datetime.fromtimestamp(timestamp)
                except:
                    pass
            
            # 解析标志
            is_read = '\\Seen' in flags
            is_flagged = '\\Flagged' in flags
            
            return {
                'account_id': account_id,
                'folder_id': folder_id,
                'uid': uid,
                'message_id': msg.get('Message-ID', ''),
                'subject': self._decode_header(msg.get('Subject', '')),
                'sender': sender,
                'sender_email': sender_email,
                'recipients': recipients,
                'date_sent': date_sent,
                'is_read': is_read,
                'is_flagged': is_flagged,
                'has_attachments': self._has_attachments(msg),
                'size_bytes': len(header_data)
            }
            
        except Exception as e:
            logger.error(f"Failed to parse email data: {e}")
            return None
    
    def _parse_email_address(self, address_str: str) -> Tuple[str, str]:
        """解析邮件地址，返回(显示名称, 邮件地址)"""
        try:
            parsed = email.utils.parseaddr(address_str)
            name, addr = parsed
            name = self._decode_header(name) if name else addr
            return name, addr
        except:
            return address_str, address_str
    
    def _parse_email_addresses(self, addresses_str: str) -> List[Dict[str, str]]:
        """解析多个邮件地址"""
        try:
            addresses = email.utils.getaddresses([addresses_str])
            return [
                {'name': self._decode_header(name) if name else addr, 'email': addr}
                for name, addr in addresses
            ]
        except:
            return []
    
    def _decode_header(self, header_value: str) -> str:
        """解码邮件头部"""
        if not header_value:
            return ""
        
        try:
            from email.header import decode_header
            decoded_parts = decode_header(header_value)
            result = []
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        try:
                            result.append(part.decode(encoding))
                        except:
                            result.append(part.decode('utf-8', errors='ignore'))
                    else:
                        result.append(part.decode('utf-8', errors='ignore'))
                else:
                    result.append(str(part))
            
            return ' '.join(result)
        except:
            return str(header_value)
    
    def _has_attachments(self, msg: email.message.Message) -> bool:
        """检查邮件是否有附件"""
        try:
            return msg.is_multipart() and any(
                part.get_content_disposition() == 'attachment'
                for part in msg.walk()
            )
        except:
            return False
    
    def _update_account_sync_status(self, account_id: str, status: str, total_emails: int):
        """更新账户同步状态"""
        try:
            self.db.conn.execute("""
                UPDATE accounts SET 
                    last_sync = CURRENT_TIMESTAMP,
                    sync_status = ?,
                    total_emails = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, total_emails, account_id))
            self.db.conn.commit()
        except Exception as e:
            logger.error(f"Failed to update account sync status: {e}")
    
    def _is_first_sync(self, account_id: str) -> bool:
        """检查是否是账户的首次同步"""
        try:
            cursor = self.db.conn.execute(
                "SELECT COUNT(*) FROM emails WHERE account_id = ?", 
                (account_id,)
            )
            count = cursor.fetchone()[0]
            return count == 0
        except Exception as e:
            logger.warning(f"Failed to check first sync status: {e}")
            return True  # 出错时默认为首次同步，使用半年范围
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return self.db.get_sync_status()
    
    def search_cached_emails(self, query: str, account_id: str = None, 
                           limit: int = 50) -> List[Dict[str, Any]]:
        """搜索缓存的邮件"""
        return self.db.search_emails(query, account_id, limit=limit)
    
    def get_recent_emails(self, account_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取最近邮件"""
        return self.db.get_recent_emails(account_id, limit)
    
    def close(self):
        """关闭同步管理器"""
        if self.db:
            self.db.close()
