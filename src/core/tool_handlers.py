"""
Tool handlers implementation - Business logic for each MCP tool
Uses service layer to reduce coupling with implementation details
"""
import logging
from typing import Dict, Any, List, Optional
from ..account_manager import AccountManager
from ..services.email_service import EmailService
import sqlite3

logger = logging.getLogger(__name__)

class ToolContext:
    """Context passed to tool handlers"""
    def __init__(self, account_manager: AccountManager, messages_func):
        self.account_manager = account_manager
        self.get_message = messages_func
        # Initialize all services
        from ..services import (
            EmailService, 
            CommunicationService, 
            FolderService, 
            SystemService
        )
        self.email_service = EmailService(account_manager)
        self.communication_service = CommunicationService(account_manager)
        self.folder_service = FolderService(account_manager)
        self.system_service = SystemService(account_manager)

class EmailToolHandlers:
    """Handlers for email-related tools"""
    
    @staticmethod
    def handle_list_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle list_emails tool"""
        try:
            result = ctx.email_service.list_emails(
                limit=args.get('limit', 100),
                unread_only=args.get('unread_only', True),
                folder=args.get('folder', 'all'),
                account_id=args.get('account_id'),
                offset=args.get('offset', 0),
                include_metadata=args.get('include_metadata', True),
                use_cache=args.get('use_cache', True)
            )
            
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
            result = ctx.email_service.get_email_detail(
                email_id=args['email_id'],
                folder=args.get('folder', 'INBOX'),
                account_id=args.get('account_id')
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
            result = ctx.email_service.mark_emails(
                email_ids=args['email_ids'],
                mark_as=args['mark_as'],
                folder=args.get('folder', 'INBOX'),
                account_id=args.get('account_id'),
                dry_run=args.get('dry_run', False),
                email_accounts=args.get('email_accounts')
            )
            
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
            result = ctx.email_service.delete_emails(
                email_ids=args['email_ids'],
                folder=args.get('folder', 'INBOX'),
                permanent=args.get('permanent', False),
                trash_folder=args.get('trash_folder', 'Trash'),
                account_id=args.get('account_id'),
                dry_run=args.get('dry_run', False),
                email_accounts=args.get('email_accounts')
            )
            
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
            result = ctx.email_service.search_emails(
                query=args.get('query'),
                search_in=args.get('search_in', 'all'),
                date_from=args.get('date_from'),
                date_to=args.get('date_to'),
                folder=args.get('folder', 'all'),
                unread_only=args.get('unread_only', False),
                has_attachments=args.get('has_attachments'),
                limit=args.get('limit', 50),
                account_id=args.get('account_id'),
                offset=args.get('offset', 0)
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
        if result.get('skip_summary'):
            summary_needed = False
        else:
            summary_needed = True
        
        total_emails = result.get('total_emails', result.get('total_in_folder'))
        total_unread = result.get('total_unread', result.get('unread_count'))
        offset = result.get('offset')
        
        # Summary
        if summary_needed:
            if 'accounts_count' in result:
                summary = ctx.get_message(
                    'found_emails',
                    len(emails),
                    total_emails or 0,
                    total_unread or 0
                )
                if offset is not None:
                    summary += f" (offset {offset})"
                response.append({"type": "text", "text": summary})
                
                if result['accounts_count'] > 0:
                    response.append({
                        "type": "text",
                        "text": ctx.get_message('from_accounts', result['accounts_count'])
                    })
            elif total_emails is not None or total_unread is not None:
                summary = ctx.get_message(
                    'found_emails',
                    len(emails),
                    total_emails or len(emails),
                    total_unread or 0
                )
                if offset is not None:
                    summary += f" (offset {offset})"
                response.append({"type": "text", "text": summary})
            elif offset is not None:
                response.append({
                    "type": "text",
                    "text": f"Showing {len(emails)} email(s) (offset {offset})"
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
            if email.get('folder'):
                email_info += f"\n  Folder: {email['folder']}"
            if email.get('source'):
                email_info += f"\n  Source: {email['source']}"
            
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
        email_list_result = EmailToolHandlers._format_email_list({'emails': emails, 'skip_summary': True}, ctx)
        
        # If email_list_result has summary, skip it; otherwise keep all items
        if len(email_list_result) > 1:
            # Has summary, skip the first item
            return response + email_list_result[1:]
        else:
            # No summary, keep all items
            return response + email_list_result
    
    @staticmethod
    def handle_list_unread_folders(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle list_unread_folders tool - Return unread count per folder"""
        try:
            result = ctx.folder_service.list_folders_with_unread_count(
                account_id=args.get('account_id'),
                include_empty=args.get('include_empty', False)
            )
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            return EmailToolHandlers._format_unread_folders(result, ctx)
            
        except Exception as e:
            logger.error(f"List unread folders failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_get_email_headers(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle get_email_headers tool - Get only email headers without body"""
        try:
            result = ctx.email_service.get_email_headers(
                email_id=args['email_id'],
                folder=args.get('folder', 'INBOX'),
                account_id=args.get('account_id'),
                headers=args.get('headers')
            )
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            return EmailToolHandlers._format_email_headers(result, ctx)
            
        except Exception as e:
            logger.error(f"Get email headers failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_get_recent_activity(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle get_recent_activity tool - Get recent sync/connection activity"""
        try:
            result = ctx.system_service.get_recent_activity(
                account_id=args.get('account_id'),
                include_stats=args.get('include_stats', True)
            )
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            return EmailToolHandlers._format_recent_activity(result, ctx)
            
        except Exception as e:
            logger.error(f"Get recent activity failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def _format_unread_folders(result: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Format unread folders result"""
        folders = result.get('folders', [])
        
        if not folders:
            return [{"type": "text", "text": "No folders found"}]
        
        response = []
        
        # Summary
        total_unread = sum(f.get('unread_count', 0) for f in folders)
        summary = f"📁 Folders with unread emails (Total: {total_unread} unread)\n\n"
        
        folder_lines = []
        for folder in folders:
            folder_name = folder.get('name', 'Unknown')
            unread_count = folder.get('unread_count', 0)
            total_count = folder.get('total_count', 0)
            account = folder.get('account', 'Unknown')
            
            marker = "🔴" if unread_count > 0 else "⚪"
            folder_lines.append(
                f"{marker} {folder_name}: {unread_count} unread / {total_count} total ({account})"
            )
        
        response.append({
            "type": "text",
            "text": summary + "\n".join(folder_lines)
        })
        
        return response
    
    @staticmethod
    def _format_email_headers(result: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Format email headers result"""
        headers = result.get('headers', {})
        
        if not headers:
            return [{"type": "text", "text": "No headers found"}]
        
        header_lines = ["📋 Email Headers:\n"]
        for key, value in headers.items():
            header_lines.append(f"  {key}: {value}")
        
        # Add metadata
        if 'source' in result:
            header_lines.append(f"\n  Source: {result['source']}")
        if 'folder' in result:
            header_lines.append(f"  Folder: {result['folder']}")
        if 'account_id' in result:
            header_lines.append(f"  Account: {result['account_id']}")
        
        return [{"type": "text", "text": "\n".join(header_lines)}]
    
    @staticmethod
    def _format_recent_activity(result: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Format recent activity result"""
        accounts = result.get('accounts', [])
        
        if not accounts:
            return [{"type": "text", "text": "No recent activity found"}]
        
        response = []
        summary_lines = ["⏱️  Recent Email Activity:\n"]
        
        for acc in accounts:
            account_name = acc.get('account', 'Unknown')
            last_sync = acc.get('last_sync', 'Never')
            last_error = acc.get('last_error')
            success_rate = acc.get('success_rate', 0)
            
            status = "✅" if not last_error else "⚠️"
            summary_lines.append(
                f"{status} {account_name}:"
            )
            summary_lines.append(f"  Last Sync: {last_sync}")
            
            if last_error:
                summary_lines.append(f"  Last Error: {last_error}")
            
            if acc.get('include_stats'):
                summary_lines.append(f"  Success Rate: {success_rate:.1f}%")
                if 'total_syncs' in acc:
                    summary_lines.append(f"  Total Syncs: {acc['total_syncs']}")
            
            summary_lines.append("")  # Empty line between accounts
        
        response.append({"type": "text", "text": "\n".join(summary_lines)})
        
        return response
