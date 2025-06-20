"""
Parallel email fetching for better performance
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

from ..legacy_operations import fetch_emails

logger = logging.getLogger(__name__)

class ParallelEmailFetcher:
    """Fetch emails from multiple accounts in parallel"""
    
    def __init__(self, max_workers: int = 5):
        """
        Initialize parallel fetcher
        
        Args:
            max_workers: Maximum number of concurrent connections
        """
        self.max_workers = max_workers
        self._lock = threading.Lock()
    
    def fetch_from_account(
        self, 
        account_info: Dict[str, Any], 
        limit: int, 
        unread_only: bool, 
        folder: str
    ) -> Dict[str, Any]:
        """
        Fetch emails from a single account
        
        Returns:
            Dict with emails and account info
        """
        try:
            account_id = account_info['id']
            account_email = account_info['email']
            
            logger.info(f"Fetching from {account_email}...")
            
            # Use existing fetch_emails function
            result = fetch_emails(limit, unread_only, folder, account_id)
            
            if "error" not in result:
                # Add account email to each email
                emails = result['emails']
                for email in emails:
                    email['account'] = account_email
                
                return {
                    'success': True,
                    'account': account_email,
                    'emails': emails,
                    'total': result['total_in_folder'],
                    'unread': result['unread_count'],
                    'fetched': len(emails)
                }
            else:
                return {
                    'success': False,
                    'account': account_email,
                    'error': result['error'],
                    'emails': [],
                    'total': 0,
                    'unread': 0,
                    'fetched': 0
                }
                
        except Exception as e:
            logger.error(f"Failed to fetch from {account_info.get('email', 'unknown')}: {e}")
            return {
                'success': False,
                'account': account_info.get('email', 'unknown'),
                'error': str(e),
                'emails': [],
                'total': 0,
                'unread': 0,
                'fetched': 0
            }
    
    def fetch_all_parallel(
        self,
        accounts: List[Dict[str, Any]],
        limit: int = 50,
        unread_only: bool = False,
        folder: str = "INBOX"
    ) -> Dict[str, Any]:
        """
        Fetch emails from all accounts in parallel
        
        Returns:
            Combined results from all accounts
        """
        all_emails = []
        accounts_info = []
        total_emails = 0
        total_unread = 0
        failed_accounts = []
        
        start_time = datetime.now()
        
        # Use ThreadPoolExecutor for parallel fetching
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(accounts))) as executor:
            # Submit all tasks
            future_to_account = {
                executor.submit(
                    self.fetch_from_account,
                    account,
                    limit,
                    unread_only,
                    folder
                ): account
                for account in accounts
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    result = future.result()
                    
                    if result['success']:
                        # Thread-safe operations
                        with self._lock:
                            all_emails.extend(result['emails'])
                            accounts_info.append({
                                'account': result['account'],
                                'total': result['total'],
                                'unread': result['unread'],
                                'fetched': result['fetched']
                            })
                            total_emails += result['total']
                            total_unread += result['unread']
                    else:
                        failed_accounts.append({
                            'account': result['account'],
                            'error': result['error']
                        })
                        
                except Exception as e:
                    logger.error(f"Unexpected error for account {account.get('email', 'unknown')}: {e}")
                    failed_accounts.append({
                        'account': account.get('email', 'unknown'),
                        'error': str(e)
                    })
        
        # Sort all emails by date (newest first)
        all_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Limit total results
        all_emails = all_emails[:limit]
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Parallel fetch completed in {elapsed_time:.2f} seconds")
        
        result = {
            'emails': all_emails,
            'total_emails': total_emails,
            'total_unread': total_unread,
            'accounts_count': len(accounts),
            'accounts_info': accounts_info,
            'fetch_time': elapsed_time
        }
        
        if failed_accounts:
            result['failed_accounts'] = failed_accounts
            result['success_rate'] = len(accounts_info) / len(accounts) * 100
        
        return result


# Global instance for reuse
parallel_fetcher = ParallelEmailFetcher(max_workers=5)


def fetch_emails_parallel(
    accounts: List[Dict[str, Any]],
    limit: int = 50,
    unread_only: bool = False,
    folder: str = "INBOX"
) -> Dict[str, Any]:
    """
    Convenience function to fetch emails in parallel
    """
    return parallel_fetcher.fetch_all_parallel(accounts, limit, unread_only, folder)