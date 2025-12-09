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
import re

from ..account_manager import AccountManager
from ..connection_manager import ConnectionManager
from ..database.email_sync_db import EmailSyncDatabase
from ..connection_pool import get_connection_pool
from ..background.sync_config import SyncConfigManager

logger = logging.getLogger(__name__)

class EmailSyncManager:
    """邮件同步管理器"""
    
    def __init__(self, db_path: str = None, config: Dict[str, Any] = None, account_manager=None):
        """
        初始化同步管理器
        
        Args:
            db_path: 数据库路径
            config: 同步配置
            account_manager: 可选的 AccountManager 实例（避免重新读取配置）
        """
        self.account_manager = account_manager or AccountManager()
        self.db = EmailSyncDatabase(db_path)
        self.sync_lock = threading.Lock()
        self.sync_status = {}
        self.config = self._normalize_config(config)
        self.connection_pool = get_connection_pool()
        # 延迟导入避免循环依赖
        self._health_monitor = None
    
    @property
    def health_monitor(self):
        """延迟加载健康监控器"""
        if self._health_monitor is None:
            from ..background.sync_health_monitor import get_health_monitor
            self._health_monitor = get_health_monitor()
        return self._health_monitor
        
    def _load_config(self) -> Dict[str, Any]:
        """加载同步配置"""
        try:
            manager = SyncConfigManager()
            config = manager.get_config()
        except Exception as e:
            logger.warning(f"Failed to load sync config via SyncConfigManager: {e}")
            config = {}
        
        # 兼容旧配置（无 sync 节点）
        sync_cfg = config.get('sync', {}) if isinstance(config.get('sync'), dict) else {}
        first_sync_days = sync_cfg.get('first_sync_days', config.get('first_sync_days', 180))
        incremental_sync_days = sync_cfg.get('incremental_sync_days', config.get('incremental_sync_days', 7))
        
        folders_cfg = config.get('folders', {})
        exclude_folders = folders_cfg.get('exclude_folders', config.get('exclude_folders', []))
        priority_folders = folders_cfg.get('priority_folders', config.get('priority_folders', []))
        sync_all = folders_cfg.get('sync_all', folders_cfg.get('sync_all', True))
        
        return {
            "first_sync_days": first_sync_days or 180,
            "incremental_sync_days": incremental_sync_days or 7,
            "folders": {
                "sync_all": sync_all,
                "exclude_folders": exclude_folders,
                "priority_folders": priority_folders
            }
        }
    
    def _normalize_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """规范化同步配置（兼容传入的全量或部分配置）"""
        if not config:
            return self._load_config()
        
        # 如果传入的就是 SyncConfigManager 的整体配置，则交给 _load_config 逻辑处理
        if isinstance(config, dict) and ('sync' in config or 'folders' in config or 'first_sync_days' in config):
            # 将外部配置与默认加载的配置合并，避免缺失字段
            base = self._load_config()
            # 提取嵌套的 sync 配置
            sync_cfg = config.get('sync', {}) if isinstance(config.get('sync'), dict) else {}
            base['first_sync_days'] = sync_cfg.get('first_sync_days', config.get('first_sync_days', base['first_sync_days']))
            base['incremental_sync_days'] = sync_cfg.get('incremental_sync_days', config.get('incremental_sync_days', base['incremental_sync_days']))
            
            folders_cfg = config.get('folders', {})
            base_folders = base.get('folders', {})
            base_folders['sync_all'] = folders_cfg.get('sync_all', base_folders.get('sync_all', True))
            base_folders['exclude_folders'] = folders_cfg.get('exclude_folders', base_folders.get('exclude_folders', []))
            base_folders['priority_folders'] = folders_cfg.get('priority_folders', base_folders.get('priority_folders', []))
            base['folders'] = base_folders
            return base
        
        # 未知格式，退回默认
        return self._load_config()
        
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
        
        # 防止 WAL 无限累积，完成全局同步后尝试收缩
        self._checkpoint_wal_safe(truncate=True, threshold_mb=256)
        
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
                folder_errors: List[Tuple[str, str]] = []
                
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
                        folder_errors.append((folder_name, str(e)))
                        continue
                
                # 记录文件夹错误，但不中断整个账户同步
                if folder_errors:
                    error_details = ", ".join(f"{name}: {err}" for name, err in folder_errors[:3])
                    logger.warning(f"Some folders failed to sync ({len(folder_errors)} folders). Sample: {error_details}")
                    # 不抛出异常，让账户同步继续完成
                
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
        finally:
            # 单账户同步时也进行 WAL 收缩，防止 -wal 文件膨胀
            self._checkpoint_wal_safe(truncate=False, threshold_mb=256)
    
    def _get_account_folders(self, mail, account_id: str) -> List[str]:
        """获取账户的所有文件夹"""
        try:
            result, folders = mail.list()
            if result != 'OK':
                raise Exception(f"Failed to list folders: {folders}")
            
            folder_names = []
            for raw_folder in folders:
                try:
                    decoded = raw_folder.decode('utf-8')
                except Exception:
                    decoded = str(raw_folder)
                # IMAP LIST 响应形如: (* FLAGS) "/" "Folder"
                match = re.search(r'\"([^"]+)\"$', decoded)
                if match:
                    folder_name = match.group(1)
                else:
                    parts = decoded.split(' ')
                    folder_name = parts[-1].strip('"') if parts else None
                if folder_name:
                    folder_names.append(folder_name)
            
            # 配置化过滤与优先级
            cfg_folders = self.config.get('folders', {})
            exclude_cfg = set(cfg_folders.get('exclude_folders', []))
            priority_cfg = cfg_folders.get('priority_folders', [])
            sync_all = cfg_folders.get('sync_all', True)
            
            # 过滤掉一些不需要同步的系统文件夹和不可选文件夹
            excluded_folders = {
                '[Gmail]',  # Gmail 伪文件夹，无法 SELECT
                '[Gmail]/All Mail', 
                '[Gmail]/Important', 
                '[Gmail]/Chats',
                'Sent Messages',  # QQ邮箱的伪文件夹
                'Deleted Messages',  # QQ邮箱的伪文件夹
                'Drafts',  # 某些邮箱的草稿箱可能无法访问
                'Junk',  # 垃圾邮件箱可能无法访问
                'NAS &W5pl9k77UqE-'  # 163邮箱的问题文件夹，EXAMINE 命令错误
            } | exclude_cfg
            folder_names = [f for f in folder_names if f not in excluded_folders]
            
            # 如果 sync_all 关闭，则只同步 priority 列表中存在的文件夹
            if not sync_all and priority_cfg:
                priority_set = set(priority_cfg)
                folder_names = [f for f in folder_names if f in priority_set]
            
            # 按优先列表排序（其余保持原顺序）
            if priority_cfg:
                priority_order = {name: idx for idx, name in enumerate(priority_cfg)}
                folder_names.sort(key=lambda name: priority_order.get(name, len(priority_order)))
            
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
                last_sync_time = self.db.get_last_sync_time(account_id)
                
                if is_first_sync or not last_sync_time:
                    # 首次同步：获取配置的天数范围内的邮件
                    days_back = self.config.get('first_sync_days', 180)  # 默认半年
                    date_from_dt = datetime.now() - timedelta(days=days_back)
                    date_from = date_from_dt.strftime("%d-%b-%Y")
                    search_criteria = f'SINCE {date_from}'
                    logger.info(f"First sync: processing messages since {date_from} (last {days_back} days)")
                else:
                    # 增量同步：从上次同步时间往前回退一天，避免边界遗漏
                    buffer_hours = 24
                    since_dt = last_sync_time - timedelta(hours=buffer_hours)
                    # 如果用户配置了最大增量窗口，则限制最远时间
                    days_back = self.config.get('incremental_sync_days', 7)
                    max_since_dt = datetime.now() - timedelta(days=days_back)
                    if since_dt < max_since_dt:
                        since_dt = max_since_dt
                    date_from = since_dt.strftime("%d-%b-%Y")
                    search_criteria = f'SINCE {date_from}'
                    logger.info(f"Incremental sync: processing messages since {date_from} (last sync {last_sync_time})")
            
            # 搜索邮件
            result, data = mail.uid('search', None, search_criteria)
            if result != 'OK':
                logger.warning(f"UID search failed for folder {folder_name}: {data}")
                return 0, 0
            
            email_ids = data[0].split() if data[0] else []
            logger.info(f"Found {len(email_ids)} messages to sync in {folder_name}")
            
            if not email_ids:
                # 更新文件夹同步时间
                self.db.add_or_update_folder(
                    account_id, folder_name, folder_name, total_messages, last_sync=datetime.now().isoformat()
                )
                return 0, 0
            
            # 批量获取邮件信息
            added, updated = self._fetch_and_store_emails(mail, account_id, folder_id, email_ids)
            
            # 更新文件夹同步时间
            self.db.add_or_update_folder(
                account_id, folder_name, folder_name, total_messages, last_sync=datetime.now().isoformat()
            )
            
            return added, updated
            
        except Exception as e:
            logger.error(f"Folder sync failed for {folder_name}: {e}")
            # 重新抛出异常，让上层知道同步失败
            raise
    
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
                result, data = mail.uid('fetch', email_id, '(RFC822.HEADER FLAGS UID)')
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
        if not self.db.update_account_sync_status(account_id, status, total_emails):
            logger.error(f"Failed to update account sync status for {account_id}")
    
    def _is_first_sync(self, account_id: str) -> bool:
        """检查是否是账户的首次同步"""
        count = self.db.get_email_count_for_account(account_id)
        if count is None:
            logger.warning("Failed to check first sync status from database, defaulting to first sync")
            return True
        return count == 0
    
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
    
    def _checkpoint_wal_safe(self, truncate: bool, threshold_mb: int):
        """Best-effort WAL checkpoint，避免异常抛出影响业务流程"""
        try:
            self.db.checkpoint_wal(truncate=truncate, wal_size_mb_threshold=threshold_mb)
        except Exception:
            logger.debug("Skip WAL checkpoint due to error", exc_info=True)
    
    def close(self):
        """关闭同步管理器"""
        if self.db:
            self.db.close()
