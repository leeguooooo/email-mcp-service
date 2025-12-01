"""
Enhanced email fetching from multiple folders
"""
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

from ..connection_manager import ConnectionManager
from ..account_manager import AccountManager
from ..legacy_operations import fetch_emails

logger = logging.getLogger(__name__)

# UTF-7 folder name mappings for 163
FOLDER_NAME_MAP = {
    '&g0l6P3ux-': '草稿箱',
    '&XfJT0ZAB-': '已发送',
    '&XfJSIJZk-': '已删除',
    '&V4NXPpCuTvY-': '垃圾邮件',
    '&dcVr0mWHTvZZOQ-': '病毒文件夹',
    '&Xn9USpCuTvY-': '广告邮件',
    '&i6KWBZCuTvY-': '订阅邮件',
    '&ZeB1KJCuTvY-': '通知邮件',
    '&lj+RzE6R-': '计费',
    '&XA98cw-': '开票'
}

class MultiFolderFetcher:
    """Fetch emails from multiple folders across accounts"""
    
    def __init__(self, max_workers: int = 5, account_manager=None):
        """
        Initialize multi-folder fetcher
        
        Args:
            max_workers: Maximum number of concurrent operations
            account_manager: Optional AccountManager instance to reuse (avoids re-reading config)
        """
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self.account_manager = account_manager or AccountManager()
    
    def fetch_all_unread(
        self,
        account_id: Optional[str] = None,
        limit_per_folder: int = 50,
        include_folders: Optional[List[str]] = None,
        exclude_folders: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Fetch unread emails from all folders
        
        Args:
            account_id: Specific account or None for all
            limit_per_folder: Max emails per folder
            include_folders: Only include these folders (None = all)
            exclude_folders: Exclude these folders
            
        Returns:
            Combined results from all folders
        """
        # Default exclude list
        if exclude_folders is None:
            exclude_folders = ['&g0l6P3ux-', 'Drafts', '草稿箱', 'Notes']
        
        # Get accounts to process
        if account_id:
            account = self.account_manager.get_account(account_id)
            accounts = [account] if account else []
        else:
            accounts = [
                self.account_manager.get_account(acc['id'])
                for acc in self.account_manager.list_accounts()
            ]
        
        all_results = []
        start_time = datetime.now()
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(accounts))) as executor:
            futures = {
                executor.submit(
                    self._fetch_account_all_folders,
                    account,
                    limit_per_folder,
                    include_folders,
                    exclude_folders
                ): account
                for account in accounts if account
            }
            
            for future in as_completed(futures):
                account = futures[future]
                try:
                    result = future.result()
                    all_results.append(result)
                except Exception as e:
                    logger.error(f"Failed to fetch from {account['email']}: {e}")
                    all_results.append({
                        'account': account['email'],
                        'success': False,
                        'error': str(e),
                        'emails': [],
                        'folders_info': []
                    })
        
        # Combine all results
        all_emails = []
        total_unread = 0
        accounts_info = []
        failed_accounts = []
        
        for result in all_results:
            if result['success']:
                all_emails.extend(result['emails'])
                total_unread += result['total_unread']
                accounts_info.append({
                    'account': result['account'],
                    'folders_checked': result['folders_checked'],
                    'total_unread': result['total_unread'],
                    'folders_info': result['folders_info']
                })
            else:
                failed_accounts.append({
                    'account': result['account'],
                    'error': result.get('error', 'Unknown error')
                })
        
        # Sort by date
        all_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            'success': True,
            'emails': all_emails,
            'total_emails': len(all_emails),
            'total_unread': total_unread,
            'accounts_info': accounts_info,
            'fetch_time': elapsed_time
        }
        
        if failed_accounts:
            result['failed_accounts'] = failed_accounts
        
        logger.info(f"Multi-folder fetch completed in {elapsed_time:.2f}s: "
                   f"{len(all_emails)} emails from {len(accounts_info)} accounts")
        
        return result
    
    def _fetch_account_all_folders(
        self,
        account: Dict[str, Any],
        limit_per_folder: int,
        include_folders: Optional[List[str]],
        exclude_folders: List[str]
    ) -> Dict[str, Any]:
        """Fetch unread from all folders in one account"""
        try:
            conn_mgr = ConnectionManager(account)
            mail = conn_mgr.connect_imap()
            
            # List all folders
            result, folders = mail.list()
            if result != 'OK':
                raise ValueError("Failed to list folders")
            
            all_emails = []
            folders_info = []
            total_unread = 0
            folders_checked = 0
            
            for folder_data in folders:
                try:
                    # Parse folder name
                    folder_str = folder_data.decode('utf-8')
                    
                    # Try different parsing methods
                    folder_name = None
                    
                    # Method 1: Standard format with separator
                    if ' "/" ' in folder_str:
                        parts = folder_str.split(' "/" ')
                        if len(parts) >= 2:
                            folder_name = parts[-1].strip('"')
                    # Method 2: Other separators
                    elif '"." ' in folder_str:
                        parts = folder_str.split('"." ')
                        folder_name = parts[-1].strip('"')
                    elif '" " ' in folder_str:
                        parts = folder_str.split('" " ')
                        folder_name = parts[-1].strip('"')
                    else:
                        # Method 3: Extract quoted string at end
                        import re
                        match = re.search(r'"([^"]+)"$', folder_str)
                        if match:
                            folder_name = match.group(1)
                    
                    if not folder_name:
                        logger.warning(f"Could not parse folder name from: {folder_str}")
                        continue
                    
                    # Check include/exclude
                    if include_folders and folder_name not in include_folders:
                        continue
                    if exclude_folders and folder_name in exclude_folders:
                        continue
                    
                    # Select folder and check for unread
                    result, data = mail.select(folder_name, readonly=True)
                    if result == 'OK':
                        # Quick check for unread
                        result, data = mail.search(None, 'UNSEEN')
                        if result == 'OK' and data[0]:
                            unread_ids = data[0].split()
                            unread_count = len(unread_ids)
                            
                            if unread_count > 0:
                                # Get human-readable folder name
                                display_name = FOLDER_NAME_MAP.get(folder_name, folder_name)
                                
                                logger.info(f"{account['email']}: Found {unread_count} unread in {display_name}")
                                
                                # Fetch emails from this folder
                                folder_emails = self._fetch_from_folder(
                                    account,
                                    folder_name,
                                    min(limit_per_folder, unread_count)
                                )
                                
                                # Add folder info to emails
                                for email in folder_emails:
                                    email['folder'] = folder_name
                                    email['folder_display'] = display_name
                                
                                all_emails.extend(folder_emails)
                                
                                folders_info.append({
                                    'folder': folder_name,
                                    'folder_display': display_name,
                                    'unread': unread_count,
                                    'fetched': len(folder_emails)
                                })
                                
                                total_unread += unread_count
                        
                        folders_checked += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to check folder {folder_name}: {e}")
                    continue
            
            mail.logout()
            
            return {
                'account': account['email'],
                'success': True,
                'emails': all_emails,
                'total_unread': total_unread,
                'folders_checked': folders_checked,
                'folders_info': folders_info
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch from {account['email']}: {e}")
            return {
                'account': account['email'],
                'success': False,
                'error': str(e),
                'emails': [],
                'folders_info': []
            }
    
    def _fetch_from_folder(
        self,
        account: Dict[str, Any],
        folder: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch emails from specific folder"""
        try:
            result = fetch_emails(
                limit=limit,
                unread_only=True,
                folder=folder,
                account_id=account['id']
            )
            
            if 'error' not in result:
                return result.get('emails', [])
            
        except Exception as e:
            logger.error(f"Failed to fetch from {folder}: {e}")
        
        return []


# Global instance
multi_folder_fetcher = MultiFolderFetcher()