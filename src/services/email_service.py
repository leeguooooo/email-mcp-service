"""
Email service layer - Clean interface for email operations
"""
import logging
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


class EmailService:
    """Service layer for email operations"""
    
    def __init__(self, account_manager):
        """
        Initialize email service
        
        Args:
            account_manager: AccountManager instance
        """
        self.account_manager = account_manager
    
    def _execute_with_parallel_fallback(
        self,
        email_ids: List[str],
        folder: str,
        account_id: Optional[str],
        parallel_operation: Callable,
        sequential_operation: Callable,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute operation with automatic parallel/sequential fallback
        
        Args:
            email_ids: List of email IDs
            folder: Email folder
            account_id: Account ID
            parallel_operation: Parallel operation function to try
            sequential_operation: Sequential operation function as fallback
            **kwargs: Additional operation-specific parameters
            
        Returns:
            Dictionary with operation result
        """
        if len(email_ids) > 1:
            # Try parallel operations first
            try:
                from ..operations.parallel_operations import parallel_ops
                return parallel_ops.execute_batch_operation(
                    parallel_operation,
                    email_ids,
                    folder,
                    account_id,
                    **kwargs
                )
            except ImportError:
                logger.debug("Parallel operations not available, using sequential fallback")
            
            # Sequential fallback
            return sequential_operation(email_ids, folder, account_id, **kwargs)
        else:
            # Single email - use sequential
            return sequential_operation(email_ids, folder, account_id, **kwargs)
    
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
    
    def list_emails(
        self,
        limit: int = 50,
        unread_only: bool = False,
        folder: str = 'INBOX',
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List emails from inbox
        
        Args:
            limit: Maximum number of emails to return
            unread_only: Only return unread emails
            folder: Email folder to fetch from
            account_id: Specific account to fetch from (optional)
            
        Returns:
            Dictionary containing emails list and metadata with 'success' field
        """
        try:
            # Import here to avoid circular dependencies
            from ..legacy_operations import fetch_emails
            
            # Check if we should use optimized fetch
            if unread_only and not account_id and folder == 'INBOX':
                try:
                    from ..operations.optimized_fetch import fetch_all_providers_optimized
                    result = fetch_all_providers_optimized(limit, unread_only)
                    return self._ensure_success_field(result)
                except ImportError:
                    logger.debug("Optimized fetch not available, using standard fetch")
            
            result = fetch_emails(limit, unread_only, folder, account_id)
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"List emails failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def get_email_detail(
        self,
        email_id: str,
        folder: str = 'INBOX',
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get detailed content of a specific email
        
        Args:
            email_id: The ID of the email to retrieve
            folder: Email folder
            account_id: Specific account ID (optional)
            
        Returns:
            Dictionary containing email details with 'success' field
        """
        try:
            from ..legacy_operations import get_email_detail
            result = get_email_detail(email_id, folder, account_id)
            return self._ensure_success_field(result)
        except Exception as e:
            logger.error(f"Get email detail failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def mark_emails(
        self,
        email_ids: List[str],
        mark_as: str,
        folder: str = 'INBOX',
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mark emails as read or unread
        
        Args:
            email_ids: List of email IDs to mark
            mark_as: 'read' or 'unread'
            folder: Email folder
            account_id: Specific account ID (optional)
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        try:
            from ..legacy_operations import mark_email_read
            from ..connection_manager import ConnectionManager
            from ..operations.email_operations import EmailOperations
            
            def sequential_mark(ids: List[str], fld: str, acc_id: Optional[str], **kwargs) -> Dict[str, Any]:
                """Sequential fallback for marking emails"""
                mark_type = kwargs.get('mark_as', 'read')
                
                # Get account once outside loop for efficiency
                account = None
                if mark_type == 'unread':
                    account = self.account_manager.get_account(acc_id)
                    if not account:
                        return {'error': 'No email account configured', 'success': False}
                    conn_mgr = ConnectionManager(account)
                    email_ops = EmailOperations(conn_mgr)
                
                results = []
                for email_id in ids:
                    if mark_type == 'read':
                        res = mark_email_read(email_id, fld, acc_id)
                    else:
                        res = email_ops.mark_email_unread(email_id, fld)
                    results.append(res)
                
                success_count = sum(1 for r in results if 'error' not in r)
                return {
                    'success': success_count == len(results),
                    'marked_count': success_count,
                    'total': len(results)
                }
            
            # Single email - direct execution
            if len(email_ids) == 1:
                email_id = email_ids[0]
                if mark_as == 'read':
                    result = mark_email_read(email_id, folder, account_id)
                else:
                    account = self.account_manager.get_account(account_id)
                    if not account:
                        return {'error': 'No email account configured', 'success': False}
                    conn_mgr = ConnectionManager(account)
                    email_ops = EmailOperations(conn_mgr)
                    result = email_ops.mark_email_unread(email_id, folder)
                return self._ensure_success_field(result)
            
            # Multiple emails - try parallel, fallback to sequential
            try:
                from ..operations.parallel_operations import parallel_ops, batch_ops
                result = parallel_ops.execute_batch_operation(
                    batch_ops.batch_mark_emails,
                    email_ids,
                    folder,
                    account_id,
                    mark_as=mark_as
                )
                return self._ensure_success_field(result)
            except ImportError:
                logger.debug("Parallel operations not available, using sequential fallback")
                return sequential_mark(email_ids, folder, account_id, mark_as=mark_as)
                    
        except Exception as e:
            logger.error(f"Mark emails failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def delete_emails(
        self,
        email_ids: List[str],
        folder: str = 'INBOX',
        permanent: bool = False,
        trash_folder: str = 'Trash',
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Delete emails (move to trash or permanently delete)
        
        Args:
            email_ids: List of email IDs to delete
            folder: Source folder
            permanent: Permanently delete instead of moving to trash
            trash_folder: Trash folder name
            account_id: Specific account ID (optional)
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        try:
            from ..legacy_operations import delete_email, move_email_to_trash
            
            def sequential_delete(ids: List[str], fld: str, acc_id: Optional[str], **kwargs) -> Dict[str, Any]:
                """Sequential fallback for deleting emails"""
                is_permanent = kwargs.get('permanent', False)
                trash_fld = kwargs.get('trash_folder', 'Trash')
                
                results = []
                for email_id in ids:
                    if is_permanent:
                        res = delete_email(email_id, fld, acc_id)
                    else:
                        res = move_email_to_trash(email_id, fld, trash_fld, acc_id)
                    results.append(res)
                
                success_count = sum(1 for r in results if r.get('success'))
                return {
                    'success': success_count == len(results),
                    'deleted_count': success_count,
                    'total': len(results)
                }
            
            # Single email - direct execution
            if len(email_ids) == 1:
                email_id = email_ids[0]
                if permanent:
                    result = delete_email(email_id, folder, account_id)
                else:
                    result = move_email_to_trash(email_id, folder, trash_folder, account_id)
                return self._ensure_success_field(result)
            
            # Multiple emails - try parallel, fallback to sequential
            try:
                from ..operations.parallel_operations import parallel_ops, batch_ops
                if permanent:
                    result = parallel_ops.execute_batch_operation(
                        batch_ops.batch_delete_emails,
                        email_ids,
                        folder,
                        account_id
                    )
                else:
                    result = parallel_ops.execute_batch_operation(
                        batch_ops.batch_move_emails,
                        email_ids,
                        folder,
                        account_id,
                        target_folder=trash_folder
                    )
                return self._ensure_success_field(result)
            except ImportError:
                logger.debug("Parallel operations not available, using sequential fallback")
                return sequential_delete(email_ids, folder, account_id, permanent=permanent, trash_folder=trash_folder)
                    
        except Exception as e:
            logger.error(f"Delete emails failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def search_emails(
        self,
        query: Optional[str] = None,
        search_in: str = 'all',
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        folder: str = 'all',
        unread_only: bool = False,
        has_attachments: Optional[bool] = None,
        limit: int = 50,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search emails with various criteria
        
        Args:
            query: Search query text
            search_in: Where to search (subject, from, body, to, all)
            date_from: Start date (YYYY-MM-DD format)
            date_to: End date (YYYY-MM-DD format)
            folder: Folder to search in
            unread_only: Only search unread emails
            has_attachments: Filter by attachment presence
            limit: Maximum results
            account_id: Search specific account only
            
        Returns:
            Dictionary containing search results with 'success' field
        """
        try:
            # Use optimized search if available
            try:
                from ..operations.optimized_search import search_all_accounts_parallel
                result = search_all_accounts_parallel(
                    query=query,
                    search_in=search_in,
                    date_from=date_from,
                    date_to=date_to,
                    folder=folder,
                    unread_only=unread_only,
                    limit=limit,
                    account_id=account_id
                )
                return self._ensure_success_field(result)
            except ImportError:
                logger.debug("Optimized search not available, using standard search")
                # Fallback to standard search
                from ..connection_manager import ConnectionManager
                from ..operations.search_operations import SearchOperations
                
                account = self.account_manager.get_account(account_id)
                if not account:
                    return {'error': 'No email account configured', 'success': False}
                    
                conn_mgr = ConnectionManager(account)
                search_ops = SearchOperations(conn_mgr)
                result = search_ops.search_emails(
                    query=query,
                    search_in=search_in,
                    date_from=date_from,
                    date_to=date_to,
                    folder=folder if folder != 'all' else 'INBOX',
                    unread_only=unread_only,
                    has_attachments=has_attachments,
                    limit=limit
                )
                return self._ensure_success_field(result)
                
        except Exception as e:
            logger.error(f"Search emails failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}

