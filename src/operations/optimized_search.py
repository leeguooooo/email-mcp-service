"""
Optimized email search with caching and parallel processing
"""
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import hashlib
import json
from functools import lru_cache

from ..connection_manager import ConnectionManager
from ..account_manager import AccountManager
from .uid_search import UIDSearchEngine

logger = logging.getLogger(__name__)

# Simple in-memory cache for search results
_search_cache = {}
_cache_timestamps = {}
CACHE_TTL_SECONDS = 60  # 60 seconds cache


def clear_search_cache():
    """Clear in-memory search cache (used after mutations)."""
    _search_cache.clear()
    _cache_timestamps.clear()

def get_cache_key(params: Dict[str, Any]) -> str:
    """Generate cache key from search parameters"""
    # Sort params for consistent key generation
    sorted_params = json.dumps(params, sort_keys=True)
    return hashlib.md5(sorted_params.encode()).hexdigest()

def get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached result if still valid"""
    if cache_key in _search_cache:
        timestamp = _cache_timestamps.get(cache_key, 0)
        if datetime.now().timestamp() - timestamp < CACHE_TTL_SECONDS:
            logger.info(f"Using cached search result for key: {cache_key}")
            return _search_cache[cache_key]
        else:
            # Clean up expired cache
            del _search_cache[cache_key]
            del _cache_timestamps[cache_key]
    return None

def set_cached_result(cache_key: str, result: Dict[str, Any]):
    """Store result in cache"""
    _search_cache[cache_key] = result
    _cache_timestamps[cache_key] = datetime.now().timestamp()

def search_single_account(
    account_info: Dict[str, Any],
    query: str,
    search_in: str = "all",
    unread_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    folder: str = "INBOX",
    limit: int = 50,
    account_manager: Optional[AccountManager] = None
) -> Dict[str, Any]:
    """Search emails in a single account using UID search"""
    try:
        account_id = account_info['id']
        account_email = account_info['email']
        
        # Get account details
        manager = account_manager or AccountManager()
        account = manager.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        # Connect to IMAP
        conn_mgr = ConnectionManager(account)
        mail = conn_mgr.connect_imap()
        
        # Use UID search engine
        search_engine = UIDSearchEngine(mail)
        
        # Search for UIDs
        uids, total_count = search_engine.search_by_criteria(
            query=query,
            search_in=search_in,
            unread_only=unread_only,
            date_from=date_from,
            date_to=date_to,
            folder=folder,
            limit=limit
        )
        
        # Fetch email details for found UIDs
        emails = []
        if uids:
            emails = search_engine.fetch_emails_by_uids(uids, include_body=True)
            
            # Add account info to each email
            for email in emails:
                email['account'] = account_email
                email['account_id'] = account_id
                email['folder'] = folder
        
        # Close connection
        conn_mgr.close_imap()
        
        return {
            'success': True,
            'account': account_email,
            'emails': emails,
            'total_found': total_count,
            'fetched': len(emails),
            'search_params': {
                'query': query,
                'search_in': search_in,
                'folder': folder
            }
        }
        
    except Exception as e:
        logger.error(f"Search failed for {account_info.get('email', 'unknown')}: {e}")
        return {
            'success': False,
            'account': account_info.get('email', 'unknown'),
            'error': str(e),
            'emails': [],
            'total_found': 0,
            'fetched': 0
        }

def search_all_accounts_parallel(
    query: str,
    search_in: str = "all",
    unread_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    folder: str = "all",
    limit: int = 50,
    account_id: Optional[str] = None,
    account_manager: Optional[AccountManager] = None
) -> Dict[str, Any]:
    """
    Search emails across all accounts in parallel with caching

    Args:
        query: Search query string
        search_in: Field scope for search
        unread_only: Filter unread messages
        date_from: Lower bound date filter
        date_to: Upper bound date filter
        folder: IMAP folder to search (use "all" for INBOX default)
        limit: Maximum number of emails to return
        account_id: Optional constrain to a single account
        account_manager: Existing AccountManager to reuse (prevents config
            desync when callers use custom account storage)
    """
    # Check cache first
    cache_params = {
        'query': query,
        'search_in': search_in,
        'unread_only': unread_only,
        'date_from': date_from,
        'date_to': date_to,
        'folder': folder,
        'limit': limit,
        'account_id': account_id
    }
    cache_key = get_cache_key(cache_params)
    cached = get_cached_result(cache_key)
    if cached:
        return cached
    
    try:
        # Get accounts to search
        manager = account_manager or AccountManager()
        if account_id:
            account = manager.get_account(account_id)
            if not account:
                return {
                    'success': False,
                    'error': f'Account {account_id} not found'
                }
            accounts = [{'id': account_id, 'email': account['email'], 'provider': account['provider']}]
        else:
            accounts = manager.list_accounts()
        
        if not accounts:
            return {
                'success': False,
                'error': 'No email accounts configured'
            }
        
        # Determine folders to search
        folders_to_search = ['INBOX'] if folder == "all" else [folder]
        
        all_emails = []
        accounts_info = []
        failed_searches = []
        start_time = datetime.now()
        
        # Search accounts in parallel
        with ThreadPoolExecutor(max_workers=min(5, len(accounts))) as executor:
            futures = []
            
            # Submit search tasks for each account and folder combination
            for account in accounts:
                for search_folder in folders_to_search:
                    future = executor.submit(
                        search_single_account,
                        account,
                        query,
                        search_in,
                        unread_only,
                        date_from,
                        date_to,
                        search_folder,
                        limit,
                        manager
                    )
                    futures.append((future, account, search_folder))
            
            # Collect results
            for future, account, search_folder in futures:
                try:
                    result = future.result(timeout=30)
                    
                    if result['success']:
                        all_emails.extend(result['emails'])
                        
                        # Track account info
                        account_found = False
                        for info in accounts_info:
                            if info['account'] == result['account']:
                                info['total_found'] += result['total_found']
                                info['fetched'] += result['fetched']
                                info['folders_searched'].append(search_folder)
                                account_found = True
                                break
                        
                        if not account_found:
                            accounts_info.append({
                                'account': result['account'],
                                'total_found': result['total_found'],
                                'fetched': result['fetched'],
                                'folders_searched': [search_folder]
                            })
                    else:
                        failed_searches.append({
                            'account': result['account'],
                            'folder': search_folder,
                            'error': result['error']
                        })
                        
                except Exception as e:
                    logger.error(f"Search task failed: {e}")
                    failed_searches.append({
                        'account': account.get('email', 'unknown'),
                        'folder': search_folder,
                        'error': str(e)
                    })
        
        # Sort all emails by date (newest first)
        all_emails.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        # Limit total results
        all_emails = all_emails[:limit]
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        result = {
            'success': True,
            'emails': all_emails,
            'total_emails': len(all_emails),
            'accounts_searched': len(accounts),
            'accounts_info': accounts_info,
            'search_time': elapsed_time,
            'search_params': cache_params
        }
        
        if failed_searches:
            result['failed_searches'] = failed_searches
            result['partial_success'] = True
        
        # Cache successful results
        if result['success']:
            set_cached_result(cache_key, result)
        
        return result
        
    except Exception as e:
        logger.error(f"Parallel search failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }
