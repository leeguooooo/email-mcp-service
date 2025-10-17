"""
Legacy operations from original main.py
Preserved for backward compatibility
"""
import imaplib
import email
from email.header import decode_header
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json
from pathlib import Path
import os

from .connection_manager import ConnectionManager
from .account_manager import AccountManager

logger = logging.getLogger(__name__)

# Initialize account manager
account_manager = AccountManager()

def get_connection_manager(account_id: Optional[str] = None) -> ConnectionManager:
    """Get connection manager for account"""
    account = account_manager.get_account(account_id)
    if not account:
        raise ValueError("No email account configured")
    return ConnectionManager(account)

def decode_mime_words(s):
    """Decode MIME encoded words in headers"""
    if not s:
        return ""
    decoded = decode_header(s)
    result = ""
    for text, encoding in decoded:
        if isinstance(text, bytes):
            result += text.decode(encoding or 'utf-8', errors='ignore')
        else:
            result += text
    return result

def _normalize_folder_name(folder: Optional[Union[str, bytes]]) -> Union[str, bytes]:
    """
    Prepare folder/mailbox name for IMAP commands.
    Ensures spaces and special characters are properly quoted and
    non-ASCII names are IMAP UTF-7 encoded.
    """
    if not folder:
        return "INBOX"
    if isinstance(folder, bytes):
        return folder
    # Strip leading/trailing whitespace but keep original if it matters
    folder_str = folder.strip() or "INBOX"
    # Encode to IMAP UTF-7 when non-ASCII characters are present
    try:
        folder_str.encode('ascii')
        encoded = folder_str
    except UnicodeEncodeError:
        try:
            encoded_bytes = imaplib.IMAP4._encode_utf7(folder_str)
            encoded = encoded_bytes.decode('ascii') if isinstance(encoded_bytes, bytes) else encoded_bytes
        except Exception:
            encoded = folder_str
    try:
        return imaplib.IMAP4._quote(encoded)
    except Exception:
        # Fallback: add double quotes if there are spaces or special chars
        if any(ch.isspace() for ch in encoded) and not (encoded.startswith('"') and encoded.endswith('"')):
            return f'"{encoded}"'
        return encoded

