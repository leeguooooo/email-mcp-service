"""
Legacy operations from original main.py
Preserved for backward compatibility
"""
import imaplib
import sqlite3
import email
from email.header import decode_header
import logging
import re
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json
from pathlib import Path
import os
from datetime import datetime

from .connection_manager import ConnectionManager
from .account_manager import AccountManager
from .operations.cached_operations import CachedEmailOperations

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
    """
    Decode MIME encoded words in headers with robust charset handling.
    
    Handles non-standard charsets like 'unknown-8bit' by falling back to latin-1.
    """
    if not s:
        return ""
    decoded = decode_header(s)
    result = ""
    for text, encoding in decoded:
        if isinstance(text, bytes):
            # Normalize and validate encoding
            if encoding:
                encoding_lower = encoding.lower()
                # Map known problematic encodings to safe alternatives
                if encoding_lower in ('unknown-8bit', 'x-unknown', '8bit', 'unknown'):
                    encoding = 'latin-1'  # Safe fallback that handles all byte values
            else:
                encoding = 'utf-8'  # Default for None
            
            try:
                result += text.decode(encoding, errors='ignore')
            except (LookupError, UnicodeDecodeError):
                # Final fallback for truly unknown codecs
                logger.debug(f"Unknown encoding '{encoding}', falling back to latin-1")
                result += text.decode('latin-1', errors='replace')
        else:
            result += text
    return result

def safe_parse_email(raw_email: bytes) -> email.message.Message:
    """
    安全地解析邮件，支持编码容错
    """
    try:
        return email.message_from_bytes(raw_email)
    except (LookupError, UnicodeDecodeError) as e:
        logger.warning(f"Email parsing failed with encoding error: {e}, using latin-1 fallback")
        try:
            text = raw_email.decode('latin-1', errors='replace')
            return email.message_from_string(text)
        except Exception as fallback_error:
            logger.error(f"Failed to parse email even with fallback: {fallback_error}")
            raise

# Parse raw email safely


def _close_mail_safely(mail):
    """Best-effort IMAP cleanup; tolerate AUTH state."""
    try:
        if mail is None:
            return
        state = getattr(mail, "state", None)
        if state == "SELECTED":
            try:
                mail.close()
            except Exception:
                pass
        mail.logout()
    except Exception as exc:
        logger.warning(f"Error closing IMAP connection: {exc}")
def _get_sync_db_path() -> Path:
    """Locate sync cache DB path (best-effort)."""
    try:
        from .config.paths import EMAIL_SYNC_DB
        return Path(EMAIL_SYNC_DB)
    except Exception:
        return Path("data/email_sync.db")


def _lookup_message_id_from_sync_db(account_id: str, uid: str, folder: Optional[str] = None):
    """Best-effort lookup of Message-ID from local sync DB by account/uid/folder."""
    db_path = _get_sync_db_path()
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(db_path)
        try:
            if folder:
                row = conn.execute(
                    """
                    SELECT e.message_id
                    FROM emails e
                    JOIN folders f ON e.folder_id = f.id
                    WHERE e.account_id = ?
                      AND e.uid = ?
                      AND f.name = ? COLLATE NOCASE
                    ORDER BY e.id DESC
                    LIMIT 1
                    """,
                    (account_id, str(uid), folder),
                ).fetchone()
                if row and row[0]:
                    return row[0]

            row = conn.execute(
                "SELECT message_id FROM emails WHERE account_id = ? AND uid = ? ORDER BY id DESC LIMIT 1",
                (account_id, str(uid)),
            ).fetchone()
            if row and row[0]:
                return row[0]
        finally:
            conn.close()
    except Exception:
        pass
    return None


def _mark_sync_cache_read(account_id: str, uid: str):
    """Best-effort mark local sync cache as read for given account/uid."""
    db_path = _get_sync_db_path()
    if not db_path.exists():
        return
    try:
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE emails SET is_read = 1, updated_at = CURRENT_TIMESTAMP WHERE account_id = ? AND uid = ?",
            (account_id, str(uid)),
        )
        conn.commit()
        conn.close()
    except Exception:
        return

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


