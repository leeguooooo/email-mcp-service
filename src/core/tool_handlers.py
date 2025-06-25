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
            limit = args.get('limit', 100)
            # 最少显示50封
            if limit < 50:
                limit = 50
            folder = args.get('folder', 'INBOX')
            account_id = args.get('account_id')
            
            # If fetching unread emails, use database for accurate status
            if unread_only:
                try:
                    from operations.database_fetch import fetch_emails_from_database
                    logger.info("Using database fetch for unread emails (accurate read status)")
                    result = fetch_emails_from_database(limit, unread_only, account_id)
                except ImportError:
                    logger.warning("Database fetch not available, using standard fetch")
                    result = fetch_emails(limit, unread_only, folder, account_id)
            else:
                # Regular fetch for all emails
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
            # Try new improved function first
            try:
                from operations.improved_email_ops import get_email_detail_by_db_id
                result = get_email_detail_by_db_id(
                    args['email_id'],
                    args.get('account_id')
                )
            except ImportError:
                # Fallback to legacy function
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
            
            # Try improved delete function first
            try:
                from operations.improved_email_ops import delete_emails_by_db_ids
                result = delete_emails_by_db_ids(email_ids, permanent)
            except ImportError:
                # Fallback to legacy operations
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
                        logger.info("Parallel operations not available, using sequential delete")
                        # Fallback to sequential
                        results = []
                        errors = []
                        for email_id in email_ids:
                            try:
                                if permanent:
                                    res = delete_email(email_id, folder, account_id)
                                else:
                                    res = move_email_to_trash(email_id, folder, trash_folder, account_id)
                                results.append(res)
                                if not res.get('success'):
                                    errors.append(f"Email {email_id}: {res.get('error', 'Unknown error')}")
                            except Exception as e:
                                errors.append(f"Email {email_id}: {str(e)}")
                                results.append({'success': False, 'error': str(e)})
                        
                        success_count = sum(1 for r in results if r.get('success'))
                        result = {
                            'success': success_count == len(results),
                            'deleted_count': success_count,
                            'total': len(results)
                        }
                        if errors:
                            result['errors'] = errors
                else:
                    # Single email
                    email_id = email_ids[0]
                    if permanent:
                        result = delete_email(email_id, folder, account_id)
                    else:
                        result = move_email_to_trash(email_id, folder, trash_folder, account_id)
            
            if result.get('success'):
                deleted_count = result.get('deleted_count', len(email_ids) if isinstance(email_ids, list) else 1)
                action_text = "永久删除" if permanent else "移到垃圾箱"
                return [{
                    "type": "text",
                    "text": f"✅ 成功{action_text} {deleted_count} 封邮件"
                }]
            else:
                error_msg = result.get('error', 'Unknown error')
                if result.get('errors'):
                    error_msg = '\n'.join(result['errors'])
                elif result.get('deleted_count', 0) > 0:
                    total = result.get('total', len(email_ids) if isinstance(email_ids, list) else 1)
                    error_msg = f"部分成功: 删除了 {result['deleted_count']}/{total} 封邮件\n{error_msg}"
                
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('operation_failed')}{error_msg}"
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
                    limit=args.get('limit', 100),
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
                    limit=args.get('limit', 100)
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
        """Format email list for display - concise grouped format"""
        emails = result.get('emails', [])
        
        if not emails:
            return [{"type": "text", "text": ctx.get_message('no_email')}]
        
        # Group emails by account
        emails_by_account = {}
        for email in emails:
            account = email.get('account', 'Unknown')
            if account not in emails_by_account:
                emails_by_account[account] = []
            emails_by_account[account].append(email)
        
        # Build concise output
        output_lines = []
        
        # Summary line
        total_emails = len(emails)
        total_unread = sum(1 for e in emails if e.get('unread'))
        output_lines.append(f"📧 {total_emails} 封邮件 ({total_unread} 未读)")
        output_lines.append("💡 使用 get_email_detail 工具和 [ID] 查看详情")
        output_lines.append("🗑️ 使用 delete_emails 工具和 [ID] 删除邮件")
        output_lines.append("")
        
        # Format each account's emails
        for account, account_emails in emails_by_account.items():
            # Account header with count
            unread_count = sum(1 for e in account_emails if e.get('unread'))
            output_lines.append(f"📮 {account} ({len(account_emails)}封，{unread_count}未读)")
            output_lines.append("")
            
            # Email entries - ultra-concise single line format
            for email in account_emails[:50]:  # Limit per account
                # Use symbols: 🔴 for unread, nothing for read
                mark = "🔴" if email.get('unread') else "  "
                
                # Truncate subject if too long
                subject = email.get('subject', 'No subject')
                if len(subject) > 50:
                    subject = subject[:47] + "..."
                
                # Extract sender name (before email address)
                sender = email.get('from', 'Unknown')
                if '<' in sender:
                    sender = sender.split('<')[0].strip()
                if len(sender) > 15:
                    sender = sender[:12] + "..."
                
                # Format date/time to MM-DD HH:MM
                date_str = email.get('date', '')
                # Try to parse and format date
                try:
                    from datetime import datetime
                    # Handle various date formats
                    if 'T' in date_str:  # ISO format
                        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else:
                        # Try to parse other formats
                        parts = date_str.split()
                        if len(parts) >= 5:  # Full email date format
                            dt = datetime.strptime(' '.join(parts[1:5]), '%d %b %Y %H:%M:%S')
                        else:
                            dt = None
                    
                    if dt:
                        date_str = dt.strftime('%m-%d %H:%M')
                except:
                    # Fallback - just take first 10 chars if too long
                    if len(date_str) > 10:
                        date_str = date_str[:10]
                
                # Build compact line: mark [ID] Subject | Sender | Time
                email_id = email.get('id', 'no-id')
                if len(str(email_id)) > 8:
                    email_id = str(email_id)[:8]
                
                # 使用方括号让ID更明显
                line = f"{mark}[{email_id}] {subject} | {sender} | {date_str}"
                output_lines.append(line)
            
            if len(account_emails) > 50:
                output_lines.append(f"  ... 还有 {len(account_emails) - 50} 封")
            
            output_lines.append("")  # Empty line between accounts
        
        # Add performance info if available
        if 'fetch_time' in result:
            output_lines.append(f"⏱️ 耗时 {result['fetch_time']:.1f}秒")
        
        return [{
            "type": "text",
            "text": "\n".join(output_lines).strip()
        }]
    
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