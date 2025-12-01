"""
Optimized email fetching with connection pool and batch operations
"""
import logging
import re
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
        '垃圾邮件': '垃圾邮件',
        '已删除': '已删除',
        '广告邮件': '广告邮件'
    }
}

# Friendly names used when we do not have provider-specific labels
DEFAULT_FRIENDLY_NAMES = {
    'inbox': 'INBOX',
    'spam': 'Spam',
    'junk': 'Junk',
    'trash': 'Trash',
    'deleted': 'Deleted',
    'important': 'Important'
}

FOLDER_NAME_PATTERN = re.compile(r'"(?P<name>.*)"$')


def _normalize_folder_name(name: str) -> str:
    """Normalize folder names for comparison (case-insensitive, ignore punctuation)."""
    return ''.join(ch.lower() for ch in name if ch.isalnum())


def _extract_folder_name(raw_folder: bytes) -> Optional[str]:
    """Extract the human-readable folder name from IMAP LIST response."""
    try:
        decoded = raw_folder.decode('utf-8')
    except Exception:
        decoded = str(raw_folder)
    
    match = FOLDER_NAME_PATTERN.search(decoded)
    if match:
        return match.group('name')
    
    # Fallback: take last token, removing quotes
    parts = decoded.split(' ')
    if parts:
        return parts[-1].strip('"')
    return None


def _list_available_folders(account: Dict[str, Any]) -> List[str]:
    """Return list of folders actually advertised by the IMAP server."""
    available: set[str] = set()
    try:
        conn_mgr = ConnectionManager(account)
        mail = conn_mgr.connect_imap()
        try:
            status, folders = mail.list()
            if status == 'OK' and folders:
                for entry in folders:
                    name = _extract_folder_name(entry)
                    if name:
                        available.add(name)
        finally:
            try:
                mail.logout()
            except Exception:
                pass
    except Exception as exc:
        logger.debug("Unable to list folders for %s: %s", account.get('email'), exc)
    return list(available)


def _friendly_folder_name(folder: str, provider_map: Dict[str, str]) -> str:
    """Return display-friendly folder name."""
    normalized = _normalize_folder_name(folder)
    for key, value in provider_map.items():
        if _normalize_folder_name(key) == normalized:
            return value
    return DEFAULT_FRIENDLY_NAMES.get(normalized, folder)


def _resolve_folder(candidate: str,
                    available_map: Dict[str, str]) -> Optional[str]:
    """
    Resolve candidate folder name to an actual folder advertised by the server.
    available_map maps normalized names -> actual names.
    """
    normalized = _normalize_folder_name(candidate)
    if normalized in available_map:
        return available_map[normalized]
    return None

def fetch_all_providers_optimized(limit: int = 50, unread_only: bool = True, use_cache: bool = True, account_manager=None) -> Dict[str, Any]:
    """
    Optimized fetch that checks key folders for all email providers
    
    Args:
        limit: Total email limit
        unread_only: Only fetch unread emails
        use_cache: Whether to use cached results
        account_manager: Optional AccountManager instance to reuse (avoids re-reading config)
        
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
    
    # Reuse provided manager or create new one
    if account_manager is None:
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
    
    available_folders = _list_available_folders(account)
    available_set = set(available_folders)
    available_map = {
        _normalize_folder_name(name): name for name in available_folders
    }
    provider_map = COMMON_FOLDERS.get(provider, {})
    
    # Get folders to check based on provider
    folders_to_check: List[Dict[str, Any]] = [{'name': 'INBOX', 'label': 'INBOX'}]
    
    if provider_map:
        for actual_name, friendly_label in provider_map.items():
            folders_to_check.append({'name': actual_name, 'label': friendly_label})
    
    # Also try common folder names as heuristics
    common_extras = ['Spam', 'Junk', 'Trash', 'Deleted']
    
    # Limit folders to check for performance
    max_folders = 3 if unread_only else 5
    emails_per_folder = max(20 if unread_only else 10, limit // max_folders)
    
    checked_folders = set()
    
    def _try_fetch_folder(actual_folder: str, friendly_label: Optional[str]) -> bool:
        nonlocal all_emails, total_in_all, total_unread
        if actual_folder in checked_folders:
            return False
        checked_folders.add(actual_folder)
        try:
            result = fetch_emails(
                limit=emails_per_folder,
                unread_only=unread_only,
                folder=actual_folder,
                account_id=account['id']
            )
            
            if 'error' in result:
                logger.debug("Skipping folder %s for %s: %s", actual_folder, account.get('email'), result['error'])
                return False
                
            emails = result.get('emails') or []
            if not emails:
                return False

            friendly = friendly_label or _friendly_folder_name(actual_folder, provider_map)
            for email in emails:
                email['folder'] = actual_folder
                if actual_folder.upper() != 'INBOX' and friendly:
                    email['subject'] = f"[{friendly}] {email.get('subject', '')}"
            
            all_emails.extend(emails)
            total_in_all += result.get('total_in_folder', 0)
            total_unread += result.get('unread_count', 0)
            return True
        except Exception as e:
            logger.debug("Skipping folder %s for %s due to error: %s", actual_folder, account.get('email'), e)
            return False
    
    def _resolve_and_fetch(candidate: str, label_hint: Optional[str]) -> bool:
        if not available_map:
            # Could not list folders; best effort attempt with provided name
            return _try_fetch_folder(candidate, label_hint)

        actual = candidate if candidate in available_set else _resolve_folder(candidate, available_map)
        if not actual:
            return False
        hint = None
        if label_hint and _normalize_folder_name(candidate) == _normalize_folder_name(actual):
            hint = label_hint
        return _try_fetch_folder(actual, hint)
    
    for entry in folders_to_check[:max_folders]:
        candidate = entry['name']
        label_hint = entry.get('label')
        _resolve_and_fetch(candidate, label_hint)
    
    # Try common folders if we haven't found many emails
    if len(all_emails) < limit // 2:
        for folder in common_extras:
            if available_map and not _resolve_folder(folder, available_map):
                continue
            _resolve_and_fetch(folder, None)
    
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