_IMAP_LIST_FLAGS_RE = re.compile(r"^\\((?P<flags>[^)]*)\\)")


def _parse_imap_list_response(folder_data: bytes) -> Dict[str, str]:
    """
    Parse an IMAP LIST response line.

    Example: b'(\\\\Sent) \"/\" \"&XfJT0ZAB-\"'
    """
    try:
        line = folder_data.decode("utf-8", errors="ignore").strip()
    except Exception:
        line = str(folder_data)

    flags_match = _IMAP_LIST_FLAGS_RE.match(line)
    flags = flags_match.group("flags") if flags_match else ""

    quoted = re.findall(r"\"([^\"]*)\"", line)
    delimiter = quoted[-2] if len(quoted) >= 2 else ""
    name = quoted[-1] if quoted else line.split()[-1] if line.split() else ""

    return {"name": name, "flags": flags, "delimiter": delimiter}


def _find_uid_by_message_id_across_folders(
    mail: imaplib.IMAP4,
    msg_id: str,
    *,
    skip_folders: Optional[set[str]] = None,
    max_folders: int = 50,
) -> Optional[Dict[str, str]]:
    """
    Search all folders for a Message-ID and return the folder + resolved UID.

    Returns:
        {"folder": <folder_name>, "uid": <uid>} or None
    """
    skip = {f.lower() for f in (skip_folders or set()) if f}
    try:
        result, folders = mail.list()
    except Exception as exc:
        logger.warning(f"IMAP LIST failed during Message-ID fallback: {exc}")
        return None

    if result != "OK" or not folders:
        return None

    # Prefer INBOX early when present
    parsed: List[Dict[str, str]] = []
    for folder_data in folders:
        info = _parse_imap_list_response(folder_data)
        name = info.get("name") or ""
        if not name:
            continue
        flags = (info.get("flags") or "").lower()
        if "\\noselect" in flags:
            continue
        if name.lower() in skip:
            continue
        parsed.append({"name": name})

    # Keep deterministic order; INBOX first if present
    parsed.sort(key=lambda x: 0 if x["name"].lower() == "inbox" else 1)
    parsed = parsed[:max_folders]

    for entry in parsed:
        folder_name = entry["name"]
        try:
            sel_result, _ = mail.select(_normalize_folder_name(folder_name))
            if sel_result != "OK":
                continue
            search_result, search_data = mail.uid(
                "search", None, "HEADER", "Message-ID", msg_id
            )
            if search_result != "OK" or not search_data or not search_data[0]:
                continue
            uid_list = search_data[0].split()
            if not uid_list:
                continue
            alt_uid = uid_list[0]
            alt_uid_decoded = (
                alt_uid.decode() if isinstance(alt_uid, bytes) else str(alt_uid)
            )
            return {"folder": folder_name, "uid": alt_uid_decoded}
        except Exception as exc:
            logger.debug(
                "Message-ID search failed for folder %s: %s", folder_name, exc
            )
            continue

    return None

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
        # Resolve account_id only when it matches a configured account id/email.
        # IMPORTANT: do not implicitly fall back to the default account for unknown ids.
        resolved_account = None
        if account_id and account_manager.list_accounts():
            accounts = account_manager.accounts_data.get('accounts', {})
            if account_id in accounts:
                resolved_account = account_manager.get_account(account_id)
            elif '@' in str(account_id):
                for acc_id, acc_data in accounts.items():
                    if acc_data.get('email') == account_id:
                        resolved_account = account_manager.get_account(acc_id)
                        break
            if resolved_account:
                account_id = resolved_account.get('id', account_id)
        # If no specific account, fetch from all accounts
        # CRITICAL: Must check this BEFORE trying cache, because cache only works for single account
        if account_id is None and account_manager.list_accounts():
            return fetch_emails_multi_account(limit, unread_only, folder, use_cache)

        # Try cache first if requested (only for single account)
        if use_cache and account_id is not None:
            try:
                # Import inside function so tests can patch it reliably
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
                        logger.info(
                            "Cache hit: %s emails (age: %.1f min)",
                            len(result.get('emails', [])),
                            result.get('cache_age_minutes', 0) or 0.0,
                        )
                        return result
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
                # Log as debug instead of error to reduce noise
                logger.debug(f"Folder '{folder}' not available: {data}")
                return {
                    'emails': [],
                    'total_in_folder': 0,
                    'unread_count': 0,
                    'error': f"Folder '{folder}' not available"
                }
            
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
                    # CRITICAL: Use UID FETCH with headers only (much faster than full RFC822)
                    result, data = mail.uid('fetch', email_uid, '(RFC822.HEADER FLAGS)')
                    if result != 'OK' or not data or data[0] is None:
                        raise Exception(f"UID fetch failed for {email_uid}: {result}")
                    raw_headers = data[0][1] if isinstance(data[0], tuple) and len(data[0]) > 1 else b""
                    msg = safe_parse_email(raw_headers)
                    
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
                    
                    # Check if unread (FLAGS were included in the same FETCH)
                    flags_str = ""
                    if data and data[0]:
                        flags_response = data[0]
                        if isinstance(flags_response, tuple) and flags_response[0]:
                            flags_str = (
                                flags_response[0].decode("utf-8")
                                if isinstance(flags_response[0], bytes)
                                else str(flags_response[0])
                            )
                        elif isinstance(flags_response, bytes):
                            flags_str = flags_response.decode("utf-8", errors="ignore")
                    is_unread = '\\Seen' not in flags_str
                    
                    # CRITICAL: Return UID as the primary ID (stable identifier)
                    uid_str = email_uid.decode() if isinstance(email_uid, bytes) else str(email_uid)
                    message_id = msg.get("Message-ID", "")
                    
                    email_info = {
                        "id": uid_str,  # UID - stable even when messages are added/deleted
                        "uid": uid_str,  # Explicit UID field for clarity
                        "from": from_addr,
                        "subject": subject,
                        "date": date_formatted,
                        "unread": is_unread,
                        "message_id": message_id,
                        "folder": folder,
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
        # 优先使用指定文件夹，Gmail 账户若失败则回退到 [Gmail]/All Mail
        folders_to_try = [folder or "INBOX"]
        if conn_mgr.provider == "gmail":
            normalized = _normalize_folder_name(folder)
            if "All Mail" not in str(normalized):  # 避免重复添加
                folders_to_try.append("[Gmail]/All Mail")
        
        last_error = None
        selected_folder = None
        resolved_folder_name: Optional[str] = None
        for candidate in folders_to_try:
            selected_folder = _normalize_folder_name(candidate)
            result, data = mail.select(selected_folder)
            if result == 'OK':
                resolved_folder_name = candidate
                break
            last_error = f"Cannot select folder '{candidate}': {data}"
            selected_folder = None
        
        if not selected_folder:
            raise ValueError(last_error or f"Cannot select folder '{folder}'")
        
        # Ensure email_id is a string
        if isinstance(email_id, int):
            email_id = str(email_id)
        requested_email_id = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
        email_id = requested_email_id
        msg_id = _lookup_message_id_from_sync_db(
            conn_mgr.account_id,
            email_id,
            resolved_folder_name or folder or "INBOX",
        )
        
        # CRITICAL: Try UID first (stable), fallback to sequence number
        result, data = mail.uid('fetch', email_id, '(RFC822)')
        
        # Check if UID fetch failed or returned empty
        if result != 'OK' or not data or data[0] is None:
            # Try to resolve by Message-ID when possible (handles UIDVALIDITY changes)
            if msg_id:
                try:
                    search_result, search_data = mail.uid(
                        "search", None, "HEADER", "Message-ID", str(msg_id)
                    )
                    if search_result == "OK" and search_data and search_data[0]:
                        uid_list = search_data[0].split()
                        if uid_list:
                            alt_uid = uid_list[0]
                            alt_uid_decoded = (
                                alt_uid.decode()
                                if isinstance(alt_uid, bytes)
                                else str(alt_uid)
                            )
                            alt_result, alt_data = mail.uid(
                                "fetch", alt_uid_decoded, "(RFC822)"
                            )
                            if (
                                alt_result == "OK"
                                and alt_data
                                and alt_data[0] is not None
                            ):
                                logger.info(
                                    "Resolved email UID via Message-ID search: requested=%s resolved=%s",
                                    requested_email_id,
                                    alt_uid_decoded,
                                )
                                email_id = alt_uid_decoded
                                result, data = alt_result, alt_data
                except Exception as search_exc:
                    logger.warning(f"Message-ID search failed: {search_exc}")

            # Cross-folder fallback (providers like 163 use special-use folders that don't map to INBOX)
            if (
                msg_id
                and (result != "OK" or not data or data[0] is None)
                and conn_mgr.provider != "gmail"
            ):
                try:
                    found = _find_uid_by_message_id_across_folders(
                        mail,
                        str(msg_id),
                        skip_folders={resolved_folder_name or folder or "INBOX"},
                    )
                    if found:
                        found_folder = found["folder"]
                        found_uid = found["uid"]
                        logger.info(
                            "Resolved via cross-folder Message-ID search: requested=%s resolved=%s folder=%s",
                            requested_email_id,
                            found_uid,
                            found_folder,
                        )
                        resolved_folder_name = found_folder
                        email_id = found_uid
                        alt_result, alt_data = mail.uid("fetch", found_uid, "(RFC822)")
                        if (
                            alt_result == "OK"
                            and alt_data
                            and alt_data[0] is not None
                        ):
                            result, data = alt_result, alt_data
                except Exception as search_exc:
                    logger.warning(f"Cross-folder Message-ID search failed: {search_exc}")

            # Fallback to sequence number only if still missing after Message-ID resolution
            if result != 'OK' or not data or data[0] is None:
                logger.warning(f"UID fetch failed for {email_id}, trying sequence number")
                result, data = mail.fetch(email_id, '(RFC822)')
        
        # Validate data
        if result != 'OK':
            raise Exception(f"Failed to fetch email {email_id}: {result}")
        
        if not data or data[0] is None:
            raise Exception(f"Email {email_id} not found or has been deleted")
        
        raw_email = data[0][1]
        msg = safe_parse_email(raw_email)
        
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
            "requested_id": requested_email_id,
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
            "folder": resolved_folder_name or folder,
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
        # 优先使用指定文件夹，Gmail 账户若失败则回退到 [Gmail]/All Mail
        folders_to_try = [folder or "INBOX"]
        if conn_mgr.provider == "gmail":
            normalized = _normalize_folder_name(folder)
            if "All Mail" not in str(normalized):  # 避免重复添加
                folders_to_try.append("[Gmail]/All Mail")
        
        last_error = None
        selected_folder = None
        resolved_folder_name: Optional[str] = None
        for candidate in folders_to_try:
            selected_folder = _normalize_folder_name(candidate)
            result, data = mail.select(selected_folder)
            if result == 'OK':
                resolved_folder_name = candidate
                break
            last_error = f"Cannot select folder '{candidate}': {data}"
            selected_folder = None
        
        if not selected_folder:
            raise ValueError(last_error or f"Cannot select folder '{folder}'")
        
        # Ensure email_id is a string
        if isinstance(email_id, int):
            email_id = str(email_id)
        
        flags_to_add = r"(\Seen)"
        success = False
        resolved_uid = str(email_id)
        msg_id = _lookup_message_id_from_sync_db(
            conn_mgr.account_id,
            email_id,
            resolved_folder_name or folder or "INBOX",
        )

        def _extract_flags_str(fetch_data) -> str:
            if not fetch_data or not fetch_data[0]:
                return ""
            flags_response = fetch_data[0]
            if isinstance(flags_response, tuple) and flags_response[0]:
                return (
                    flags_response[0].decode("utf-8")
                    if isinstance(flags_response[0], bytes)
                    else str(flags_response[0])
                )
            if isinstance(flags_response, bytes):
                return flags_response.decode("utf-8", errors="ignore")
            return str(flags_response)

        def _verify_seen(uid_or_seq: str, *, use_uid: bool) -> bool:
            try:
                if use_uid:
                    r, d = mail.uid("fetch", uid_or_seq, "(FLAGS)")
                else:
                    r, d = mail.fetch(uid_or_seq, "(FLAGS)")
                if r != "OK" or not d or d[0] is None:
                    return False
                return "\\Seen" in _extract_flags_str(d)
            except Exception:
                return False

        # 1) Try UID store first, then verify via UID FETCH FLAGS.
        result, _data = mail.uid("store", email_id, "+FLAGS", flags_to_add)
        if result == "OK" and _verify_seen(str(email_id), use_uid=True):
            success = True
            resolved_uid = str(email_id)

        # 2) UID 可能因 UIDVALIDITY 变化/同步延迟而不匹配，基于 Message-ID 再搜一遍（当前文件夹）
        if not success and msg_id:
            try:
                search_result, search_data = mail.uid(
                    "search", None, "HEADER", "Message-ID", str(msg_id)
                )
                if search_result == "OK" and search_data and search_data[0]:
                    uid_list = search_data[0].split()
                    for alt_uid in uid_list:
                        alt_uid_decoded = (
                            alt_uid.decode()
                            if isinstance(alt_uid, bytes)
                            else str(alt_uid)
                        )
                        result, _data = mail.uid(
                            "store", alt_uid_decoded, "+FLAGS", flags_to_add
                        )
                        if result == "OK" and _verify_seen(
                            alt_uid_decoded, use_uid=True
                        ):
                            logger.info(
                                "Marked via Message-ID search UID=%s",
                                alt_uid_decoded,
                            )
                            success = True
                            resolved_uid = alt_uid_decoded
                            break
            except Exception as search_exc:
                logger.warning(f"Message-ID search failed: {search_exc}")

        # 3) Cross-folder fallback (e.g. 163 special-use folders)
        if (
            not success
            and msg_id
            and conn_mgr.provider != "gmail"
        ):
            try:
                found = _find_uid_by_message_id_across_folders(
                    mail,
                    str(msg_id),
                    skip_folders={resolved_folder_name or folder or "INBOX"},
                )
                if found:
                    found_folder = found["folder"]
                    found_uid = found["uid"]
                    mail.select(_normalize_folder_name(found_folder))
                    result, _data = mail.uid(
                        "store", found_uid, "+FLAGS", flags_to_add
                    )
                    if result == "OK" and _verify_seen(found_uid, use_uid=True):
                        logger.info(
                            "Marked via cross-folder Message-ID search UID=%s folder=%s",
                            found_uid,
                            found_folder,
                        )
                        success = True
                        resolved_uid = found_uid
                        resolved_folder_name = found_folder
            except Exception as search_exc:
                logger.warning(f"Cross-folder Message-ID search failed: {search_exc}")

        # 4) Final fallback to sequence-number STORE (legacy servers)
        if not success:
            logger.warning(f"UID store failed for {email_id}, trying sequence number")
            result, _data = mail.store(email_id, "+FLAGS", flags_to_add)
            success = result == "OK" and _verify_seen(str(email_id), use_uid=False)
        
        if not success:
            raise Exception(f"Failed to mark email {email_id} as read")
        
        # Best-effort update local sync cache
        _mark_sync_cache_read(conn_mgr.account_id, resolved_uid)
        
        return {"success": True, "message": "Email marked as read", "account": conn_mgr.email}
        
    except Exception as e:
        logger.error(f"Error marking email as read: {e}")
        return {"error": str(e)}
    
    finally:
        try:
            if 'mail' in locals():
                _close_mail_safely(mail)
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in mark_email_read: {e}")

def delete_email(email_id, folder="INBOX", account_id=None):
    """Delete email permanently"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        # 优先使用指定文件夹，Gmail 账户若失败则回退到 [Gmail]/All Mail
        folders_to_try = [folder or "INBOX"]
        if conn_mgr.provider == "gmail":
            normalized = _normalize_folder_name(folder)
            if "All Mail" not in str(normalized):  # 避免重复添加
                folders_to_try.append("[Gmail]/All Mail")
        
        last_error = None
        selected_folder = None
        for candidate in folders_to_try:
            selected_folder = _normalize_folder_name(candidate)
            result, data = mail.select(selected_folder)
            if result == 'OK':
                break
            last_error = f"Cannot select folder '{candidate}': {data}"
            selected_folder = None
        
        if not selected_folder:
            raise ValueError(last_error or f"Cannot select folder '{folder}'")
        
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
                _close_mail_safely(mail)
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in delete_email: {e}")

def move_email_to_trash(email_id, folder="INBOX", trash_folder="Trash", account_id=None):
    """Move email to trash folder"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        # 优先使用指定文件夹，Gmail 账户若失败则回退到 [Gmail]/All Mail
        folders_to_try = [folder or "INBOX"]
        if conn_mgr.provider == "gmail":
            normalized = _normalize_folder_name(folder)
            if "All Mail" not in str(normalized):  # 避免重复添加
                folders_to_try.append("[Gmail]/All Mail")
        
        last_error = None
        selected_folder = None
        for candidate in folders_to_try:
            selected_folder = _normalize_folder_name(candidate)
            result, data = mail.select(selected_folder)
            if result == 'OK':
                break
            last_error = f"Cannot select folder '{candidate}': {data}"
            selected_folder = None
        
        if not selected_folder:
            raise ValueError(last_error or f"Cannot select folder '{folder}'")
        
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
                _close_mail_safely(mail)
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in move_email_to_trash: {e}")

def batch_move_to_trash(email_ids, folder="INBOX", trash_folder="Trash", account_id=None):
    """Move multiple emails to trash"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        # 优先使用指定文件夹，Gmail 账户若失败则回退到 [Gmail]/All Mail
        folders_to_try = [folder or "INBOX"]
        if conn_mgr.provider == "gmail":
            normalized = _normalize_folder_name(folder)
            if "All Mail" not in str(normalized):  # 避免重复添加
                folders_to_try.append("[Gmail]/All Mail")
        
        last_error = None
        selected_folder = None
        for candidate in folders_to_try:
            selected_folder = _normalize_folder_name(candidate)
            result, data = mail.select(selected_folder)
            if result == 'OK':
                break
            last_error = f"Cannot select folder '{candidate}': {data}"
            selected_folder = None
        
        if not selected_folder:
            raise ValueError(last_error or f"Cannot select folder '{folder}'")
        
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
                _close_mail_safely(mail)
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
        
        # 优先使用指定文件夹，Gmail 账户若失败则回退到 [Gmail]/All Mail
        folders_to_try = [folder or "INBOX"]
        if conn_mgr.provider == "gmail":
            normalized = _normalize_folder_name(folder)
            if "All Mail" not in str(normalized):  # 避免重复添加
                folders_to_try.append("[Gmail]/All Mail")
        
        last_error = None
        selected_folder = None
        for candidate in folders_to_try:
            selected_folder = _normalize_folder_name(candidate)
            result, data = mail.select(selected_folder)
            if result == 'OK':
                break
            last_error = f"Cannot select folder '{candidate}': {data}"
            selected_folder = None
        
        if not selected_folder:
            raise ValueError(last_error or f"Cannot select folder '{folder}'")
        
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
                _close_mail_safely(mail)
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in batch_delete_emails: {e}")

def batch_mark_read(email_ids, folder="INBOX", account_id=None):
    """Mark multiple emails as read"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        # 优先使用指定文件夹，Gmail 账户若失败则回退到 [Gmail]/All Mail
        folders_to_try = [folder or "INBOX"]
        if conn_mgr.provider == "gmail":
            normalized = _normalize_folder_name(folder)
            if "All Mail" not in str(normalized):  # 避免重复添加
                folders_to_try.append("[Gmail]/All Mail")
        
        last_error = None
        selected_folder = None
        for candidate in folders_to_try:
            selected_folder = _normalize_folder_name(candidate)
            result, data = mail.select(selected_folder)
            if result == 'OK':
                break
            last_error = f"Cannot select folder '{candidate}': {data}"
            selected_folder = None
        
        if not selected_folder:
            raise ValueError(last_error or f"Cannot select folder '{folder}'")
        
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
                _close_mail_safely(mail)
        except Exception as e:
            logger.warning(f"Error closing IMAP connection in batch_mark_read: {e}")
