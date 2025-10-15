"""
Communication tool handlers - Send, reply, forward emails
Uses service layer to reduce coupling with implementation details
"""
import logging
from typing import Dict, Any, List
from .tool_handlers import ToolContext

logger = logging.getLogger(__name__)

class CommunicationHandlers:
    """Handlers for email communication tools"""
    
    @staticmethod
    def handle_send_email(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle send_email tool"""
        try:
            result = ctx.communication_service.send_email(
                to=args['to'],
                subject=args['subject'],
                body=args['body'],
                cc=args.get('cc'),
                bcc=args.get('bcc'),
                attachments=args.get('attachments'),
                is_html=args.get('is_html', False),
                account_id=args.get('account_id')
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
            result = ctx.communication_service.reply_email(
                email_id=args['email_id'],
                body=args['body'],
                reply_all=args.get('reply_all', False),
                folder=args.get('folder', 'INBOX'),
                attachments=args.get('attachments'),
                is_html=args.get('is_html', False),
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
            result = ctx.communication_service.forward_email(
                email_id=args['email_id'],
                to=args['to'],
                body=args.get('body'),
                folder=args.get('folder', 'INBOX'),
                include_attachments=args.get('include_attachments', True),
                account_id=args.get('account_id')
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
