"""
Legacy operations from original main.py
Preserved for backward compatibility
"""
import imaplib
import email
from email.header import decode_header
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
from pathlib import Path
import os

from connection_manager import ConnectionManager
from account_manager import AccountManager

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

def get_mailbox_status(folder="INBOX", account_id=None):
    """Get mailbox status"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        # Select the folder
        result, data = mail.select(folder)
        
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

def fetch_emails(limit=50, unread_only=False, folder="INBOX", account_id=None):
    """Fetch emails from account"""
    try:
        # If no specific account, fetch from all accounts
        if account_id is None and account_manager.list_accounts():
            return fetch_emails_multi_account(limit, unread_only, folder)
        
        # Single account fetch
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        mail.select(folder)
        
        # Search criteria
        if unread_only:
            result, data = mail.search(None, 'UNSEEN')
        else:
            result, data = mail.search(None, 'ALL')
        
        email_ids = data[0].split()
        total_in_folder = len(email_ids)
        
        # Get unread count
        result, data = mail.search(None, 'UNSEEN')
        unread_count = len(data[0].split()) if data[0] else 0
        
        # Limit emails
        email_ids = email_ids[-limit:]
        email_ids.reverse()
        
        emails = []
        for email_id in email_ids:
            try:
                result, data = mail.fetch(email_id, '(RFC822)')
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
                
                # Check if unread
                result, data = mail.fetch(email_id, '(FLAGS)')
                flags = data[0].decode('utf-8') if data[0] else ""
                is_unread = '\\Seen' not in flags
                
                email_info = {
                    "id": email_id.decode() if isinstance(email_id, bytes) else email_id,
                    "from": from_addr,
                    "subject": subject,
                    "date": date_formatted,
                    "unread": is_unread,
                    "account": conn_mgr.email
                }
                
                emails.append(email_info)
                
            except Exception as e:
                logger.warning(f"Failed to fetch email {email_id}: {e}")
        
        mail.logout()
        
        return {
            "emails": emails,
            "total_in_folder": total_in_folder,
            "unread_count": unread_count,
            "folder": folder,
            "account": conn_mgr.email
        }
        
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        return {"error": str(e)}

def fetch_emails_multi_account(limit=50, unread_only=False, folder="INBOX"):
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
        return fetch_emails_parallel(accounts, limit, unread_only, folder)
    except ImportError:
        logger.warning("Parallel fetch not available, falling back to sequential")
        # Fallback to sequential if parallel not available
        return fetch_emails_multi_account_sequential(limit, unread_only, folder)
    except Exception as e:
        logger.error(f"Parallel fetch failed: {e}, falling back to sequential")
        return fetch_emails_multi_account_sequential(limit, unread_only, folder)

def fetch_emails_multi_account_sequential(limit=50, unread_only=False, folder="INBOX"):
    """Original sequential fetch (fallback)"""
    all_emails = []
    accounts_info = []
    total_emails = 0
    total_unread = 0
    
    accounts = account_manager.list_accounts()
    
    for account_info in accounts:
        try:
            account_id = account_info['id']
            result = fetch_emails(limit, unread_only, folder, account_id)
            
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
        
        mail.select(folder)
        
        # Ensure email_id is a string
        if isinstance(email_id, int):
            email_id = str(email_id)
        
        result, data = mail.fetch(email_id, '(RFC822)')
        if result != 'OK':
            raise Exception(f"Failed to fetch email {email_id}")
        
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
        
        # Check if unread
        result, data = mail.fetch(email_id, '(FLAGS)')
        flags = data[0].decode('utf-8') if data[0] else ""
        is_unread = '\\Seen' not in flags
        
        mail.logout()
        
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
            "account": conn_mgr.email
        }
        
    except Exception as e:
        logger.error(f"Error getting email detail: {e}")
        return {"error": str(e)}

def mark_email_read(email_id, folder="INBOX", account_id=None):
    """Mark email as read"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        mail.select(folder)
        mail.store(email_id, '+FLAGS', '\\Seen')
        mail.close()
        mail.logout()
        
        return {"success": True, "message": "Email marked as read", "account": conn_mgr.email}
        
    except Exception as e:
        logger.error(f"Error marking email as read: {e}")
        return {"error": str(e)}

