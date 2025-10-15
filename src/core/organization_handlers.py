"""
Organization tool handlers - Folders, flags, attachments
Uses service layer to reduce coupling with implementation details
"""
import logging
from typing import Dict, Any, List
from .tool_handlers import ToolContext

logger = logging.getLogger(__name__)

class OrganizationHandlers:
    """Handlers for email organization tools"""
    
    @staticmethod
    def handle_list_folders(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle list_folders tool"""
        try:
            result = ctx.folder_service.list_folders(args.get('account_id'))
            
            if result.get('success'):
                folders = result.get('folders', [])
                
                if not folders:
                    return [{"type": "text", "text": "No folders found"}]
                
                # Format folder list
                text = ctx.get_message('found_folders', len(folders)) + "\n\n"
                
                for folder in folders:
                    # Show folder hierarchy
                    indent = "  " * folder.get('level', 0)
                    folder_name = folder['name']
                    
                    # Add message count if available
                    if 'message_count' in folder:
                        folder_name += f" ({folder['message_count']} {ctx.get_message('messages')})"
                    
                    text += f"{indent}📁 {folder_name}\n"
                
                return [{"type": "text", "text": text}]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result.get('error', 'List folders failed')}"
                }]
                
        except Exception as e:
            logger.error(f"List folders failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_move_emails_to_folder(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle move_emails_to_folder tool"""
        try:
            result = ctx.folder_service.move_emails_to_folder(
                email_ids=args['email_ids'],
                target_folder=args['target_folder'],
                source_folder=args.get('source_folder', 'INBOX'),
                account_id=args.get('account_id')
            )
            
            if result.get('success'):
                return [{
                    "type": "text",
                    "text": ctx.get_message('operation_success')
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('operation_failed')}{result.get('error', 'Move failed')}"
                }]
                
        except Exception as e:
            logger.error(f"Move emails to folder failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_flag_email(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle flag_email tool"""
        try:
            result = ctx.folder_service.flag_email(
                email_id=args['email_id'],
                flag_type=args['flag_type'],
                set_flag=args.get('set_flag', True),
                folder=args.get('folder', 'INBOX'),
                account_id=args.get('account_id')
            )
            
            if result.get('success'):
                return [{
                    "type": "text",
                    "text": ctx.get_message('operation_success')
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('operation_failed')}{result.get('error', 'Flag operation failed')}"
                }]
                
        except Exception as e:
            logger.error(f"Flag email failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_get_email_attachments(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle get_email_attachments tool"""
        try:
            result = ctx.folder_service.get_email_attachments(
                email_id=args['email_id'],
                folder=args.get('folder', 'INBOX'),
                account_id=args.get('account_id')
            )
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            attachments = result.get('attachments', [])
            
            if not attachments:
                return [{"type": "text", "text": "No attachments found"}]
            
            # Format attachment list
            text = f"Found {len(attachments)} attachment(s):\n\n"
            
            for att in attachments:
                text += f"📎 **{att['filename']}**\n"
                text += f"   Type: {att.get('content_type', 'unknown')}\n"
                text += f"   Size: {att.get('size', 'unknown')}\n"
                if att.get('content'):
                    text += f"   Content: Available (base64 encoded)\n"
                text += "\n"
            
            return [{"type": "text", "text": text}]
            
        except Exception as e:
            logger.error(f"Get email attachments failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
