"""
Communication tool handlers - Send, reply, forward emails
"""
import logging
from typing import Dict, Any, List, Optional
from legacy_operations import get_email_detail
from operations.smtp_operations import SMTPOperations
from core.tool_handlers import ToolContext

logger = logging.getLogger(__name__)

class CommunicationHandlers:
    """Handlers for email communication tools"""
    
    @staticmethod
    def handle_send_email(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle send_email tool"""
        try:
            conn_mgr = ctx.get_connection_manager(args.get('account_id'))
            smtp_ops = SMTPOperations(conn_mgr)
            
            result = smtp_ops.send_email(
                to=args['to'],
                subject=args['subject'],
                body=args['body'],
                cc=args.get('cc'),
                bcc=args.get('bcc'),
                attachments=args.get('attachments'),
                is_html=args.get('is_html', False)
            )
            
            if result.get('success'):
                recipient_count = len(args['to']) + len(args.get('cc', [])) + len(args.get('bcc', []))
                return [{
                    "type": "text",
                    "text": ctx.get_message('email_sent', recipient_count)
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result.get('error', 'Send failed')}"
                }]
                
        except Exception as e:
            logger.error(f"Send email failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_reply_email(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle reply_email tool"""
        try:
            # First get the original email
            original = get_email_detail(
                args['email_id'],
                args.get('folder', 'INBOX'),
                args.get('account_id')
            )
            
            if 'error' in original:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{original['error']}"
                }]
            
            conn_mgr = ctx.get_connection_manager(args.get('account_id'))
            smtp_ops = SMTPOperations(conn_mgr)
            
            result = smtp_ops.reply_email(
                original_msg=original,
                body=args['body'],
                reply_all=args.get('reply_all', False),
                attachments=args.get('attachments'),
                is_html=args.get('is_html', False)
            )
            
            if result.get('success'):
                return [{
                    "type": "text",
                    "text": ctx.get_message('operation_success')
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result.get('error', 'Reply failed')}"
                }]
                
        except Exception as e:
            logger.error(f"Reply email failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_forward_email(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle forward_email tool"""
        try:
            # First get the original email
            original = get_email_detail(
                args['email_id'],
                args.get('folder', 'INBOX'),
                args.get('account_id')
            )
            
            if 'error' in original:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{original['error']}"
                }]
            
            conn_mgr = ctx.get_connection_manager(args.get('account_id'))
            smtp_ops = SMTPOperations(conn_mgr)
            
            # Build forward message
            forward_body = ""
            if args.get('body'):
                forward_body = args['body'] + "\n\n"
            
            forward_body += f"---------- Forwarded message ----------\n"
            forward_body += f"From: {original['from']}\n"
            forward_body += f"Date: {original['date']}\n"
            forward_body += f"Subject: {original['subject']}\n"
            forward_body += f"To: {original['to']}\n\n"
            forward_body += original.get('body', '')
            
            # Include attachments if requested
            attachments = None
            if args.get('include_attachments', True) and original.get('attachments'):
                attachments = original['attachments']
            
            result = smtp_ops.send_email(
                to=args['to'],
                subject=f"Fwd: {original['subject']}",
                body=forward_body,
                attachments=attachments,
                is_html=original.get('is_html', False)
            )
            
            if result.get('success'):
                return [{
                    "type": "text",
                    "text": ctx.get_message('email_sent', len(args['to']))
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result.get('error', 'Forward failed')}"
                }]
                
        except Exception as e:
            logger.error(f"Forward email failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]