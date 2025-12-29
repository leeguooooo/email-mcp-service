"""
Folder operations for email management
"""
import imaplib
import logging
import re
from typing import List, Dict, Any, Optional
from email.header import decode_header

logger = logging.getLogger(__name__)


def _logout_safely(mail):
    if not mail:
        return
    try:
        if getattr(mail, 'state', '').upper() == 'SELECTED':
            mail.close()
    except Exception:
        pass
    try:
        mail.logout()
    except Exception:
        pass


_IMAP_LIST_FLAGS_RE = re.compile(r"^\((?P<flags>[^)]*)\)")


def _parse_imap_list_response(folder_data: bytes) -> Dict[str, str]:
    """
    Parse an IMAP LIST response line.

    Example: b'(\\Sent) \"/\" \"&XfJT0ZAB-\"'
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


def _quote_mailbox(name: str) -> str:
    if not name:
        return name
    escaped = name.replace('"', '\\"')
    if escaped.startswith('"') and escaped.endswith('"'):
        return escaped
    return f'"{escaped}"'


class FolderOperations:
    """Handles folder-related operations"""
    
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
    
    def list_folders(self) -> Dict[str, Any]:
        """
        List all folders in the email account
        
        Returns:
            Dict containing folder list and hierarchy
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # List all folders
                result, folders = mail.list()
                
                if result != 'OK':
                    raise ValueError("Failed to list folders")
                
                folder_list = []
                folder_tree = {}
                
                for folder_data in folders:
                    parsed = _parse_imap_list_response(folder_data)
                    folder_name = parsed.get("name", "")
                    flags = parsed.get("flags", "")
                    delimiter = parsed.get("delimiter", "")

                    if not folder_name:
                        continue

                    # Get message count (best-effort)
                    try:
                        result, data = mail.select(_quote_mailbox(folder_name), readonly=True)
                        message_count = int(data[0]) if result == "OK" and data and data[0] else 0
                    except Exception:
                        message_count = 0

                    folder_info = {
                        "name": folder_name,
                        "attributes": flags,
                        "delimiter": delimiter,
                        "message_count": message_count,
                        "path": folder_name,
                    }

                    folder_list.append(folder_info)

                    # Build folder tree using delimiter (fallback to '.')
                    delim = delimiter or "."
                    self._add_to_tree(folder_tree, folder_name.split(delim), folder_info)
                
                return {
                    'success': True,
                    'folders': folder_list,
                    'folder_tree': folder_tree,
                    'total_folders': len(folder_list),
                    'account': self.connection_manager.email
                }
                
            finally:
                _logout_safely(mail)
                
        except Exception as e:
            logger.error(f"Failed to list folders: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def create_folder(self, folder_name: str, parent_folder: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new folder
        
        Args:
            folder_name: Name of the new folder
            parent_folder: Parent folder path (optional)
            
        Returns:
            Dict with success status
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Construct full folder path
                if parent_folder:
                    full_path = f"{parent_folder}.{folder_name}"
                else:
                    full_path = folder_name
                
                # Create folder
                result, data = mail.create(full_path)
                
                if result == 'OK':
                    logger.info(f"✅ Created folder: {full_path}")
                    return {
                        'success': True,
                        'message': f'Folder "{full_path}" created successfully',
                        'folder_path': full_path,
                        'account': self.connection_manager.email
                    }
                else:
                    raise ValueError(f"Failed to create folder: {data}")
                    
            finally:
                _logout_safely(mail)
                
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def delete_folder(self, folder_name: str) -> Dict[str, Any]:
        """
        Delete a folder
        
        Args:
            folder_name: Name of the folder to delete
            
        Returns:
            Dict with success status
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Delete folder
                result, data = mail.delete(folder_name)
                
                if result == 'OK':
                    logger.info(f"✅ Deleted folder: {folder_name}")
                    return {
                        'success': True,
                        'message': f'Folder "{folder_name}" deleted successfully',
                        'account': self.connection_manager.email
                    }
                else:
                    raise ValueError(f"Failed to delete folder: {data}")
                    
            finally:
                _logout_safely(mail)
                
        except Exception as e:
            logger.error(f"Failed to delete folder: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def rename_folder(self, old_name: str, new_name: str) -> Dict[str, Any]:
        """
        Rename a folder
        
        Args:
            old_name: Current folder name
            new_name: New folder name
            
        Returns:
            Dict with success status
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Rename folder
                result, data = mail.rename(old_name, new_name)
                
                if result == 'OK':
                    logger.info(f"✅ Renamed folder: {old_name} -> {new_name}")
                    return {
                        'success': True,
                        'message': f'Folder renamed from "{old_name}" to "{new_name}"',
                        'account': self.connection_manager.email
                    }
                else:
                    raise ValueError(f"Failed to rename folder: {data}")
                    
            finally:
                _logout_safely(mail)
                
        except Exception as e:
            logger.error(f"Failed to rename folder: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def move_emails_to_folder(
        self, 
        email_ids: List[str], 
        target_folder: str, 
        source_folder: str = "INBOX"
    ) -> Dict[str, Any]:
        """
        Move emails to a different folder
        
        Args:
            email_ids: List of email IDs to move
            target_folder: Target folder name
            source_folder: Source folder name (default: INBOX)
            
        Returns:
            Dict with success status and moved count
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Select source folder
                result, data = mail.select(source_folder)
                if result != 'OK':
                    raise ValueError(f"Cannot select source folder: {source_folder}")
                
                moved_count = 0
                failed_ids = []
                
                for email_id in email_ids:
                    try:
                        # Copy email to target folder
                        result, data = mail.copy(email_id, target_folder)
                        
                        if result == 'OK':
                            # Mark as deleted in source folder
                            result, data = mail.store(email_id, '+FLAGS', '\\Deleted')
                            if result == 'OK':
                                moved_count += 1
                            else:
                                failed_ids.append(email_id)
                        else:
                            failed_ids.append(email_id)
                            
                    except Exception as e:
                        logger.warning(f"Failed to move email {email_id}: {e}")
                        failed_ids.append(email_id)
                
                # Expunge to remove from source folder
                mail.expunge()
                
                result_data = {
                    'success': True,
                    'message': f'Moved {moved_count}/{len(email_ids)} emails to "{target_folder}"',
                    'moved_count': moved_count,
                    'source_folder': source_folder,
                    'target_folder': target_folder,
                    'account': self.connection_manager.email
                }
                
                if failed_ids:
                    result_data['failed_ids'] = failed_ids
                
                return result_data
                
            finally:
                _logout_safely(mail)
                
        except Exception as e:
            logger.error(f"Failed to move emails: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def empty_folder(self, folder_name: str) -> Dict[str, Any]:
        """
        Empty a folder (delete all emails in it)
        
        Args:
            folder_name: Name of the folder to empty
            
        Returns:
            Dict with success status and deleted count
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # Select folder
                result, data = mail.select(folder_name)
                if result != 'OK':
                    raise ValueError(f"Cannot select folder: {folder_name}")
                
                # Search for all messages
                result, data = mail.search(None, 'ALL')
                if result != 'OK':
                    raise ValueError("Failed to search emails")
                
                email_ids = data[0].split()
                if not email_ids:
                    return {
                        'success': True,
                        'message': f'Folder "{folder_name}" is already empty',
                        'deleted_count': 0,
                        'account': self.connection_manager.email
                    }
                
                # Mark all as deleted
                for email_id in email_ids:
                    mail.store(email_id, '+FLAGS', '\\Deleted')
                
                # Expunge to permanently delete
                mail.expunge()
                
                logger.info(f"✅ Emptied folder {folder_name}: deleted {len(email_ids)} emails")
                
                return {
                    'success': True,
                    'message': f'Emptied folder "{folder_name}": deleted {len(email_ids)} emails',
                    'deleted_count': len(email_ids),
                    'folder': folder_name,
                    'account': self.connection_manager.email
                }
                
            finally:
                _logout_safely(mail)
                
        except Exception as e:
            logger.error(f"Failed to empty folder: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def _add_to_tree(self, tree: Dict, path_parts: List[str], folder_info: Dict):
        """Helper to build folder tree structure"""
        if not path_parts:
            return
        
        current = path_parts[0]
        if current not in tree:
            tree[current] = {'info': None, 'children': {}}
        
        if len(path_parts) == 1:
            tree[current]['info'] = folder_info
        else:
            self._add_to_tree(tree[current]['children'], path_parts[1:], folder_info)
