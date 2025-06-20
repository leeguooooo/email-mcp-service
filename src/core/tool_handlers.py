"""
Tool handlers implementation - Business logic for each MCP tool
"""
import logging
from typing import Dict, Any, List, Optional
from account_manager import AccountManager
from connection_manager import ConnectionManager
from legacy_operations import (
    fetch_emails, get_email_detail, mark_email_read, 
    delete_email, check_connection, move_email_to_trash
)
from operations.smtp_operations import SMTPOperations
from operations.folder_operations import FolderOperations
from operations.search_operations import SearchOperations
from operations.email_operations import EmailOperations

logger = logging.getLogger(__name__)

class ToolContext:
    """Context passed to tool handlers"""
    def __init__(self, account_manager: AccountManager, messages_func):
        self.account_manager = account_manager
        self.get_message = messages_func
    
    def get_connection_manager(self, account_id: Optional[str] = None) -> ConnectionManager:
        """Get connection manager for specified account"""
        account = self.account_manager.get_account(account_id)
        if not account:
            raise ValueError("No email account configured")
        return ConnectionManager(account)

class EmailToolHandlers:
    """Handlers for email-related tools"""
    
    @staticmethod
    def handle_list_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle list_emails tool"""
        try:
            # Check if we should use optimized fetch
            unread_only = args.get('unread_only', False)
            limit = args.get('limit', 50)
            folder = args.get('folder', 'INBOX')
            account_id = args.get('account_id')
            
            # If fetching all unread from all accounts/folders
            if unread_only and not account_id and folder == 'INBOX':
                try:
                    from operations.optimized_fetch import fetch_all_providers_optimized
                    result = fetch_all_providers_optimized(limit, unread_only)
                except ImportError:
                    logger.warning("Optimized fetch not available, using standard fetch")
                    result = fetch_emails(limit, unread_only, folder, account_id)
            else:
                result = fetch_emails(limit, unread_only, folder, account_id)
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            return EmailToolHandlers._format_email_list(result, ctx)
            
        except Exception as e:
            logger.error(f"List emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_get_email_detail(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle get_email_detail tool"""
        try:
            result = get_email_detail(
                args['email_id'],
                args.get('folder', 'INBOX'),
                args.get('account_id')
            )
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            return EmailToolHandlers._format_email_detail(result, ctx)
            
        except Exception as e:
            logger.error(f"Get email detail failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_mark_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle mark_emails tool"""
        try:
            email_ids = args['email_ids']
            mark_as = args['mark_as']
            folder = args.get('folder', 'INBOX')
            account_id = args.get('account_id')
            
            # Use parallel operations if available and multiple emails
            if len(email_ids) > 1:
                try:
                    from operations.parallel_operations import parallel_ops, batch_ops
                    result = parallel_ops.execute_batch_operation(
                        batch_ops.batch_mark_emails,
                        email_ids,
                        folder,
                        account_id,
                        mark_as=mark_as
                    )
                except ImportError:
                    # Fallback to sequential
                    results = []
                    for email_id in email_ids:
                        if mark_as == 'read':
                            res = mark_email_read(email_id, folder, account_id)
                        else:
                            conn_mgr = ctx.get_connection_manager(account_id)
                            email_ops = EmailOperations(conn_mgr)
                            res = email_ops.mark_email_unread(email_id, folder)
                        results.append(res)
                    
                    success_count = sum(1 for r in results if 'error' not in r)
                    result = {
                        'success': success_count == len(results),
                        'marked_count': success_count,
                        'total': len(results)
                    }
            else:
                # Single email
                email_id = email_ids[0]
                if mark_as == 'read':
                    result = mark_email_read(email_id, folder, account_id)
                else:
                    conn_mgr = ctx.get_connection_manager(account_id)
                    email_ops = EmailOperations(conn_mgr)
                    result = email_ops.mark_email_unread(email_id, folder)
            
            if result.get('success'):
                return [{
                    "type": "text",
                    "text": ctx.get_message('operation_success')
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('operation_failed')}{result.get('error', 'Unknown error')}"
                }]
                
        except Exception as e:
            logger.error(f"Mark emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_delete_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle delete_emails tool"""
        try:
            email_ids = args['email_ids']
            folder = args.get('folder', 'INBOX')
            permanent = args.get('permanent', False)
            trash_folder = args.get('trash_folder', 'Trash')
            account_id = args.get('account_id')
            
            # Use parallel operations if available and multiple emails
            if len(email_ids) > 1:
                try:
                    from operations.parallel_operations import parallel_ops, batch_ops
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
                except ImportError:
                    # Fallback to sequential
                    results = []
                    for email_id in email_ids:
                        if permanent:
                            res = delete_email(email_id, folder, account_id)
                        else:
                            res = move_email_to_trash(email_id, folder, trash_folder, account_id)
                        results.append(res)
                    
                    success_count = sum(1 for r in results if r.get('success'))
                    result = {
                        'success': success_count == len(results),
                        'deleted_count': success_count,
                        'total': len(results)
                    }
            else:
                # Single email
                email_id = email_ids[0]
                if permanent:
                    result = delete_email(email_id, folder, account_id)
                else:
                    result = move_email_to_trash(email_id, folder, trash_folder, account_id)
            
            if result.get('success'):
                return [{
                    "type": "text",
                    "text": ctx.get_message('operation_success')
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('operation_failed')}{result.get('error', 'Unknown error')}"
                }]
                
        except Exception as e:
            logger.error(f"Delete emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_search_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle search_emails tool"""
        try:
            # Use optimized search if available
            try:
                from operations.optimized_search import search_all_accounts_parallel
                result = search_all_accounts_parallel(
                    query=args.get('query'),
                    search_in=args.get('search_in', 'all'),
                    date_from=args.get('date_from'),
                    date_to=args.get('date_to'),
                    folder=args.get('folder', 'all'),
                    unread_only=args.get('unread_only', False),
                    limit=args.get('limit', 50),
                    account_id=args.get('account_id')
                )
            except ImportError:
                # Fallback to standard search
                conn_mgr = ctx.get_connection_manager(args.get('account_id'))
                search_ops = SearchOperations(conn_mgr)
                result = search_ops.search_emails(
                    query=args.get('query'),
                    search_in=args.get('search_in', 'all'),
                    date_from=args.get('date_from'),
                    date_to=args.get('date_to'),
                    folder=args.get('folder', 'INBOX'),
                    unread_only=args.get('unread_only', False),
                    has_attachments=args.get('has_attachments'),
                    limit=args.get('limit', 50)
                )
            
            if not result.get('success', True):
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result.get('error', 'Search failed')}"
                }]
            
            return EmailToolHandlers._format_search_results(result, ctx)
            
        except Exception as e:
            logger.error(f"Search emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def _format_email_list(result: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Format email list for display"""
        emails = result.get('emails', [])
        
        if not emails:
            return [{"type": "text", "text": ctx.get_message('no_email')}]
        
        response = []
        
        # Summary
        if 'accounts_count' in result:
            summary = ctx.get_message('found_emails', 
                len(emails), 
                result.get('total_emails', 0),
                result.get('total_unread', 0)
            )
            response.append({"type": "text", "text": summary})
            
            if result['accounts_count'] > 0:
                response.append({
                    "type": "text",
                    "text": ctx.get_message('from_accounts', result['accounts_count'])
                })
        
        # Email list
        email_list = []
        for email in emails:
            mark = ctx.get_message('unread_mark') if email.get('unread') else ctx.get_message('read_mark')
            
            email_info = f"{mark}{email['subject']}\n"
            email_info += f"  {ctx.get_message('from')}{email['from']}\n"
            email_info += f"  {ctx.get_message('date')}{email['date']}\n"
            email_info += f"  {ctx.get_message('id')}{email['id']}"
            
            if 'account' in email:
                email_info += f"\n  {ctx.get_message('account')}{email['account']}"
            
            email_list.append(email_info)
        
        response.append({
            "type": "text",
            "text": "\n\n".join(email_list)
        })
        
        # Performance metrics
        if 'fetch_time' in result:
            response.append({
                "type": "text",
                "text": ctx.get_message('fetch_time', result['fetch_time'])
            })
        
        # Account details
        if 'accounts_info' in result and result['accounts_info']:
            account_details = [ctx.get_message('account_stats')]
            for acc in result['accounts_info']:
                detail = f"  • {acc['account']}: {ctx.get_message('emails_count', acc['fetched'], acc['total'], acc['unread'])}"
                account_details.append(detail)
            
            response.append({
                "type": "text",
                "text": "\n".join(account_details)
            })
        
        return response
    
    @staticmethod
    def _format_email_detail(email: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Format email detail for display"""
        response = []
        
        # Headers
        headers = f"**Subject:** {email['subject']}\n"
        headers += f"**From:** {email['from']}\n"
        headers += f"**To:** {email['to']}\n"
        if email.get('cc'):
            headers += f"**CC:** {email['cc']}\n"
        headers += f"**Date:** {email['date']}\n"
        
        if email.get('attachments'):
            headers += f"**Attachments:** {len(email['attachments'])} file(s)\n"
            for att in email['attachments']:
                headers += f"  - {att['filename']} ({att.get('size', 'unknown size')})\n"
        
        response.append({"type": "text", "text": headers})
        
        # Body
        if email.get('body'):
            response.append({
                "type": "text",
                "text": f"\n**Content:**\n{email['body']}"
            })
        
        return response
    
    @staticmethod
    def _format_search_results(result: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Format search results for display"""
        emails = result.get('emails', [])
        
        if not emails:
            return [{"type": "text", "text": ctx.get_message('no_email')}]
        
        response = []
        
        # Summary
        summary = f"Found {len(emails)} email(s)"
        if 'total_found' in result:
            summary += f" (showing {result.get('displayed', len(emails))} of {result['total_found']})"
        
        response.append({"type": "text", "text": summary})
        
        # Format emails similar to list
        email_list_result = EmailToolHandlers._format_email_list({'emails': emails}, ctx)
        
        # If email_list_result has summary, skip it; otherwise keep all items
        if len(email_list_result) > 1:
            # Has summary, skip the first item
            return response + email_list_result[1:]
        else:
            # No summary, keep all items
            return response + email_list_result