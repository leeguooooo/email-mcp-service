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
        account_id: Optional[str] = None,
        offset: int = 0,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        List emails from inbox
        
        Args:
            limit: Maximum number of emails to return
            unread_only: Only return unread emails
            folder: Email folder to fetch from
            account_id: Specific account to fetch from (optional)
            offset: Number of emails to skip for pagination (default: 0)
            include_metadata: Include source metadata in results (default: True)
            
        Returns:
            Dictionary containing emails list and metadata with 'success' field
        """
        try:
            # Import here to avoid circular dependencies
            from ..legacy_operations import fetch_emails
            
            # Check if we should use optimized fetch
            if unread_only and not account_id and folder == 'INBOX' and offset == 0:
                try:
                    from ..operations.optimized_fetch import fetch_all_providers_optimized
                    result = fetch_all_providers_optimized(limit, unread_only)
                    result = self._ensure_success_field(result)
                    
                    # Add metadata if requested
                    if include_metadata and 'emails' in result:
                        for email in result['emails']:
                            email['source'] = 'optimized_fetch'
                    
                    return result
                except ImportError:
                    logger.debug("Optimized fetch not available, using standard fetch")
            
            # Fetch with offset applied (fetch more and slice)
            fetch_limit = limit + offset if offset > 0 else limit
            result = fetch_emails(fetch_limit, unread_only, folder, account_id)
            result = self._ensure_success_field(result)
            
            # Apply pagination
            if offset > 0 and 'emails' in result:
                result['emails'] = result['emails'][offset:offset + limit]
                result['offset'] = offset
                result['limit'] = limit
            
            # Add metadata if requested
            if include_metadata and 'emails' in result:
                for email in result['emails']:
                    if 'source' not in email:
                        email['source'] = 'imap_fetch'
            
            return result
            
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
        account_id: Optional[str] = None,
        dry_run: bool = False,
        email_accounts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Mark emails as read or unread
        
        Args:
            email_ids: List of email IDs to mark
            mark_as: 'read' or 'unread'
            folder: Email folder
            account_id: Specific account ID (optional)
            dry_run: If true, only validate without executing (default: False)
            email_accounts: Optional per-email account mapping for multi-account scenarios
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        # Dry run mode: validate and return without executing
        if dry_run:
            return {
                'success': True,
                'dry_run': True,
                'would_mark': len(email_ids),
                'mark_as': mark_as,
                'email_ids': email_ids,
                'message': f'Dry run: would mark {len(email_ids)} emails as {mark_as}'
            }
        try:
            from ..legacy_operations import mark_email_read
            from ..connection_manager import ConnectionManager
            from ..operations.email_operations import EmailOperations
            
            # Helper caches for unread operations
            conn_cache: Dict[str, ConnectionManager] = {}
            ops_cache: Dict[str, EmailOperations] = {}
            available_accounts = [acc['id'] for acc in self.account_manager.list_accounts() if acc.get('id')]
            
            def _get_email_ops(acc_id: str) -> EmailOperations:
                if acc_id not in ops_cache:
                    account = self.account_manager.get_account(acc_id)
                    if not account:
                        raise ValueError(f'No email account configured for {acc_id}')
                    conn_mgr = ConnectionManager(account)
                    conn_cache[acc_id] = conn_mgr
                    ops_cache[acc_id] = EmailOperations(conn_mgr)
                return ops_cache[acc_id]
            
            def _mark_single(email_id: str, fld: str, acc_id: Optional[str]) -> Dict[str, Any]:
                candidate_ids = []
                if acc_id:
                    candidate_ids.append(acc_id)
                else:
                    candidate_ids.extend(available_accounts)
                if not candidate_ids:
                    return {
                        'success': False,
                        'error': 'No email accounts configured',
                        'email_id': email_id,
                        'folder': fld
                    }
                attempts = []
                for candidate in candidate_ids:
                    try:
                        if mark_as == 'read':
                            result = mark_email_read(email_id, fld, candidate)
                        else:
                            email_ops = _get_email_ops(candidate)
                            result = email_ops.mark_email_unread(email_id, fld)
                        result = self._ensure_success_field(result)
                        result.setdefault('email_id', email_id)
                        result.setdefault('folder', fld)
                        result.setdefault('account_id', candidate)
                        if result.get('success'):
                            return result
                        attempts.append(result)
                    except Exception as exc:
                        attempts.append({
                            'success': False,
                            'error': str(exc),
                            'email_id': email_id,
                            'folder': fld,
                            'account_id': candidate
                        })
                failure = attempts[-1] if attempts else {
                    'success': False,
                    'error': 'Unable to mark email (no successful account matches)',
                    'email_id': email_id,
                    'folder': fld
                }
                failure['success'] = False
                failure.setdefault('attempted_accounts', [a.get('account_id') for a in attempts if a.get('account_id')])
                return failure
            
            def sequential_mark(ids: List[str], fld: str, acc_id: Optional[str]) -> Dict[str, Any]:
                results = [_mark_single(eid, fld, acc_id) for eid in ids]
                success_count = sum(1 for r in results if r.get('success'))
                return {
                    'success': success_count == len(results),
                    'marked_count': success_count,
                    'total': len(results),
                    'results': results
                }
            
            # Determine default account automatically if there is only one configured
            if not account_id and not email_accounts and len(available_accounts) == 1:
                account_id = available_accounts[0]
            
            # Single email fast-path when account is known
            if len(email_ids) == 1 and not email_accounts:
                single_id = email_ids[0]
                target_account = account_id
                return sequential_mark([single_id], folder, target_account)
            
            # Multiple emails with explicit account map
            if not account_id and email_accounts:
                results = []
                for entry in email_accounts:
                    email_id = entry.get('email_id')
                    entry_account = entry.get('account_id')
                    entry_folder = entry.get('folder', folder)
                    if not email_id:
                        results.append({
                            'success': False,
                            'error': 'email_id is required for each email_accounts entry'
                        })
                        continue
                    results.append(_mark_single(email_id, entry_folder, entry_account))
                
                total = len(email_accounts)
                success_count = sum(1 for r in results if r.get('success'))
                return {
                    'success': success_count == total,
                    'marked_count': success_count,
                    'total': total,
                    'results': results
                }
            
            # Multiple emails - prefer parallel when account_id is known
            if len(email_ids) > 1:
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
                except Exception as exc:
                    logger.warning(f"Parallel mark failed, falling back to sequential: {exc}")
            
            return sequential_mark(email_ids, folder, account_id)
                    
        except Exception as e:
            logger.error(f"Mark emails failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def delete_emails(
        self,
        email_ids: List[str],
        folder: str = 'INBOX',
        permanent: bool = False,
        trash_folder: str = 'Trash',
        account_id: Optional[str] = None,
        dry_run: bool = False,
        email_accounts: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Delete emails (move to trash or permanently delete)
        
        Args:
            email_ids: List of email IDs to delete
            folder: Source folder
            permanent: Permanently delete instead of moving to trash
            trash_folder: Trash folder name
            account_id: Specific account ID (optional)
            dry_run: If true, only validate without executing (default: False)
            email_accounts: Optional per-email account mapping for multi-account scenarios
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        # Dry run mode: validate and return without executing
        if dry_run:
            return {
                'success': True,
                'dry_run': True,
                'would_delete': len(email_ids),
                'permanent': permanent,
                'email_ids': email_ids,
                'message': f'Dry run: would {"permanently delete" if permanent else "move to trash"} {len(email_ids)} emails'
            }
        try:
            from ..legacy_operations import delete_email, move_email_to_trash
            
            available_accounts = [acc['id'] for acc in self.account_manager.list_accounts() if acc.get('id')]
            
            def _delete_single(email_id: str, fld: str, acc_id: Optional[str], trash_fld: str) -> Dict[str, Any]:
                candidate_ids = []
                if acc_id:
                    candidate_ids.append(acc_id)
                else:
                    candidate_ids.extend(available_accounts)
                if not candidate_ids:
                    return {
                        'success': False,
                        'error': 'No email accounts configured',
                        'email_id': email_id,
                        'folder': fld
                    }
                attempts = []
                for candidate in candidate_ids:
                    try:
                        if permanent:
                            result = delete_email(email_id, fld, candidate)
                        else:
                            result = move_email_to_trash(email_id, fld, trash_fld, candidate)
                        result = self._ensure_success_field(result)
                        result.setdefault('email_id', email_id)
                        result.setdefault('folder', fld)
                        result.setdefault('account_id', candidate)
                        if result.get('success'):
                            return result
                        attempts.append(result)
                    except Exception as exc:
                        attempts.append({
                            'success': False,
                            'error': str(exc),
                            'email_id': email_id,
                            'folder': fld,
                            'account_id': candidate
                        })
                failure = attempts[-1] if attempts else {
                    'success': False,
                    'error': 'Unable to delete email (no successful account matches)',
                    'email_id': email_id,
                    'folder': fld
                }
                failure['success'] = False
                failure.setdefault('attempted_accounts', [a.get('account_id') for a in attempts if a.get('account_id')])
                return failure
            
            def sequential_delete(ids: List[str], fld: str, acc_id: Optional[str], trash_fld: str) -> Dict[str, Any]:
                results = [_delete_single(eid, fld, acc_id, trash_fld) for eid in ids]
                success_count = sum(1 for r in results if r.get('success'))
                return {
                    'success': success_count == len(results),
                    'deleted_count': success_count,
                    'total': len(results),
                    'results': results
                }
            
            if not account_id and not email_accounts and len(available_accounts) == 1:
                account_id = available_accounts[0]
            
            if len(email_ids) == 1 and not email_accounts:
                single_id = email_ids[0]
                return sequential_delete([single_id], folder, account_id, trash_folder)
            
            if not account_id and email_accounts:
                results = []
                for entry in email_accounts:
                    email_id = entry.get('email_id')
                    entry_account = entry.get('account_id')
                    entry_folder = entry.get('folder', folder)
                    if not email_id:
                        results.append({
                            'success': False,
                            'error': 'email_id is required for each email_accounts entry'
                        })
                        continue
                    results.append(_delete_single(email_id, entry_folder, entry_account, trash_folder))
                
                total = len(email_accounts)
                success_count = sum(1 for r in results if r.get('success'))
                return {
                    'success': success_count == total,
                    'deleted_count': success_count,
                    'total': total,
                    'results': results
                }
            
            if len(email_ids) > 1:
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
                except Exception as exc:
                    logger.warning(f"Parallel delete failed, falling back to sequential: {exc}")
            
            return sequential_delete(email_ids, folder, account_id, trash_folder)
                    
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
        account_id: Optional[str] = None,
        offset: int = 0
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
            offset: Number of results to skip for pagination (default: 0)
            
        Returns:
            Dictionary containing search results with 'success' field
        """
        try:
            # Use optimized search if available
            try:
                from ..operations.optimized_search import search_all_accounts_parallel
                
                # Fetch more to handle offset
                fetch_limit = limit + offset if offset > 0 else limit
                result = search_all_accounts_parallel(
                    query=query,
                    search_in=search_in,
                    date_from=date_from,
                    date_to=date_to,
                    folder=folder,
                    unread_only=unread_only,
                    limit=fetch_limit,
                    account_id=account_id
                )
                result = self._ensure_success_field(result)
                
                # Apply pagination
                if offset > 0 and 'emails' in result:
                    result['emails'] = result['emails'][offset:offset + limit]
                    result['offset'] = offset
                    result['limit'] = limit
                
                return result
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
                
                # Handle offset for fallback (fetch more and slice)
                fetch_limit = limit + offset if offset > 0 else limit
                result = search_ops.search_emails(
                    query=query,
                    search_in=search_in,
                    date_from=date_from,
                    date_to=date_to,
                    folder=folder if folder != 'all' else 'INBOX',
                    unread_only=unread_only,
                    has_attachments=has_attachments,
                    limit=fetch_limit
                )
                result = self._ensure_success_field(result)
                
                # Apply pagination if offset is used
                if offset > 0 and 'emails' in result:
                    result['emails'] = result['emails'][offset:offset + limit]
                    result['offset'] = offset
                    result['limit'] = limit
                
                return result
                
        except Exception as e:
            logger.error(f"Search emails failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def get_email_headers(
        self,
        email_id: str,
        folder: str = 'INBOX',
        account_id: Optional[str] = None,
        headers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get only email headers without fetching body (atomic operation, efficient for classification)
        
        Args:
            email_id: Email ID to get headers from
            folder: Email folder
            account_id: Specific account ID (optional)
            headers: Specific headers to retrieve (optional, defaults to common headers)
            
        Returns:
            Dictionary containing email headers with 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            
            # Default common headers if not specified
            if not headers:
                headers = ['From', 'To', 'Subject', 'Date', 'Message-ID', 'CC', 'BCC', 'Reply-To']
            
            mail = conn_mgr.connect_imap()
            
            try:
                mail.select(folder, readonly=True)
                
                # Fetch only headers using UID (email_id is UID, not sequence number)
                fetch_command = '(BODY.PEEK[HEADER.FIELDS ({})])'.format(' '.join(headers))
                _, msg_data = mail.uid('fetch', email_id, fetch_command)
                
                if not msg_data or not msg_data[0]:
                    return {'error': 'Email not found', 'success': False}
                
                # Parse headers
                from email.parser import HeaderParser
                
                # UID fetch returns: [(b'UID_NUM (UID UID_NUM BODY[...] {...})', b'header_data'), ...]
                # Need to extract the actual header data
                header_data = None
                if isinstance(msg_data[0], tuple) and len(msg_data[0]) >= 2:
                    header_data = msg_data[0][1]
                elif isinstance(msg_data[0], bytes):
                    header_data = msg_data[0]
                
                if not header_data:
                    return {'error': 'Failed to parse email headers', 'success': False}
                
                if isinstance(header_data, bytes):
                    header_data = header_data.decode('utf-8', errors='replace')
                
                parser = HeaderParser()
                parsed_headers = parser.parsestr(header_data)
                
                result_headers = {}
                for header_name in headers:
                    value = parsed_headers.get(header_name)
                    if value:
                        result_headers[header_name] = value
                
                return {
                    'success': True,
                    'headers': result_headers,
                    'email_id': email_id,
                    'folder': folder,
                    'account_id': account.get('email', account_id),
                    'source': 'imap_headers_uid'
                }
            
            finally:
                conn_mgr.close_imap(mail)
            
        except Exception as e:
            logger.error(f"Get email headers failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
