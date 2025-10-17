"""
Organization tool handlers - Folders, flags, attachments
Uses service layer to reduce coupling with implementation details
"""
import logging
from typing import Dict, Any, List
from .tool_handlers import ToolContext
from ..operations.contact_analysis import analyze_contacts, get_contact_timeline

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
    
    @staticmethod
    def handle_analyze_contacts(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle analyze_contacts tool"""
        try:
            result = analyze_contacts(
                account_id=args.get('account_id'),
                days=args.get('days', 30),
                limit=args.get('limit', 10),
                group_by=args.get('group_by', 'both')
            )
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            # Format analysis results
            text = "📊 **Contact Frequency Analysis**\n\n"
            
            # Period info
            period = result['analysis_period']
            text += f"**Analysis Period**: Last {period['days']} days\n"
            text += f"**Account**: {result['account_id']}\n"
            text += f"**Total Emails Analyzed**: {result['total_emails_analyzed']}\n\n"
            
            # Top senders
            if 'top_senders' in result:
                text += "**📨 Top Senders:**\n"
                for i, sender in enumerate(result['top_senders'], 1):
                    text += f"{i}. {sender['email']}\n"
                    text += f"   {sender['count']} emails ({sender['percentage']}%)\n"
                text += "\n"
            
            # Top recipients
            if 'top_recipients' in result:
                text += "**📤 Top Recipients:**\n"
                for i, recipient in enumerate(result['top_recipients'], 1):
                    text += f"{i}. {recipient['email']}\n"
                    text += f"   {recipient['count']} emails ({recipient['percentage']}%)\n"
                text += "\n"
            
            # Summary
            summary = result['summary']
            text += "**📈 Summary:**\n"
            text += f"- Unique Senders: {summary['unique_senders']}\n"
            text += f"- Unique Recipients: {summary['unique_recipients']}\n"
            text += f"- Avg Emails/Sender: {summary['avg_emails_per_sender']}\n"
            text += f"- Avg Emails/Recipient: {summary['avg_emails_per_recipient']}\n"
            
            return [{"type": "text", "text": text}]
            
        except Exception as e:
            logger.error(f"Analyze contacts failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_get_contact_timeline(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle get_contact_timeline tool"""
        try:
            result = get_contact_timeline(
                contact_email=args['contact_email'],
                account_id=args.get('account_id'),
                days=args.get('days', 90)
            )
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            # Format timeline
            text = f"📅 **Communication Timeline: {result['contact_email']}**\n\n"
            text += f"**Account**: {result['account_id']}\n"
            text += f"**Total Interactions**: {result['total_interactions']}\n\n"
            
            if not result['timeline']:
                text += "No recent interactions found.\n"
            else:
                text += "**Recent Interactions:**\n\n"
                for item in result['timeline'][:20]:  # Show last 20
                    direction = "📨 Received" if item['direction'] == 'received' else "📤 Sent"
                    status = "✅" if item['is_read'] else "📬"
                    text += f"{direction} {status} - {item['date']}\n"
                    text += f"  {item['subject']}\n\n"
                
                if len(result['timeline']) > 20:
                    text += f"... and {len(result['timeline']) - 20} more interactions\n"
            
            return [{"type": "text", "text": text}]
            
        except Exception as e:
            logger.error(f"Get contact timeline failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
