"""
Enhanced email operations
"""
import imaplib
import logging
from typing import List, Dict, Any, Optional
from email import message_from_bytes
from email.header import decode_header
import os
import email

logger = logging.getLogger(__name__)

class EmailOperations:
    """Handles enhanced email operations"""
    
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
    
    def mark_email_unread(self, email_id: str, folder: str = "INBOX") -> Dict[str, Any]:
        """
        Mark an email as unread
        
        Args:
            email_id: Email ID to mark as unread
            folder: Email folder
            
        Returns:
            Dict with success status
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Select folder
                result, data = mail.select(folder)
                if result != 'OK':
                    raise ValueError(f"Cannot select folder: {folder}")
                
                # Remove \\Seen flag
                result, data = mail.store(email_id, '-FLAGS', '\\Seen')
                
                if result == 'OK':
                    logger.info(f"✅ Marked email {email_id} as unread")
                    return {
                        'success': True,
                        'message': f'Email marked as unread',
                        'email_id': email_id,
                        'folder': folder,
                        'account': self.connection_manager.email
                    }
                else:
                    raise ValueError(f"Failed to mark as unread: {data}")
                    
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Failed to mark email as unread: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def flag_email(
        self, 
        email_id: str, 
        flag_type: str = "flagged",  # flagged, important, answered
        folder: str = "INBOX",
        set_flag: bool = True
    ) -> Dict[str, Any]:
        """
        Flag or unflag an email
        
        Args:
            email_id: Email ID to flag
            flag_type: Type of flag (flagged/important/answered)
            folder: Email folder
            set_flag: True to set flag, False to remove
            
        Returns:
            Dict with success status
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Select folder
                result, data = mail.select(folder)
                if result != 'OK':
                    raise ValueError(f"Cannot select folder: {folder}")
                
                # Map flag types to IMAP flags
                flag_map = {
                    'flagged': '\\Flagged',
                    'important': '\\Flagged',  # Most providers use Flagged for important
                    'answered': '\\Answered'
                }
                
                imap_flag = flag_map.get(flag_type, '\\Flagged')
                operation = '+FLAGS' if set_flag else '-FLAGS'
                
                # Set or remove flag
                result, data = mail.store(email_id, operation, imap_flag)
                
                if result == 'OK':
                    action = "set" if set_flag else "removed"
                    logger.info(f"✅ Flag {flag_type} {action} for email {email_id}")
                    return {
                        'success': True,
                        'message': f'Flag "{flag_type}" {action}',
                        'email_id': email_id,
                        'flag_type': flag_type,
                        'set_flag': set_flag,
                        'folder': folder,
                        'account': self.connection_manager.email
                    }
                else:
                    raise ValueError(f"Failed to update flag: {data}")
                    
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Failed to flag email: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def get_email_attachments(
        self, 
        email_id: str, 
        save_path: Optional[str] = None,
        folder: str = "INBOX"
    ) -> Dict[str, Any]:
        """
        Get and optionally download email attachments
        
        Args:
            email_id: Email ID to get attachments from
            save_path: Directory to save attachments (optional)
            folder: Email folder
            
        Returns:
            Dict with attachment information
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Select folder
                result, data = mail.select(folder, readonly=True)
                if result != 'OK':
                    raise ValueError(f"Cannot select folder: {folder}")
                
                # Fetch email
                result, data = mail.fetch(email_id, '(RFC822)')
                if result != 'OK':
                    raise ValueError(f"Failed to fetch email {email_id}")
                
                # Parse email
                raw_email = data[0][1]
                msg = message_from_bytes(raw_email)
                
                attachments = []
                attachment_count = 0
                
                # Walk through email parts
                for part in msg.walk():
                    # Skip non-attachment parts
                    if part.get_content_disposition() is None:
                        continue
                    
                    if 'attachment' not in part.get_content_disposition():
                        continue
                    
                    # Get filename
                    filename = part.get_filename()
                    if not filename:
                        continue
                    
                    # Decode filename if needed
                    decoded_filename = decode_header(filename)
                    if decoded_filename:
                        filename = ""
                        for text, encoding in decoded_filename:
                            if isinstance(text, bytes):
                                filename += text.decode(encoding or 'utf-8', errors='ignore')
                            else:
                                filename += text
                    
                    # Get attachment data
                    attachment_data = part.get_payload(decode=True)
                    size = len(attachment_data)
                    
                    attachment_info = {
                        'filename': filename,
                        'size': size,
                        'size_formatted': self._format_size(size),
                        'content_type': part.get_content_type()
                    }
                    
                    # Save if path provided
                    if save_path and os.path.isdir(save_path):
                        filepath = os.path.join(save_path, filename)
                        
                        # Handle duplicate filenames
                        base, ext = os.path.splitext(filepath)
                        counter = 1
                        while os.path.exists(filepath):
                            filepath = f"{base}_{counter}{ext}"
                            counter += 1
                        
                        with open(filepath, 'wb') as f:
                            f.write(attachment_data)
                        
                        attachment_info['saved_path'] = filepath
                        logger.info(f"Saved attachment: {filepath}")
                    
                    attachments.append(attachment_info)
                    attachment_count += 1
                
                return {
                    'success': True,
                    'attachments': attachments,
                    'attachment_count': attachment_count,
                    'email_id': email_id,
                    'folder': folder,
                    'account': self.connection_manager.email
                }
                
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Failed to get attachments: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def batch_mark_unread(self, email_ids: List[str], folder: str = "INBOX") -> Dict[str, Any]:
        """
        Mark multiple emails as unread
        
        Args:
            email_ids: List of email IDs to mark as unread
            folder: Email folder
            
        Returns:
            Dict with success status and count
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Select folder
                result, data = mail.select(folder)
                if result != 'OK':
                    raise ValueError(f"Cannot select folder: {folder}")
                
                marked_count = 0
                failed_ids = []
                
                for email_id in email_ids:
                    try:
                        # Remove \\Seen flag
                        result, data = mail.store(email_id, '-FLAGS', '\\Seen')
                        if result == 'OK':
                            marked_count += 1
                        else:
                            failed_ids.append(email_id)
                    except Exception as e:
                        logger.warning(f"Failed to mark email {email_id} as unread: {e}")
                        failed_ids.append(email_id)
                
                result_data = {
                    'success': True,
                    'message': f'Marked {marked_count}/{len(email_ids)} emails as unread',
                    'marked_count': marked_count,
                    'folder': folder,
                    'account': self.connection_manager.email
                }
                
                if failed_ids:
                    result_data['failed_ids'] = failed_ids
                
                return result_data
                
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Failed to batch mark as unread: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def archive_emails(
        self, 
        email_ids: List[str], 
        archive_folder: str = "Archive",
        source_folder: str = "INBOX"
    ) -> Dict[str, Any]:
        """
        Archive emails to a specific folder
        
        Args:
            email_ids: List of email IDs to archive
            archive_folder: Archive folder name
            source_folder: Source folder
            
        Returns:
            Dict with success status
        """
        # Use folder operations to move emails
        from .folder_operations import FolderOperations
        folder_ops = FolderOperations(self.connection_manager)
        
        return folder_ops.move_emails_to_folder(
            email_ids=email_ids,
            target_folder=archive_folder,
            source_folder=source_folder
        )
    
    def _format_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"