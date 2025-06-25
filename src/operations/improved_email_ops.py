"""
Improved email operations that handle ID mapping correctly
"""
import logging
from typing import Dict, Any, Optional
import email
from email.utils import parsedate_to_datetime

from database.email_sync_db import EmailSyncDatabase
from connection_manager import ConnectionManager
from account_manager import AccountManager
from legacy_operations import decode_mime_words

logger = logging.getLogger(__name__)

def get_email_detail_by_db_id(db_id: str, account_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get email detail using database ID
    
    This function first looks up the email in the database to get the correct
    IMAP sequence number or UID, then fetches the full content from IMAP
    """
    try:
        # First, get email info from database
        db = EmailSyncDatabase(use_pool=False)
        
        # Query for the email
        sql = """
            SELECT e.*, f.name as folder_name, a.email as account_email
            FROM emails e
            JOIN folders f ON e.folder_id = f.id
            JOIN accounts a ON e.account_id = a.id
            WHERE e.id = ?
        """
        
        result = db.execute(sql, (db_id,), commit=False)
        email_row = result.fetchone()
        
        if not email_row:
            db.close()
            return {"error": f"Email with ID {db_id} not found in database"}
        
        # Extract info from database
        email_data = dict(email_row)
        folder_name = email_data['folder_name']
        account_id = email_data['account_id']
        uid = email_data['uid']
        
        db.close()
        
        # Now fetch full content from IMAP
        am = AccountManager()
        account = am.get_account(account_id)
        if not account:
            return {"error": f"Account {account_id} not found"}
        
        conn_mgr = ConnectionManager(account)
        mail = conn_mgr.connect_imap()
        
        # Select folder
        result, data = mail.select(folder_name)
        if result != 'OK':
            mail.logout()
            return {"error": f"Cannot select folder '{folder_name}': {data}"}
        
        # Search for the email by UID
        result, data = mail.search(None, f'UID {uid}')
        if result != 'OK' or not data[0]:
            # Fallback: try to find by message ID
            if email_data.get('message_id'):
                result, data = mail.search(None, f'HEADER Message-ID "{email_data["message_id"]}"')
            
            if result != 'OK' or not data[0]:
                mail.logout()
                # Return what we have from database
                return {
                    "id": db_id,
                    "subject": email_data.get('subject', 'No Subject'),
                    "from": email_data.get('sender', ''),
                    "to": email_data.get('recipients', ''),
                    "date": email_data.get('date_sent', ''),
                    "body": email_data.get('body', 'Email content not available from IMAP'),
                    "html_body": "",
                    "attachments": [],
                    "account": email_data.get('account_email', ''),
                    "folder": folder_name,
                    "source": "database_only"
                }
        
        # Get the sequence number
        sequence_nums = data[0].split()
        if not sequence_nums:
            mail.logout()
            return {"error": "Email not found in IMAP"}
        
        seq_num = sequence_nums[0]
        
        # Fetch the email
        result, data = mail.fetch(seq_num, '(RFC822)')
        if result != 'OK':
            mail.logout()
            return {"error": f"Failed to fetch email"}
        
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
            date_tuple = parsedate_to_datetime(date_str)
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
                            "content_type": content_type,
                            "size": len(part.get_payload())
                        })
                else:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            text = payload.decode(charset, errors='ignore')
                            
                            if content_type == "text/plain":
                                body += text
                            elif content_type == "text/html":
                                html_body += text
                    except Exception as e:
                        logger.warning(f"Failed to decode part: {e}")
        else:
            # Single part email
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    body = payload.decode(charset, errors='ignore')
            except Exception as e:
                logger.warning(f"Failed to decode body: {e}")
                body = "Failed to decode email body"
        
        mail.close()
        mail.logout()
        
        return {
            "id": db_id,
            "subject": subject,
            "from": from_addr,
            "to": to_addr,
            "cc": cc_addr,
            "date": date_formatted,
            "message_id": message_id,
            "body": body.strip(),
            "html_body": html_body.strip(),
            "attachments": attachments,
            "account": account.get('email'),
            "folder": folder_name
        }
        
    except Exception as e:
        logger.error(f"Error getting email detail: {e}")
        return {"error": str(e)}


def delete_emails_by_db_ids(db_ids: list, permanent: bool = False) -> Dict[str, Any]:
    """
    Delete emails using database IDs
    
    This function looks up emails in the database, groups them by account,
    then performs the delete operation via IMAP
    """
    try:
        db = EmailSyncDatabase(use_pool=False)
        
        # Get email info from database
        placeholders = ','.join('?' * len(db_ids))
        sql = f"""
            SELECT e.id, e.uid, e.account_id, e.message_id, f.name as folder_name
            FROM emails e
            JOIN folders f ON e.folder_id = f.id
            WHERE e.id IN ({placeholders})
        """
        
        results = db.execute(sql, tuple(db_ids), commit=False)
        found_rows = results.fetchall()
        
        # Check if any emails were found
        if not found_rows:
            db.close()
            return {
                'success': False,
                'error': f'None of the specified email IDs found in database: {", ".join(db_ids)}',
                'deleted_count': 0,
                'total': len(db_ids)
            }
        
        emails_by_account = {}
        
        # Group by account and folder
        for row in found_rows:
            account_id = row['account_id']
            folder = row['folder_name']
            key = (account_id, folder)
            
            if key not in emails_by_account:
                emails_by_account[key] = []
            
            emails_by_account[key].append({
                'db_id': row['id'],
                'uid': row['uid'],
                'message_id': row['message_id']
            })
        
        # Process each account/folder group
        am = AccountManager()
        total_deleted = 0
        errors = []
        
        for (account_id, folder), emails in emails_by_account.items():
            try:
                account = am.get_account(account_id)
                if not account:
                    errors.append(f"Account {account_id} not found")
                    continue
                
                conn_mgr = ConnectionManager(account)
                mail = conn_mgr.connect_imap()
                
                # Select folder
                result, data = mail.select(folder)
                if result != 'OK':
                    errors.append(f"Cannot select folder {folder} for {account_id}")
                    mail.logout()
                    continue
                
                # Delete each email
                for email_info in emails:
                    try:
                        # Try to find by UID first
                        result, data = mail.search(None, f'UID {email_info["uid"]}')
                        
                        if result != 'OK' or not data[0]:
                            # Try by message ID
                            if email_info['message_id']:
                                result, data = mail.search(None, f'HEADER Message-ID "{email_info["message_id"]}"')
                        
                        if result == 'OK' and data[0]:
                            seq_nums = data[0].split()
                            for seq_num in seq_nums:
                                mail.store(seq_num, '+FLAGS', '\\Deleted')
                                total_deleted += 1
                                
                                # Mark as deleted in database
                                db.execute(
                                    "UPDATE emails SET is_deleted = TRUE WHERE id = ?",
                                    (email_info['db_id'],)
                                )
                        else:
                            # Email not found in IMAP, just mark as deleted in DB
                            db.execute(
                                "UPDATE emails SET is_deleted = TRUE WHERE id = ?",
                                (email_info['db_id'],)
                            )
                            total_deleted += 1
                            
                    except Exception as e:
                        errors.append(f"Failed to delete email {email_info['db_id']}: {str(e)}")
                
                # Expunge if permanent delete
                if permanent:
                    mail.expunge()
                
                mail.close()
                mail.logout()
                
            except Exception as e:
                errors.append(f"Failed to process account {account_id}: {str(e)}")
        
        db.close()
        
        return {
            'success': total_deleted > 0,
            'deleted_count': total_deleted,
            'total': len(db_ids),
            'errors': errors if errors else None
        }
        
    except Exception as e:
        logger.error(f"Error deleting emails: {e}")
        return {
            'success': False,
            'error': str(e),
            'deleted_count': 0,
            'total': len(db_ids)
        }