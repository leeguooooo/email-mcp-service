"""
Optimized email fetching with connection pool and batch operations
"""
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime
import time

from ..account_manager import AccountManager
from ..connection_manager import ConnectionManager
from ..legacy_operations import fetch_emails
try:
    from ..core.connection_pool import get_connection_pool
    from .batch_fetch import BatchEmailFetcher
    USE_OPTIMIZED = True
except ImportError:
    USE_OPTIMIZED = False
from .fast_fetch import get_cached_result, set_cached_result

logger = logging.getLogger(__name__)

# Common folder names to check across different providers
COMMON_FOLDERS = {
    # Standard folders (most providers)
    'INBOX': 'INBOX',
    'Spam': 'Spam',
    'Junk': 'Junk',
    'Trash': 'Trash',
    'Deleted': 'Deleted',
    
    # Provider-specific mappings
    '163': {
        '&V4NXPpCuTvY-': '垃圾邮件',
        '&Xn9USpCuTvY-': '广告邮件',
        '&XfJSIJZk-': '已删除',
        'github': 'GitHub'
    },
    'gmail': {
        '[Gmail]/Spam': 'Spam',
        '[Gmail]/Trash': 'Trash',
        '[Gmail]/Important': 'Important'
    },
    'outlook': {
        'Junk Email': 'Junk',
        'Deleted Items': 'Deleted'
    },
    'qq': {
        'Junk': '垃圾邮件',
        'Deleted': '已删除',
        'Ads': '广告邮件'
    }
}

def fetch_all_providers_optimized(limit: int = 50, unread_only: bool = True, use_cache: bool = True) -> Dict[str, Any]:
    """
    Optimized fetch that checks key folders for all email providers
    
    Args:
        limit: Total email limit
        unread_only: Only fetch unread emails
        use_cache: Whether to use cached results
        
    Returns:
        Combined results from all accounts and important folders
    """
    # Check cache first
    if use_cache:
        cache_key = f"fetch_all_{unread_only}_{limit}"
        cached = get_cached_result(cache_key)
        if cached:
            logger.info("Returning cached email results")
            return cached
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
    
    all_results = []
    start_time = datetime.now()
    
    # Process accounts in parallel
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        
        for acc_info in accounts:
            account_id = acc_info['id']
            account = account_manager.get_account(account_id)
            
            if not account:
                continue
            
            # For all providers, check multiple folders
            future = executor.submit(
                _fetch_multi_folder_smart,
                account,
                acc_info['provider'],
                limit // len(accounts),  # Distribute limit
                unread_only
            )
            
            futures.append((future, account))
        
        # Collect results
        for future, account in futures:
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                logger.error(f"Failed to fetch from {account['email']}: {e}")
                all_results.append({
                    'account': account['email'],
                    'emails': [],
                    'total': 0,
                    'unread': 0,
                    'error': str(e)
                })
    
    # Combine results
    all_emails = []
    accounts_info = []
    total_emails = 0
    total_unread = 0
    
    for result in all_results:
        if 'error' not in result:
            all_emails.extend(result['emails'])
            accounts_info.append({
                'account': result['account'],
                'total': result['total'],
                'unread': result['unread'],
                'fetched': len(result['emails'])
            })
            total_emails += result['total']
            total_unread += result['unread']
    
    # Sort by date
    all_emails.sort(key=lambda x: x.get('date', ''), reverse=True)
    
    # Apply global limit
    all_emails = all_emails[:limit]
    
    elapsed_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"Optimized fetch completed in {elapsed_time:.2f}s")
    
    result = {
        'emails': all_emails,
        'total_emails': total_emails,
        'total_unread': total_unread,
        'accounts_count': len(accounts),
        'accounts_info': accounts_info,
        'fetch_time': elapsed_time
    }
    
    # Cache successful result
    if use_cache:
        set_cached_result(cache_key, result)
    
    return result

def _fetch_multi_folder_smart(account: Dict[str, Any], provider: str, limit: int, unread_only: bool) -> Dict[str, Any]:
    """
    Smart fetch from multiple folders based on provider
    
    Only checks folders that commonly have unread emails
    """
    all_emails = []
    total_in_all = 0
    total_unread = 0
    
    # Get folders to check based on provider
    folders_to_check = ['INBOX']  # Always check INBOX
    
    # Add provider-specific folders
    if provider in COMMON_FOLDERS:
        folders_to_check.extend(COMMON_FOLDERS[provider].keys())
    
    # Also try common folder names
    common_extras = ['Spam', 'Junk', 'Trash', 'Deleted']
    
    # Limit folders to check for performance
    max_folders = 3 if unread_only else 5
    emails_per_folder = max(20 if unread_only else 10, limit // max_folders)
    
    checked_folders = set()
    
    for folder in folders_to_check[:max_folders]:
        if folder in checked_folders:
            continue
        checked_folders.add(folder)
        
        try:
            # Quick check if folder has unread
            result = fetch_emails(
                limit=emails_per_folder,
                unread_only=unread_only,
                folder=folder,
                account_id=account['id']
            )
            
            if 'error' not in result and result.get('emails'):
                emails = result['emails']
                # Add folder info
                for email in emails:
                    email['folder'] = folder
                    if folder != 'INBOX':
                        # Add folder display name
                        if provider in COMMON_FOLDERS and folder in COMMON_FOLDERS[provider]:
                            folder_name = COMMON_FOLDERS[provider][folder]
                        else:
                            folder_name = folder
                        email['subject'] = f"[{folder_name}] {email.get('subject', '')}"
                
                all_emails.extend(emails)
                total_in_all += result.get('total_in_folder', 0)
                total_unread += result.get('unread_count', 0)
                
        except Exception as e:
            logger.debug(f"Skipping folder {folder}: {e}")
            continue
    
    # Try common folders if we haven't found many emails
    if len(all_emails) < limit // 2:
        for folder in common_extras:
            if folder not in checked_folders:
                try:
                    result = fetch_emails(
                        limit=3,  # Quick check
                        unread_only=unread_only,
                        folder=folder,
                        account_id=account['id']
                    )
                    if 'error' not in result and result.get('unread_count', 0) > 0:
                        # Found unread in this folder, fetch more
                        result = fetch_emails(
                            limit=emails_per_folder,
                            unread_only=unread_only,
                            folder=folder,
                            account_id=account['id']
                        )
                        if result.get('emails'):
                            emails = result['emails']
                            for email in emails:
                                email['folder'] = folder
                                email['subject'] = f"[{folder}] {email.get('subject', '')}"
                            all_emails.extend(emails)
                            total_unread += result.get('unread_count', 0)
                except:
                    pass
    
    return {
        'account': account['email'],
        'emails': all_emails,
        'total': total_in_all,
        'unread': total_unread
    }

def _fetch_single_folder(account: Dict[str, Any], folder: str, limit: int, unread_only: bool) -> Dict[str, Any]:
    """
    Fetch from a single folder (for non-163 accounts)
    """
    try:
        result = fetch_emails(
            limit=limit,
            unread_only=unread_only,
            folder=folder,
            account_id=account['id']
        )
        
        if 'error' not in result:
            return {
                'account': account['email'],
                'emails': result.get('emails', []),
                'total': result.get('total_in_folder', 0),
                'unread': result.get('unread_count', 0)
            }
        else:
            return {
                'account': account['email'],
                'emails': [],
                'total': 0,
                'unread': 0,
                'error': result['error']
            }
            
    except Exception as e:
        logger.error(f"Failed to fetch from {account['email']}: {e}")
        return {
            'account': account['email'],
            'emails': [],
            'total': 0,
            'unread': 0,
            'error': str(e)
        }