def delete_email(email_id, folder="INBOX", account_id=None):
    """Delete email permanently"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        mail.select(folder)
        mail.store(email_id, '+FLAGS', '\\Deleted')
        mail.expunge()
        mail.close()
        mail.logout()
        
        return {"success": True, "message": "Email deleted", "account": conn_mgr.email}
        
    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        return {"error": str(e)}

def move_email_to_trash(email_id, folder="INBOX", trash_folder="Trash", account_id=None):
    """Move email to trash folder"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        mail.select(folder)
        
        # Try to copy to trash folder
        result, data = mail.copy(email_id, trash_folder)
        
        if result == 'OK':
            # Mark as deleted in original folder
            mail.store(email_id, '+FLAGS', '\\Deleted')
            mail.expunge()
            mail.close()
            mail.logout()
            return {"success": True, "message": f"Email moved to {trash_folder}", "account": conn_mgr.email}
        else:
            # If trash folder doesn't exist, just delete
            mail.store(email_id, '+FLAGS', '\\Deleted')
            mail.expunge()
            mail.close()
            mail.logout()
            return {"success": True, "message": "Email deleted (no trash folder found)", "account": conn_mgr.email}
            
    except Exception as e:
        logger.error(f"Error moving email to trash: {e}")
        return {"error": str(e)}

def batch_move_to_trash(email_ids, folder="INBOX", trash_folder="Trash", account_id=None):
    """Move multiple emails to trash"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        mail.select(folder)
        
        # Check if trash folder exists
        result, folders = mail.list()
        trash_exists = any(trash_folder in folder.decode() for folder in folders)
        
        moved_count = 0
        failed_ids = []
        
        if not trash_exists:
            # Just delete if no trash folder
            for email_id in email_ids:
                try:
                    mail.store(email_id, '+FLAGS', '\\Deleted')
                    moved_count += 1
                except:
                    failed_ids.append(email_id)
            
            mail.expunge()
            mail.close()
            mail.logout()
            
            return {
                "success": True, 
                "message": f"Deleted {moved_count}/{len(email_ids)} emails (no trash folder)",
                "failed_ids": failed_ids,
                "account": conn_mgr.email
            }
        
        # Move to trash
        for email_id in email_ids:
            try:
                result, data = mail.copy(email_id, trash_folder)
                if result == 'OK':
                    mail.store(email_id, '+FLAGS', '\\Deleted')
                    moved_count += 1
                else:
                    failed_ids.append(email_id)
            except Exception as e:
                logger.warning(f"Failed to move email {email_id}: {e}")
                failed_ids.append(email_id)
        
        mail.expunge()
        mail.close()
        mail.logout()
        
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

def batch_delete_emails(email_ids, folder="INBOX", account_id=None):
    """Permanently delete multiple emails"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        mail.select(folder)
        
        deleted_count = 0
        failed_ids = []
        
        for email_id in email_ids:
            try:
                mail.store(email_id, '+FLAGS', '\\Deleted')
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete email {email_id}: {e}")
                failed_ids.append(email_id)
        
        mail.expunge()
        mail.close()
        mail.logout()
        
        result_data = {
            "success": True,
            "message": f"Deleted {deleted_count}/{len(email_ids)} emails",
            "account": conn_mgr.email
        }
        
        if failed_ids:
            result_data["failed_ids"] = failed_ids
        
        return result_data
        
    except Exception as e:
        logger.error(f"Error batch deleting emails: {e}")
        return {"error": str(e)}

def batch_mark_read(email_ids, folder="INBOX", account_id=None):
    """Mark multiple emails as read"""
    try:
        conn_mgr = get_connection_manager(account_id)
        mail = conn_mgr.connect_imap()
        
        mail.select(folder)
        
        marked_count = 0
        failed_ids = []
        
        for email_id in email_ids:
            try:
                mail.store(email_id, '+FLAGS', '\\Seen')
                marked_count += 1
            except Exception as e:
                logger.warning(f"Failed to mark email {email_id} as read: {e}")
                failed_ids.append(email_id)
        
        mail.close()
        mail.logout()
        
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