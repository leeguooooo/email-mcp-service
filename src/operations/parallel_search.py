"""
Parallel search operations across multiple email accounts
"""
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

from ..connection_manager import ConnectionManager
from ..account_manager import AccountManager
from .search_operations import SearchOperations

logger = logging.getLogger(__name__)

class ParallelSearchOperations:
    """Search emails across multiple accounts in parallel"""
    
    def __init__(self, max_workers: int = 5):
        """
        Initialize parallel search handler
        
        Args:
            max_workers: Maximum number of concurrent searches
        """
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self.account_manager = AccountManager()
    
    def search_all_accounts(
        self,
        query: Optional[str] = None,
        search_in: str = "all",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        folder: str = "INBOX",
        unread_only: bool = False,
        has_attachments: Optional[bool] = None,
        limit_per_account: int = 50,
        account_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Search emails across all accounts in parallel
        
        Args:
            query: Search query text
            search_in: Where to search (subject/from/body/to/all)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            folder: Folder to search in
            unread_only: Only search unread emails
            has_attachments: Filter by attachment presence
            limit_per_account: Max results per account
            account_ids: Specific account IDs to search (None = all accounts)
            
        Returns:
            Combined search results from all accounts
        """
        # Get accounts to search
        if account_ids:
            accounts = [
                self.account_manager.get_account(acc_id) 
                for acc_id in account_ids 
                if self.account_manager.get_account(acc_id)
            ]
        else:
            accounts = self.account_manager.list_accounts()
        
        if not accounts:
            return {
                'success': False,
                'error': 'No accounts available for search',
                'emails': [],
                'total_found': 0
            }
        
        all_emails = []
        accounts_info = []
        total_found = 0
        failed_accounts = []
        
        start_time = datetime.now()
        
        # Execute searches in parallel
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(accounts))) as executor:
            # Submit search tasks
            future_to_account = {
                executor.submit(
                    self._search_single_account,
                    account,
                    query,
                    search_in,
                    date_from,
                    date_to,
                    folder,
                    unread_only,
                    has_attachments,
                    limit_per_account
                ): account
                for account in accounts
            }
            
            # Collect results
            for future in as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    result = future.result()
                    
                    if result['success']:
                        with self._lock:
                            # Add account email to each result
                            for email in result['emails']:
                                email['account'] = account['email']
                                email['account_id'] = account['id']
                            
                            all_emails.extend(result['emails'])
                            
                            accounts_info.append({
                                'account': account['email'],
                                'found': result.get('displayed', 0),
                                'total_in_account': result.get('total_found', 0)
                            })
                            
                            total_found += result.get('total_found', 0)
                    else:
                        failed_accounts.append({
                            'account': account['email'],
                            'error': result.get('error', 'Unknown error')
                        })
                        
                except Exception as e:
                    logger.error(f"Search failed for {account['email']}: {e}")
                    failed_accounts.append({
                        'account': account['email'],
                        'error': str(e)
                    })
        
        # Sort combined results by date (newest first)
        all_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        # Apply global limit if needed
        total_limit = limit_per_account * len(accounts)
        all_emails = all_emails[:total_limit]
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            'success': len(all_emails) > 0 or len(failed_accounts) < len(accounts),
            'emails': all_emails,
            'total_found': total_found,
            'displayed': len(all_emails),
            'accounts_searched': len(accounts),
            'accounts_info': accounts_info,
            'search_time': elapsed_time,
            'search_params': {
                'query': query,
                'search_in': search_in,
                'date_from': date_from,
                'date_to': date_to,
                'folder': folder,
                'unread_only': unread_only,
                'has_attachments': has_attachments
            }
        }
        
        if failed_accounts:
            result['failed_accounts'] = failed_accounts
            
        logger.info(f"Parallel search completed in {elapsed_time:.2f}s: "
                   f"found {len(all_emails)} emails from {len(accounts_info)} accounts")
        
        return result
    
    def _search_single_account(
        self,
        account: Dict[str, Any],
        query: Optional[str],
        search_in: str,
        date_from: Optional[str],
        date_to: Optional[str],
        folder: str,
        unread_only: bool,
        has_attachments: Optional[bool],
        limit: int
    ) -> Dict[str, Any]:
        """
        Search in a single account
        
        Args:
            account: Account configuration
            ... (other args same as search_all_accounts)
            
        Returns:
            Search results for this account
        """
        try:
            logger.info(f"Searching in {account['email']}...")
            
            # Create connection and search operations
            conn_mgr = ConnectionManager(account)
            search_ops = SearchOperations(conn_mgr)
            
            # Execute search
            result = search_ops.search_emails(
                query=query,
                search_in=search_in,
                date_from=date_from,
                date_to=date_to,
                folder=folder,
                unread_only=unread_only,
                has_attachments=has_attachments,
                limit=limit
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Search error for {account['email']}: {e}")
            return {
                'success': False,
                'error': str(e),
                'emails': []
            }
    
    def search_by_criteria_parallel(
        self,
        criteria: Dict[str, Any],
        account_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Search with a criteria dictionary across multiple accounts
        
        Args:
            criteria: Search criteria dict
            account_ids: Specific accounts to search
            
        Returns:
            Combined search results
        """
        return self.search_all_accounts(
            query=criteria.get('query'),
            search_in=criteria.get('search_in', 'all'),
            date_from=criteria.get('date_from'),
            date_to=criteria.get('date_to'),
            folder=criteria.get('folder', 'INBOX'),
            unread_only=criteria.get('unread_only', False),
            has_attachments=criteria.get('has_attachments'),
            limit_per_account=criteria.get('limit', 50),
            account_ids=account_ids
        )


# Global instance
parallel_search = ParallelSearchOperations(max_workers=5)