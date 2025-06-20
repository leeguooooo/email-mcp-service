"""
Scan all folders for unread emails
"""
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from ..connection_manager import ConnectionManager
from ..account_manager import AccountManager

logger = logging.getLogger(__name__)

class FolderScanner:
    """Scan all folders in email accounts for unread messages"""
    
    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self.account_manager = AccountManager()
    
    def scan_all_folders(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Scan all folders in specified account(s) for unread emails
        
        Args:
            account_id: Specific account to scan, or None for all accounts
            
        Returns:
            Dict with folder scan results
        """
        if account_id:
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'success': False, 'error': f'Account not found: {account_id}'}
            accounts = [account]
        else:
            accounts = [
                self.account_manager.get_account(acc['id']) 
                for acc in self.account_manager.list_accounts()
            ]
        
        all_results = []
        
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(accounts))) as executor:
            futures = {
                executor.submit(self._scan_account_folders, account): account
                for account in accounts if account
            }
            
            for future in as_completed(futures):
                account = futures[future]
                try:
                    result = future.result()
                    all_results.append(result)
                except Exception as e:
                    logger.error(f"Failed to scan {account['email']}: {e}")
                    all_results.append({
                        'account': account['email'],
                        'success': False,
                        'error': str(e)
                    })
        
        return {
            'success': True,
            'accounts_scanned': len(all_results),
            'results': all_results
        }
    
    def _scan_account_folders(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """Scan all folders in a single account"""
        try:
            conn_mgr = ConnectionManager(account)
            mail = conn_mgr.connect_imap()
            
            # List all folders
            result, folders = mail.list()
            if result != 'OK':
                raise ValueError("Failed to list folders")
            
            folder_results = []
            total_unread = 0
            
            for folder_data in folders:
                try:
                    # Parse folder name
                    parts = folder_data.decode('utf-8').split(' "." ')
                    if len(parts) >= 2:
                        folder_name = parts[-1].strip('"')
                        
                        # Skip certain system folders
                        skip_folders = ['[Gmail]', 'Notes', 'Junk E-mail']
                        if any(skip in folder_name for skip in skip_folders):
                            continue
                        
                        # Select folder
                        result, data = mail.select(folder_name, readonly=True)
                        if result == 'OK':
                            total_messages = int(data[0].decode()) if data[0] else 0
                            
                            # Search for unread
                            result, data = mail.search(None, 'UNSEEN')
                            if result == 'OK':
                                unread_ids = data[0].split() if data[0] else []
                                unread_count = len(unread_ids)
                                
                                if unread_count > 0:
                                    folder_results.append({
                                        'folder': folder_name,
                                        'total': total_messages,
                                        'unread': unread_count
                                    })
                                    total_unread += unread_count
                                    
                                    logger.info(f"{account['email']}: {folder_name} has {unread_count} unread")
                            
                except Exception as e:
                    logger.warning(f"Failed to scan folder {folder_name}: {e}")
                    continue
            
            mail.logout()
            
            return {
                'account': account['email'],
                'provider': account.get('provider'),
                'success': True,
                'total_unread': total_unread,
                'folders_with_unread': folder_results
            }
            
        except Exception as e:
            logger.error(f"Failed to scan folders for {account['email']}: {e}")
            return {
                'account': account['email'],
                'success': False,
                'error': str(e)
            }
    
    def fetch_unread_from_all_folders(
        self, 
        account_id: Optional[str] = None,
        limit_per_folder: int = 10
    ) -> Dict[str, Any]:
        """
        Fetch unread emails from all folders
        
        Args:
            account_id: Specific account or None for all
            limit_per_folder: Max emails to fetch per folder
            
        Returns:
            Dict with emails from all folders
        """
        # First scan to find folders with unread
        scan_result = self.scan_all_folders(account_id)
        
        if not scan_result['success']:
            return scan_result
        
        all_emails = []
        
        for account_result in scan_result['results']:
            if not account_result.get('success'):
                continue
                
            account_email = account_result['account']
            folders_with_unread = account_result.get('folders_with_unread', [])
            
            if not folders_with_unread:
                continue
            
            # Get account data for fetching
            account = None
            for acc in self.account_manager.list_accounts():
                if acc['email'] == account_email:
                    account = self.account_manager.get_account(acc['id'])
                    break
            
            if not account:
                continue
            
            # Fetch from each folder with unread
            for folder_info in folders_with_unread:
                folder_name = folder_info['folder']
                try:
                    emails = self._fetch_from_folder(
                        account, 
                        folder_name, 
                        limit_per_folder
                    )
                    all_emails.extend(emails)
                except Exception as e:
                    logger.error(f"Failed to fetch from {folder_name}: {e}")
        
        # Sort by date
        all_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return {
            'success': True,
            'emails': all_emails,
            'total_found': len(all_emails),
            'scan_summary': scan_result
        }
    
    def _fetch_from_folder(
        self, 
        account: Dict[str, Any], 
        folder: str, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Fetch unread emails from a specific folder"""
        from ..legacy_operations import fetch_emails
        
        # Use existing fetch function with specific folder
        result = fetch_emails(
            limit=limit,
            unread_only=True,
            folder=folder,
            account_id=account['id']
        )
        
        if 'error' not in result:
            emails = result.get('emails', [])
            # Add folder info to each email
            for email in emails:
                email['folder'] = folder
                email['account'] = account['email']
            return emails
        
        return []


# Global instance
folder_scanner = FolderScanner()