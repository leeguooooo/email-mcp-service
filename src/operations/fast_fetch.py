"""
Fast email fetching with minimal overhead
"""
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading

from ..account_manager import AccountManager
from ..legacy_operations import fetch_emails

logger = logging.getLogger(__name__)

# Simple cache for recent fetches
_fetch_cache = {}
_cache_lock = threading.Lock()
_cache_ttl = 300  # 5 minutes (increased from 30s)

def get_cached_result(key: str) -> Optional[Dict]:
    """Get cached result if available and not expired"""
    with _cache_lock:
        if key in _fetch_cache:
            timestamp, data = _fetch_cache[key]
            if (datetime.now() - timestamp).total_seconds() < _cache_ttl:
                logger.info(f"Cache hit for {key}")
                return data
            else:
                del _fetch_cache[key]
    return None

def set_cached_result(key: str, data: Dict):
    """Cache a result"""
    with _cache_lock:
        _fetch_cache[key] = (datetime.now(), data)
        # Limit cache size
        if len(_fetch_cache) > 10:
            # Remove oldest entries
            sorted_items = sorted(_fetch_cache.items(), key=lambda x: x[1][0])
            for old_key, _ in sorted_items[:5]:
                del _fetch_cache[old_key]

def fast_fetch_single_account(account_id: str, limit: int, unread_only: bool) -> Dict[str, Any]:
    """Fast fetch for a single account - only check INBOX for speed"""
    try:
        # Only check INBOX for maximum speed
        result = fetch_emails(
            limit=limit,
            unread_only=unread_only,
            folder='INBOX',
            account_id=account_id
        )
        
        if 'error' in result:
            return {
                'account_id': account_id,
                'emails': [],
                'total': 0,
                'unread': 0,
                'error': result['error']
            }
        
        return {
            'account_id': account_id,
            'emails': result.get('emails', []),
            'total': result.get('total_emails', 0),
            'unread': result.get('unread_count', 0)
        }
    except Exception as e:
        logger.error(f"Fast fetch failed for {account_id}: {e}")
        return {
            'account_id': account_id,
            'emails': [],
            'total': 0,
            'unread': 0,
            'error': str(e)
        }

def fast_fetch_all_accounts(limit: int = 50, unread_only: bool = True) -> Dict[str, Any]:
    """Fast parallel fetch from all accounts"""
    # Check cache first
    cache_key = f"fast_fetch_{unread_only}_{limit}"
    cached = get_cached_result(cache_key)
    if cached:
        return cached
    
    start_time = datetime.now()
    account_manager = AccountManager()
    accounts = account_manager.list_accounts()
    
    if not accounts:
        return {
            'emails': [],
            'total_emails': 0,
            'total_unread': 0,
            'accounts_count': 0,
            'accounts_info': []
        }
    
    # Calculate limit per account
    limit_per_account = max(10, limit // len(accounts))
    
    # Fetch from all accounts in parallel
    all_results = []
    failed_accounts = []
    
    with ThreadPoolExecutor(max_workers=min(5, len(accounts))) as executor:
        future_to_account = {
            executor.submit(
                fast_fetch_single_account,
                acc['id'],
                limit_per_account,
                unread_only
            ): acc
            for acc in accounts
        }
        
        for future in as_completed(future_to_account, timeout=10):
            account = future_to_account[future]
            try:
                result = future.result()
                if 'error' in result:
                    failed_accounts.append({
                        'account': account['email'],
                        'error': result['error']
                    })
                else:
                    # Add account email to result
                    result['account_email'] = account['email']
                    result['provider'] = account['provider']
                    all_results.append(result)
            except Exception as e:
                logger.error(f"Failed to fetch from {account['email']}: {e}")
                failed_accounts.append({
                    'account': account['email'],
                    'error': str(e)
                })
    
    # Combine results
    all_emails = []
    accounts_info = []
    total_emails = 0
    total_unread = 0
    
    for result in all_results:
        emails = result.get('emails', [])
        # Add account info to each email
        for email in emails:
            email['account'] = result['account_email']
        
        all_emails.extend(emails)
        
        accounts_info.append({
            'account': result['account_email'],
            'provider': result['provider'],
            'fetched': len(emails),
            'total': result.get('total', 0),
            'unread': result.get('unread', 0)
        })
        
        total_emails += result.get('total', 0)
        total_unread += result.get('unread', 0)
    
    # Sort by date (newest first)
    all_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # Apply global limit
    all_emails = all_emails[:limit]
    
    elapsed_time = (datetime.now() - start_time).total_seconds()
    
    result = {
        'emails': all_emails,
        'total_emails': total_emails,
        'total_unread': total_unread,
        'accounts_count': len(accounts),
        'accounts_info': accounts_info,
        'failed_accounts': failed_accounts,
        'fetch_time': elapsed_time
    }
    
    # Cache the result
    set_cached_result(cache_key, result)
    
    logger.info(f"Fast fetch completed in {elapsed_time:.2f}s - {len(all_emails)} emails from {len(accounts)} accounts")
    
    return result
