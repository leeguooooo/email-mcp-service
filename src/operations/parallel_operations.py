"""
Parallel operations for batch email processing with safety checks
"""
import logging
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

from ..connection_manager import ConnectionManager
from ..account_manager import AccountManager

logger = logging.getLogger(__name__)

class ParallelOperations:
    """Execute batch operations in parallel with account safety"""
    
    def __init__(self, max_workers: int = 5, account_manager=None):
        """
        Initialize parallel operations handler
        
        Args:
            max_workers: Maximum number of concurrent operations
            account_manager: Optional AccountManager instance to reuse (avoids re-reading config)
        """
        self.max_workers = max_workers
        self._lock = threading.Lock()
        self.account_manager = account_manager or AccountManager()
    
    def execute_batch_operation(
        self,
        operation_func: Callable,
        email_ids: List[str],
        folder: str = "INBOX",
        account_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a batch operation on emails with proper account isolation
        
        Args:
            operation_func: Function to execute (delete, mark_read, etc.)
            email_ids: List of email IDs
            folder: Email folder
            account_id: Specific account ID (required for safety)
            **kwargs: Additional arguments for operation_func
            
        Returns:
            Combined results with success/failure counts
        """
        if not account_id:
            return {
                'success': False,
                'error': 'Account ID is required for batch operations to ensure safety'
            }
        
        # Verify account exists
        account = self.account_manager.get_account(account_id)
        if not account:
            return {
                'success': False,
                'error': f'Account not found: {account_id}'
            }
        
        # Get connection manager for specific account
        conn_mgr = ConnectionManager(account)
        
        # Execute operation
        try:
            result = operation_func(
                connection_manager=conn_mgr,
                email_ids=email_ids,
                folder=folder,
                **kwargs
            )
            
            # Add account info to result
            result['account'] = account['email']
            result['account_id'] = account_id
            
            return result
            
        except Exception as e:
            logger.error(f"Batch operation failed for {account['email']}: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': account['email'],
                'account_id': account_id
            }
    
    def execute_multi_account_operation(
        self,
        operation_func: Callable,
        accounts: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute an operation across multiple accounts in parallel
        
        Args:
            operation_func: Function to execute per account
            accounts: List of account configurations
            **kwargs: Arguments passed to operation_func
            
        Returns:
            Combined results from all accounts
        """
        all_results = []
        failed_accounts = []
        success_count = 0
        
        start_time = datetime.now()
        
        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(accounts))) as executor:
            # Submit tasks for each account
            future_to_account = {
                executor.submit(
                    self._execute_for_account,
                    operation_func,
                    account,
                    **kwargs
                ): account
                for account in accounts
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    result = future.result()
                    
                    with self._lock:
                        if result.get('success', False):
                            all_results.append(result)
                            success_count += 1
                        else:
                            failed_accounts.append({
                                'account': account['email'],
                                'error': result.get('error', 'Unknown error')
                            })
                            
                except Exception as e:
                    logger.error(f"Operation failed for {account['email']}: {e}")
                    with self._lock:
                        failed_accounts.append({
                            'account': account['email'],
                            'error': str(e)
                        })
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'success': success_count > 0,
            'results': all_results,
            'failed_accounts': failed_accounts,
            'success_count': success_count,
            'total_accounts': len(accounts),
            'execution_time': elapsed_time
        }
    
    def _execute_for_account(
        self,
        operation_func: Callable,
        account: Dict[str, Any],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute operation for a single account
        
        Args:
            operation_func: Function to execute
            account: Account configuration
            **kwargs: Additional arguments
            
        Returns:
            Operation result
        """
        try:
            conn_mgr = ConnectionManager(account)
            result = operation_func(
                connection_manager=conn_mgr,
                account_id=account['id'],
                **kwargs
            )
            
            # Ensure account info is in result
            if 'account' not in result:
                result['account'] = account['email']
            if 'account_id' not in result:
                result['account_id'] = account['id']
                
            return result
            
        except Exception as e:
            logger.error(f"Account operation failed for {account['email']}: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': account['email'],
                'account_id': account['id']
            }


# Parallel batch operation implementations
class ParallelBatchOperations:
    """Specific batch operations with parallel support"""
    
    @staticmethod
    def batch_delete_emails(
        connection_manager: ConnectionManager,
        email_ids: List[str],
        folder: str = "INBOX",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Delete multiple emails (with account safety)
        
        Args:
            connection_manager: Connection for specific account
            email_ids: List of email IDs to delete
            folder: Email folder
            
        Returns:
            Dict with deletion results
        """
        try:
            mail = connection_manager.connect_imap()
            
            try:
                result, data = mail.select(folder)
                if result != 'OK':
                    logger.debug(f"Folder '{folder}' not available for account {account_id}: {data}")
                    return {'success': False, 'error': f'Folder {folder} not available'}
                
                deleted_count = 0
                failed_ids = []
                
                for email_id in email_ids:
                    try:
                        result, data = mail.store(email_id, '+FLAGS', '\\Deleted')
                        if result == 'OK':
                            deleted_count += 1
                        else:
                            failed_ids.append(email_id)
                    except Exception as e:
                        logger.warning(f"Failed to delete email {email_id}: {e}")
                        failed_ids.append(email_id)
                
                # Expunge to permanently delete
                mail.expunge()
                
                result_data = {
                    'success': True,
                    'message': f'Deleted {deleted_count}/{len(email_ids)} emails',
                    'deleted_count': deleted_count,
                    'total_requested': len(email_ids),
                    'folder': folder
                }
                
                if failed_ids:
                    result_data['failed_ids'] = failed_ids
                
                return result_data
                
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Batch delete failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'deleted_count': 0,
                'total_requested': len(email_ids)
            }
    
    @staticmethod
    def batch_mark_emails(
        connection_manager: ConnectionManager,
        email_ids: List[str],
        folder: str = "INBOX",
        mark_as: str = "read",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Mark multiple emails as read/unread
        
        Args:
            connection_manager: Connection for specific account
            email_ids: List of email IDs
            folder: Email folder
            mark_as: "read" or "unread"
            
        Returns:
            Dict with marking results
        """
        try:
            mail = connection_manager.connect_imap()
            
            try:
                result, data = mail.select(folder)
                if result != 'OK':
                    logger.debug(f"Folder '{folder}' not available for account {account_id}: {data}")
                    return {'success': False, 'error': f'Folder {folder} not available'}
                
                marked_count = 0
                failed_ids = []
                
                # Determine flag operation
                if mark_as == "read":
                    flag_op = '+FLAGS'
                    flag = '\\Seen'
                else:
                    flag_op = '-FLAGS'
                    flag = '\\Seen'
                
                for email_id in email_ids:
                    try:
                        result, data = mail.store(email_id, flag_op, flag)
                        if result == 'OK':
                            marked_count += 1
                        else:
                            failed_ids.append(email_id)
                    except Exception as e:
                        logger.warning(f"Failed to mark email {email_id}: {e}")
                        failed_ids.append(email_id)
                
                result_data = {
                    'success': True,
                    'message': f'Marked {marked_count}/{len(email_ids)} emails as {mark_as}',
                    'marked_count': marked_count,
                    'total_requested': len(email_ids),
                    'mark_as': mark_as,
                    'folder': folder
                }
                
                if failed_ids:
                    result_data['failed_ids'] = failed_ids
                
                return result_data
                
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Batch mark failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'marked_count': 0,
                'total_requested': len(email_ids)
            }
    
    @staticmethod
    def batch_move_emails(
        connection_manager: ConnectionManager,
        email_ids: List[str],
        source_folder: str = "INBOX",
        target_folder: str = "Trash",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Move multiple emails to another folder
        
        Args:
            connection_manager: Connection for specific account
            email_ids: List of email IDs
            source_folder: Source folder
            target_folder: Target folder
            
        Returns:
            Dict with move results
        """
        try:
            mail = connection_manager.connect_imap()
            
            try:
                result, data = mail.select(source_folder)
                if result != 'OK':
                    logger.debug(f"Source folder '{source_folder}' not available for account {account_id}: {data}")
                    return {'success': False, 'error': f'Source folder {source_folder} not available'}
                
                moved_count = 0
                failed_ids = []
                
                for email_id in email_ids:
                    try:
                        # Copy to target folder
                        result, data = mail.copy(email_id, target_folder)
                        if result == 'OK':
                            # Mark as deleted in source
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
                
                # Expunge to remove from source
                mail.expunge()
                
                result_data = {
                    'success': True,
                    'message': f'Moved {moved_count}/{len(email_ids)} emails to {target_folder}',
                    'moved_count': moved_count,
                    'total_requested': len(email_ids),
                    'source_folder': source_folder,
                    'target_folder': target_folder
                }
                
                if failed_ids:
                    result_data['failed_ids'] = failed_ids
                
                return result_data
                
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Batch move failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'moved_count': 0,
                'total_requested': len(email_ids)
            }


# Global instance for reuse
parallel_ops = ParallelOperations(max_workers=5)
batch_ops = ParallelBatchOperations()