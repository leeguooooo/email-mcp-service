"""
Folder service layer - Clean interface for folder/organization operations
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class FolderService:
    """Service layer for folder and organization operations"""
    
    def __init__(self, account_manager):
        """
        Initialize folder service
        
        Args:
            account_manager: AccountManager instance
        """
        self.account_manager = account_manager
    
    def _ensure_success_field(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure result has 'success' field for consistency
        
        Args:
            result: Operation result dictionary
            
        Returns:
            Result with guaranteed 'success' field
        """
        if 'success' not in result:
            result['success'] = 'error' not in result
        return result
    
    def list_folders(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List all email folders/labels
        
        Args:
            account_id: List folders for specific account
            
        Returns:
            Dictionary containing folders list with 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.folder_operations import FolderOperations
            
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            folder_ops = FolderOperations(conn_mgr)
            
            result = folder_ops.list_folders()
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"List folders failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def move_emails_to_folder(
        self,
        email_ids: List[str],
        target_folder: str,
        source_folder: str = 'INBOX',
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Move emails to a different folder
        
        Args:
            email_ids: Email IDs to move
            target_folder: Target folder name
            source_folder: Source folder
            account_id: Specific account ID
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.folder_operations import FolderOperations
            
            # Get account once for efficiency
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            folder_ops = FolderOperations(conn_mgr)
            
            def sequential_move(ids: List[str], src_fld: str, tgt_fld: str, **kwargs) -> Dict[str, Any]:
                """Sequential fallback for moving emails"""
                results = []
                for email_id in ids:
                    res = folder_ops.move_email(email_id, src_fld, tgt_fld)
                    results.append(res)
                
                success_count = sum(1 for r in results if r.get('success'))
                return {
                    'success': success_count == len(results),
                    'moved_count': success_count,
                    'total': len(results)
                }
            
            # Single email - direct execution
            if len(email_ids) == 1:
                result = folder_ops.move_email(email_ids[0], source_folder, target_folder)
                return self._ensure_success_field(result)
            
            # Multiple emails - try parallel, fallback to sequential
            try:
                from ..operations.parallel_operations import parallel_ops, batch_ops
                result = parallel_ops.execute_batch_operation(
                    batch_ops.batch_move_emails,
                    email_ids,
                    source_folder,
                    account_id,
                    target_folder=target_folder
                )
                return self._ensure_success_field(result)
            except ImportError:
                logger.debug("Parallel operations not available, using sequential fallback")
                return sequential_move(email_ids, source_folder, target_folder)
                
        except Exception as e:
            logger.error(f"Move emails to folder failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def flag_email(
        self,
        email_id: str,
        flag_type: str,
        set_flag: bool = True,
        folder: str = 'INBOX',
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Flag/star or unflag an email
        
        Args:
            email_id: Email ID to flag/unflag
            flag_type: Flag category (flagged, important, answered)
            set_flag: Set to true to add the flag or false to remove it
            folder: Email folder
            account_id: Specific account ID
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.email_operations import EmailOperations
            
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            email_ops = EmailOperations(conn_mgr)
            
            result = email_ops.flag_email(email_id, folder, flag_type, set_flag)
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"Flag email failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def get_email_attachments(
        self,
        email_id: str,
        folder: str = 'INBOX',
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract attachments from an email
        
        Args:
            email_id: Email ID to get attachments from
            folder: Email folder
            account_id: Specific account ID
            
        Returns:
            Dictionary containing attachments list with 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.email_operations import EmailOperations
            
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            email_ops = EmailOperations(conn_mgr)
            
            result = email_ops.get_email_attachments(email_id, folder)
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"Get email attachments failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def list_folders_with_unread_count(
        self,
        account_id: Optional[str] = None,
        include_empty: bool = True
    ) -> Dict[str, Any]:
        """
        List all folders with unread email counts (atomic operation)
        
        Args:
            account_id: Get counts for specific account (optional)
            include_empty: Include folders with zero unread emails
            
        Returns:
            Dictionary containing folders with unread/total counts
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.folder_operations import FolderOperations
            
            accounts = [account_id] if account_id else None
            if not accounts:
                accounts = [acc['id'] for acc in self.account_manager.list_accounts()]
            
            all_folders = []
            
            for acc_id in accounts:
                account = self.account_manager.get_account(acc_id)
                if not account:
                    continue
                
                conn_mgr = ConnectionManager(account)
                folder_ops = FolderOperations(conn_mgr)
                
                # Get folder list
                folders_result = folder_ops.list_folders()
                if 'error' in folders_result:
                    logger.warning(f"Failed to list folders for {acc_id}: {folders_result['error']}")
                    continue
                
                # Connect once for all folders
                mail = None
                try:
                    mail = conn_mgr.connect_imap()
                    
                    # Get unread count for each folder
                    for folder_info in folders_result.get('folders', []):
                        folder_name = folder_info['name']  # Extract name from dict
                        try:
                            mail.select(folder_name, readonly=True)
                            
                            # Get UNSEEN count
                            _, unseen_data = mail.search(None, 'UNSEEN')
                            unseen_count = len(unseen_data[0].split()) if unseen_data[0] else 0
                            
                            # Get total count
                            _, total_data = mail.search(None, 'ALL')
                            total_count = len(total_data[0].split()) if total_data[0] else 0
                            
                            if include_empty or unseen_count > 0:
                                all_folders.append({
                                    'name': folder_name,
                                    'unread_count': unseen_count,
                                    'total_count': total_count,
                                    'account': account.get('email', acc_id),
                                    'account_id': acc_id
                                })
                        except Exception as e:
                            logger.warning(f"Failed to get counts for folder {folder_name}: {e}")
                            continue
                
                finally:
                    if mail:
                        conn_mgr.close_imap(mail)
            
            return {
                'success': True,
                'folders': all_folders,
                'total_folders': len(all_folders)
            }
            
        except Exception as e:
            logger.error(f"List folders with unread count failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