def get_mailbox_status(folder="INBOX", account_id=None):
    """Get mailbox status"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        # Select the folder
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        
        if result != 'OK':
            raise Exception(f"Cannot select folder {folder}")
        
        # Get total emails
        result, data = mail.search(None, 'ALL')
        total = len(data[0].split()) if data[0] else 0
        
        # Get unread emails
        result, data = mail.search(None, 'UNSEEN')
        unread = len(data[0].split()) if data[0] else 0
        
        mail.logout()
        
        return {
            "total_emails": total,
            "unread_emails": unread,
            "folder": folder,
            "account": conn_mgr.email
        }
        
    except Exception as e:
        logger.error(f"Error getting mailbox status: {e}")
        return {"error": str(e)}

def get_unread_count(account_id=None):
    """Get unread email count"""
    try:
        result = get_mailbox_status("INBOX", account_id)
        if "error" in result:
            raise Exception(result["error"])
        return result["unread_emails"]
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        raise

def check_connection():
    """Check all email connections"""
    try:
        accounts = account_manager.list_accounts()
        
        if accounts:
            results = []
            for account_info in accounts:
                account_id = account_info['id']
                try:
                    conn_mgr = get_connection_manager(account_id)
                    test_result = conn_mgr.test_connection()
                    results.append(test_result)
                except Exception as e:
                    results.append({
                        'email': account_info['email'],
                        'provider': account_info['provider'],
                        'imap': {'success': False, 'error': str(e)},
                        'smtp': {'success': False, 'error': 'Not tested'}
                    })
            
            return {
                'success': True,
                'accounts': results,
                'total_accounts': len(accounts)
            }
        else:
            # Fallback to env vars
            conn_mgr = get_connection_manager()
            return conn_mgr.test_connection()
            
    except Exception as e:
        logger.error(f"Connection check failed: {e}")
        return {'error': str(e)}

def fetch_emails(limit=50, unread_only=False, folder="INBOX", account_id=None, use_cache=False):
    """
    Fetch emails from account
    
    Args:
        limit: Maximum number of emails to fetch
        unread_only: Only fetch unread emails
        folder: Folder name (default: INBOX)
        account_id: Specific account ID (None = all accounts)
        use_cache: Try to use cached data from email_sync.db (default: False)
    """
    try:
        # If no specific account, fetch from all accounts
        # CRITICAL: Must check this BEFORE trying cache, because cache only works for single account
        if account_id is None and account_manager.list_accounts():
            return fetch_emails_multi_account(limit, unread_only, folder, use_cache)
        
        # Try cache first if requested (only for single account)
        if use_cache and account_id is not None:
            try:
                from .operations.cached_operations import CachedEmailOperations
                cache = CachedEmailOperations()
                
                if cache.is_available():
                    logger.info(f"Using cached email data for account {account_id}")
                    result = cache.list_emails_cached(
                        limit=limit,
                        unread_only=unread_only,
                        folder=folder,
                        account_id=account_id
                    )
                    # Cache returns None if expired/missing, or dict (even if emails=[]) if valid
                    if result is not None:
                        logger.info(f"Cache hit: {len(result.get('emails', []))} emails (age: {result.get('cache_age_minutes', 0):.1f} min)")
                        return result
                    else:
                        logger.info("Cache miss or expired, falling back to live fetch")
            except Exception as e:
                logger.warning(f"Cache fetch failed, falling back to live IMAP: {e}")
        
        # Single account fetch
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        try:
            # Select folder and check status
            selected_folder = _normalize_folder_name(folder)
            result, data = mail.select(selected_folder)
            if result != 'OK':
                raise ValueError(f"Cannot select folder '{folder}': {data}")
            
            # CRITICAL: Use UID search instead of sequence numbers
            # UIDs are stable even when messages are added/deleted
            if unread_only:
                result, data = mail.uid('search', None, 'UNSEEN')
            else:
                result, data = mail.uid('search', None, 'ALL')
            
            email_uids = data[0].split()
            total_in_folder = len(email_uids)
            
            # Get unread count
            result, data = mail.uid('search', None, 'UNSEEN')
            unread_count = len(data[0].split()) if data[0] else 0
            
            # Limit emails (UIDs)
            email_uids = email_uids[-limit:]
            email_uids.reverse()
            
            emails = []
            for email_uid in email_uids:
                try:
                    # CRITICAL: Use UID FETCH to get stable identifiers
                    result, data = mail.uid('fetch', email_uid, '(RFC822)')
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Parse email data
                    from_addr = decode_mime_words(msg.get("From", ""))
                    subject = decode_mime_words(msg.get("Subject", "No Subject"))
                    date_str = msg.get("Date", "")
                    
                    # Parse date
                    try:
                        date_tuple = email.utils.parsedate_to_datetime(date_str)
                        date_formatted = date_tuple.strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        date_formatted = date_str
                    
                    # Check if unread (use UID)
                    result, data = mail.uid('fetch', email_uid, '(FLAGS)')
                    # UID fetch returns: [(b'123 (UID 456 FLAGS (\\Seen))', b'')]
                    # We need to extract the FLAGS from the first element
                    flags_str = ""
                    if data and data[0]:
                        # data[0] is a tuple: (b'...', b'')
                        # We want the first element of that tuple
                        flags_response = data[0]
                        if isinstance(flags_response, tuple) and flags_response[0]:
                            flags_str = flags_response[0].decode('utf-8') if isinstance(flags_response[0], bytes) else str(flags_response[0])
                        elif isinstance(flags_response, bytes):
                            flags_str = flags_response.decode('utf-8')
                    is_unread = '\\Seen' not in flags_str
                    
                    # CRITICAL: Return UID as the primary ID (stable identifier)
                    uid_str = email_uid.decode() if isinstance(email_uid, bytes) else str(email_uid)
                    
                    email_info = {
                        "id": uid_str,  # UID - stable even when messages are added/deleted
                        "uid": uid_str,  # Explicit UID field for clarity
                        "from": from_addr,
                        "subject": subject,
                        "date": date_formatted,
                        "unread": is_unread,
                        "account": conn_mgr.email,
                        "account_id": conn_mgr.account_id  # Canonical account ID for routing
                    }
                    
                    emails.append(email_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to fetch email UID {email_uid}: {e}")
            
            return {
                "emails": emails,
                "total_in_folder": total_in_folder,
                "unread_count": unread_count,
                "folder": folder,
                "account": conn_mgr.email
            }
        
        finally:
            try:
                mail.logout()
            except Exception as e:
                logger.warning(f"Error closing IMAP connection: {e}")
        
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        return {"error": str(e)}

def fetch_emails_multi_account(limit=50, unread_only=False, folder="INBOX", use_cache=False):
    """Fetch emails from multiple accounts (now using parallel fetching)"""
    accounts = account_manager.list_accounts()
    
    if not accounts:
        return {
            'emails': [],
            'total_emails': 0,
            'total_unread': 0,
            'accounts_count': 0,
            'accounts_info': []
        }
    
    # Use parallel fetching for better performance
    try:
        from .operations.parallel_fetch import fetch_emails_parallel
        logger.info(f"Using parallel fetch for {len(accounts)} accounts")
        # Note: parallel_fetch may not support use_cache yet, will fallback if needed
        return fetch_emails_parallel(accounts, limit, unread_only, folder, use_cache)
    except (ImportError, TypeError) as e:
        # TypeError can occur if parallel_fetch doesn't accept use_cache parameter
        if isinstance(e, TypeError):
            logger.warning("Parallel fetch doesn't support use_cache, falling back to sequential")
        else:
            logger.warning("Parallel fetch not available, falling back to sequential")
        # Fallback to sequential if parallel not available
        return fetch_emails_multi_account_sequential(limit, unread_only, folder, use_cache)
    except Exception as e:
        logger.error(f"Parallel fetch failed: {e}, falling back to sequential")
        return fetch_emails_multi_account_sequential(limit, unread_only, folder, use_cache)

def fetch_emails_multi_account_sequential(limit=50, unread_only=False, folder="INBOX", use_cache=False):
    """Original sequential fetch (fallback)"""
    all_emails = []
    accounts_info = []
    total_emails = 0
    total_unread = 0
    
    accounts = account_manager.list_accounts()
    
    for account_info in accounts:
        try:
            account_id = account_info['id']
            # CRITICAL: Forward use_cache to per-account fetch
            result = fetch_emails(limit, unread_only, folder, account_id, use_cache)
            
            if "error" not in result:
                emails = result['emails']
                for email in emails:
                    email['account'] = account_info['email']
                
                all_emails.extend(emails)
                
                acc_info = {
                    'account': account_info['email'],
                    'total': result['total_in_folder'],
                    'unread': result['unread_count'],
                    'fetched': len(emails)
                }
                accounts_info.append(acc_info)
                
                total_emails += result['total_in_folder']
                total_unread += result['unread_count']
                
        except Exception as e:
            logger.warning(f"Failed to fetch from {account_info['email']}: {e}")
    
    # Sort by date
    all_emails.sort(key=lambda x: x['date'], reverse=True)
    
    # Limit total results
    all_emails = all_emails[:limit]
    
    return {
        'emails': all_emails,
        'total_emails': total_emails,
        'total_unread': total_unread,
        'accounts_count': len(accounts),
        'accounts_info': accounts_info
    }

def get_email_detail(email_id, folder="INBOX", account_id=None):
    """Get detailed email content"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        if result != 'OK':
            raise ValueError(f"Cannot select folder '{folder}': {data}")
        
        # Ensure email_id is a string
        if isinstance(email_id, int):
            email_id = str(email_id)
        
        # CRITICAL: Try UID first (stable), fallback to sequence number
        result, data = mail.uid('fetch', email_id, '(RFC822)')
        
        # Check if UID fetch failed or returned empty
        if result != 'OK' or not data or data[0] is None:
            logger.warning(f"UID fetch failed for {email_id}, trying sequence number")
            result, data = mail.fetch(email_id, '(RFC822)')
        
        # Validate data
        if result != 'OK':
            raise Exception(f"Failed to fetch email {email_id}: {result}")
        
        if not data or data[0] is None:
            raise Exception(f"Email {email_id} not found or has been deleted")
        
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email)
        
        # Extract headers
        from_addr = decode_mime_words(msg.get("From", ""))
        to_addr = decode_mime_words(msg.get("To", ""))
        cc_addr = decode_mime_words(msg.get("Cc", ""))
        subject = decode_mime_words(msg.get("Subject", "No Subject"))
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", "")
        
        # Parse date
        try:
            date_tuple = email.utils.parsedate_to_datetime(date_str)
            date_formatted = date_tuple.strftime("%Y-%m-%d %H:%M:%S")
        except:
            date_formatted = date_str
        
        # Extract body
        body = ""
        html_body = ""
        attachments = []
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        decoded_filename = decode_mime_words(filename)
                        attachments.append({
                            "filename": decoded_filename,
                            "size": len(part.get_payload(decode=True)),
                            "content_type": content_type
                        })
                
                elif content_type == "text/plain" and not body:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == "text/html" and not html_body:
                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        
        # Check if unread (try UID first, then sequence)
        result, data = mail.uid('fetch', email_id, '(FLAGS)')
        if result != 'OK' or not data or data[0] is None:
            result, data = mail.fetch(email_id, '(FLAGS)')
        
        # Parse FLAGS from response (handle tuple structure)
        flags_str = ""
        if data and data[0]:
            flags_response = data[0]
            if isinstance(flags_response, tuple) and flags_response[0]:
                flags_str = flags_response[0].decode('utf-8') if isinstance(flags_response[0], bytes) else str(flags_response[0])
            elif isinstance(flags_response, bytes):
                flags_str = flags_response.decode('utf-8')
        is_unread = '\\Seen' not in flags_str
        
        return {
            "id": email_id.decode() if isinstance(email_id, bytes) else email_id,
            "from": from_addr,
            "to": to_addr,
            "cc": cc_addr,
            "subject": subject,
            "date": date_formatted,
            "body": body or html_body,
            "html_body": html_body,
            "has_html": bool(html_body),
            "attachments": attachments,
            "attachment_count": len(attachments),
            "unread": is_unread,
            "message_id": message_id,
            "folder": folder,
            "account": conn_mgr.email,
            "account_id": conn_mgr.account_id  # Canonical account ID for consistent routing
        }
    
    except Exception as e:
        logger.error(f"Error getting email detail: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                mail.logout()
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in get_email_detail: {e}")

def mark_email_read(email_id, folder="INBOX", account_id=None):
    """Mark email as read"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        if result != 'OK':
            raise ValueError(f"Cannot select folder '{folder}': {data}")
        
        # Ensure email_id is a string
        if isinstance(email_id, int):
            email_id = str(email_id)
        
        flags_to_add = r'(\Seen)'
        # Try UID first, fallback to sequence number
        result, data = mail.uid('store', email_id, '+FLAGS', flags_to_add)
        if result != 'OK':
            logger.warning(f"UID store failed for {email_id}, trying sequence number")
            result, data = mail.store(email_id, '+FLAGS', flags_to_add)
        
        if result != 'OK':
            raise Exception(f"Failed to mark email {email_id} as read")
        
        return {"success": True, "message": "Email marked as read", "account": conn_mgr.email}
        
    except Exception as e:
        logger.error(f"Error marking email as read: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                mail.close()
                mail.logout()
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in mark_email_read: {e}")

def delete_email(email_id, folder="INBOX", account_id=None):
    """Delete email permanently"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        if result != 'OK':
            raise ValueError(f"Cannot select folder '{folder}': {data}")
        
        # Ensure email_id is a string
        if isinstance(email_id, int):
            email_id = str(email_id)
        
        deleted_flag = r'(\Deleted)'
        # Try UID first, fallback to sequence number
        result, data = mail.uid('store', email_id, '+FLAGS', deleted_flag)
        if result != 'OK':
            logger.warning(f"UID store failed for {email_id}, trying sequence number")
            result, data = mail.store(email_id, '+FLAGS', deleted_flag)
        
        if result != 'OK':
            raise Exception(f"Failed to delete email {email_id}")
        
        mail.expunge()
        
        return {"success": True, "message": "Email deleted", "account": conn_mgr.email}
        
    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                mail.close()
                mail.logout()
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in delete_email: {e}")

def move_email_to_trash(email_id, folder="INBOX", trash_folder="Trash", account_id=None):
    """Move email to trash folder"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        if result != 'OK':
            raise ValueError(f"Cannot select folder '{folder}': {data}")
        
        target_folder = _normalize_folder_name(trash_folder)

        # Ensure email_id is a string
        if isinstance(email_id, int):
            email_id = str(email_id)
        
        # Try UID copy first, fallback to sequence number
        result, data = mail.uid('copy', email_id, target_folder)
        if result != 'OK':
            logger.warning(f"UID copy failed for {email_id}, trying sequence number")
            result, data = mail.copy(email_id, target_folder)
        
        if result == 'OK':
            # Mark as deleted in original folder (use UID)
            deleted_flag = r'(\Deleted)'
            result, data = mail.uid('store', email_id, '+FLAGS', deleted_flag)
            if result != 'OK':
                mail.store(email_id, '+FLAGS', deleted_flag)
            mail.expunge()
            return {"success": True, "message": f"Email moved to {trash_folder}", "account": conn_mgr.email}
        else:
            # If trash folder doesn't exist, just delete
            # Use RFC-compliant flag format (same as successful COPY path)
            deleted_flag = r'(\Deleted)'
            result, data = mail.uid('store', email_id, '+FLAGS', deleted_flag)
            if result != 'OK':
                logger.warning(f"UID store failed for {email_id}, trying sequence number")
                result, data = mail.store(email_id, '+FLAGS', deleted_flag)
            
            # Check if deletion actually succeeded
            if result != 'OK':
                raise Exception(f"Failed to delete email {email_id} (trash folder not found, direct delete also failed)")
            
            mail.expunge()
            return {"success": True, "message": "Email deleted (no trash folder found)", "account": conn_mgr.email}
            
    except Exception as e:
        logger.error(f"Error moving email to trash: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                mail.close()
                mail.logout()
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in move_email_to_trash: {e}")

def batch_move_to_trash(email_ids, folder="INBOX", trash_folder="Trash", account_id=None):
    """Move multiple emails to trash"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        if result != 'OK':
            raise ValueError(f"Cannot select folder '{folder}': {data}")
        
        target_folder = _normalize_folder_name(trash_folder)

        # Check if trash folder exists using normalized name
        result, folders = mail.list()
        trash_exists = False
        if result == 'OK' and folders:
            # Compare normalized folder name against IMAP LIST response
            # IMAP returns: (b'(\\HasNoChildren) "/" "Trash"', ...)
            for folder_response in folders:
                try:
                    if isinstance(folder_response, bytes):
                        folder_str = folder_response.decode('utf-8', errors='ignore')
                        # Extract folder name from IMAP LIST response
                        # Format: (flags) "delimiter" "folder_name"
                        if '\"' in folder_str:
                            parts = folder_str.split('\"')
                            if len(parts) >= 4:
                                folder_name = parts[3]  # Fourth part is the folder name
                                # Normalize for comparison
                                normalized_response = _normalize_folder_name(folder_name)
                                if normalized_response == target_folder or folder_name == trash_folder:
                                    trash_exists = True
                                    break
                except:
                    continue
        
        moved_count = 0
        failed_ids = []
        
        if not trash_exists:
            # Just delete if no trash folder
            for email_id in email_ids:
                try:
                    # Ensure email_id is a string
                    if isinstance(email_id, int):
                        email_id = str(email_id)
                    # Try UID first
                    deleted_flag = r'(\Deleted)'
                    result, data = mail.uid('store', email_id, '+FLAGS', deleted_flag)
                    if result != 'OK':
                        result, data = mail.store(email_id, '+FLAGS', deleted_flag)
                    if result == 'OK':
                        moved_count += 1
                    else:
                        failed_ids.append(email_id)
                except:
                    failed_ids.append(email_id)
            
            mail.expunge()
            
            return {
                "success": True, 
                "message": f"Deleted {moved_count}/{len(email_ids)} emails (no trash folder)",
                "failed_ids": failed_ids,
                "account": conn_mgr.email
            }
        
        # Move to trash
        for email_id in email_ids:
            try:
                # Ensure email_id is a string
                if isinstance(email_id, int):
                    email_id = str(email_id)
                # Try UID copy first
                result, data = mail.uid('copy', email_id, target_folder)
                if result != 'OK':
                    result, data = mail.copy(email_id, target_folder)
                
                if result == 'OK':
                    deleted_flag = r'(\Deleted)'
                    # Mark as deleted (try UID first)
                    store_result, _ = mail.uid('store', email_id, '+FLAGS', deleted_flag)
                    if store_result != 'OK':
                        store_result, _ = mail.store(email_id, '+FLAGS', deleted_flag)
                    if store_result == 'OK':
                        moved_count += 1
                    else:
                        failed_ids.append(email_id)
                else:
                    failed_ids.append(email_id)
            except Exception as e:
                logger.warning(f"Failed to move email {email_id}: {e}")
                failed_ids.append(email_id)
        
        mail.expunge()
        
        result_data = {
            "success": True,
            "message": f"Moved {moved_count}/{len(email_ids)} emails to {trash_folder}",
            "account": conn_mgr.email
        }
        
        if failed_ids:
            result_data["failed_ids"] = failed_ids
        
        return result_data
        
    except Exception as e:
        logger.error(f"Error batch moving to trash: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                mail.close()
                mail.logout()
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in batch_move_to_trash: {e}")

def batch_delete_emails(email_ids, folder="INBOX", account_id=None, shared_connection=True):
    """
    Permanently delete multiple emails
    
    Args:
        email_ids: List of email IDs to delete
        folder: Folder name (default: INBOX)
        account_id: Account ID
        shared_connection: If True, use optimized single-connection version (default: True).
                          If False, delegate to delete_email for maximum reliability.
    
    The shared_connection=True mode reuses one IMAP session but still expunges after
    each delete, which is more reliable than batching all STOREs before expunging
    (especially for QQ mail), while being much faster than opening a new connection
    per email.
    """
    if not email_ids:
        return {"success": True, "message": "No emails to delete", "deleted_count": 0}
    
    # Optimized path: share connection but expunge each delete
    if shared_connection:
        return _batch_delete_emails_shared_connection(email_ids, folder, account_id)
    
    # Safe fallback: delegate to delete_email (multiple connections)
    
    deleted_count = 0
    failed_ids = []
    account_email = None
    
    # Delegate to delete_email for each ID
    for email_id in email_ids:
        try:
            result = delete_email(email_id, folder=folder, account_id=account_id)
            
            if 'error' in result:
                logger.warning(f"Failed to delete email {email_id}: {result['error']}")
                failed_ids.append(email_id)
            else:
                deleted_count += 1
                # Capture account info from first successful delete
                if account_email is None and 'account' in result:
                    account_email = result['account']
                    
        except Exception as e:
            logger.warning(f"Failed to delete email {email_id}: {e}")
            failed_ids.append(email_id)
    
    # Build result
    # Success only if ALL emails were deleted (no failures)
    all_succeeded = (len(failed_ids) == 0)
    
    result_data = {
        "success": all_succeeded,
        "deleted_count": deleted_count,
        "total_count": len(email_ids)
    }
    
    # Message depends on success/failure
    if all_succeeded:
        result_data["message"] = f"Successfully deleted all {deleted_count} email(s)"
    elif deleted_count == 0:
        result_data["message"] = f"Failed to delete all {len(email_ids)} email(s)"
    else:
        result_data["message"] = f"Partially deleted: {deleted_count}/{len(email_ids)} email(s) succeeded"
    
    if account_email:
        result_data["account"] = account_email
    
    if failed_ids:
        result_data["failed_ids"] = failed_ids
        result_data["failed_count"] = len(failed_ids)
    
    return result_data

def _batch_delete_emails_shared_connection(email_ids, folder="INBOX", account_id=None):
    """
    Optimized batch delete using a single shared IMAP connection.
    
    Still expunges after each delete (reliable for QQ mail), but reuses the connection
    to avoid the overhead of multiple connect/logout cycles.
    """
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        if result != 'OK':
            raise ValueError(f"Cannot select folder '{folder}': {data}")
        
        deleted_count = 0
        failed_ids = []
        
        for email_id in email_ids:
            try:
                # Ensure email_id is a string
                if isinstance(email_id, int):
                    email_id = str(email_id)
                
                # Use RFC-compliant flag format
                deleted_flag = r'(\Deleted)'
                
                # Try UID first, fallback to sequence number
                result, data = mail.uid('store', email_id, '+FLAGS', deleted_flag)
                if result != 'OK':
                    logger.warning(f"UID store failed for {email_id}, trying sequence number")
                    result, data = mail.store(email_id, '+FLAGS', deleted_flag)
                
                if result == 'OK':
                    # Expunge immediately after each successful STORE
                    # This is the key to QQ mail compatibility
                    mail.expunge()
                    deleted_count += 1
                else:
                    logger.warning(f"Failed to delete email {email_id}: store command failed with {result}")
                    failed_ids.append(email_id)
                    
            except Exception as e:
                logger.warning(f"Failed to delete email {email_id}: {e}")
                failed_ids.append(email_id)
        
        # Build result
        all_succeeded = (len(failed_ids) == 0)
        
        result_data = {
            "success": all_succeeded,
            "deleted_count": deleted_count,
            "total_count": len(email_ids),
            "account": conn_mgr.email
        }
        
        # Message depends on success/failure
        if all_succeeded:
            result_data["message"] = f"Successfully deleted all {deleted_count} email(s)"
        elif deleted_count == 0:
            result_data["message"] = f"Failed to delete all {len(email_ids)} email(s)"
        else:
            result_data["message"] = f"Partially deleted: {deleted_count}/{len(email_ids)} email(s) succeeded"
        
        if failed_ids:
            result_data["failed_ids"] = failed_ids
            result_data["failed_count"] = len(failed_ids)
        
        return result_data
        
    except Exception as e:
        logger.error(f"Error batch deleting emails: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                mail.close()
                mail.logout()
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in batch_delete_emails: {e}")

def batch_mark_read(email_ids, folder="INBOX", account_id=None):
    """Mark multiple emails as read"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        selected_folder = _normalize_folder_name(folder)
        result, data = mail.select(selected_folder)
        if result != 'OK':
            raise ValueError(f"Cannot select folder '{folder}': {data}")
        
        marked_count = 0
        failed_ids = []
        
        for email_id in email_ids:
            try:
                # Ensure email_id is a string
                if isinstance(email_id, int):
                    email_id = str(email_id)
                # Try UID first
                seen_flag = r'(\Seen)'
                result, data = mail.uid('store', email_id, '+FLAGS', seen_flag)
                if result != 'OK':
                    result, data = mail.store(email_id, '+FLAGS', seen_flag)
                if result == 'OK':
                    marked_count += 1
                else:
                    logger.warning(f"Failed to mark email {email_id} as read: store command failed with {result}")
                    failed_ids.append(email_id)
            except Exception as e:
                logger.warning(f"Failed to mark email {email_id} as read: {e}")
                failed_ids.append(email_id)
        
        result_data = {
            "success": True,
            "message": f"Marked {marked_count}/{len(email_ids)} emails as read",
            "account": conn_mgr.email
        }
        
        if failed_ids:
            result_data["failed_ids"] = failed_ids
        
        return result_data
        
    except Exception as e:
        logger.error(f"Error batch marking emails as read: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                mail.close()
                mail.logout()
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in batch_mark_read: {e}")
