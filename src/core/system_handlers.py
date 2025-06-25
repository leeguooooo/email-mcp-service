"""
System tool handlers - Account management, connection checks
"""
import logging
from typing import Dict, Any, List, Optional
from legacy_operations import check_connection
from core.tool_handlers import ToolContext

logger = logging.getLogger(__name__)

class SystemHandlers:
    """Handlers for system-related tools"""
    
    @staticmethod
    def handle_check_connection(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle check_connection tool"""
        try:
            result = check_connection()
            
            if 'error' in result:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result['error']}"
                }]
            
            # Format connection status
            response = []
            
            if 'accounts' in result:
                # Multiple accounts
                text = f"Checked {result.get('total_accounts', 0)} account(s):\n\n"
                
                for acc in result['accounts']:
                    text += f"📧 **{acc['email']}** ({acc['provider']})\n"
                    
                    # IMAP status
                    imap_status = acc.get('imap', {})
                    # Handle case where imap_status might be a string
                    if isinstance(imap_status, dict):
                        if imap_status.get('success'):
                            text += f"  ✅ IMAP: Connected\n"
                        else:
                            text += f"  ❌ IMAP: {imap_status.get('error', 'Failed')}\n"
                    else:
                        text += f"  ❌ IMAP: {imap_status}\n"
                    
                    # SMTP status
                    smtp_status = acc.get('smtp', {})
                    # Handle case where smtp_status might be a string
                    if isinstance(smtp_status, dict):
                        if smtp_status.get('success'):
                            text += f"  ✅ SMTP: Connected\n"
                        else:
                            text += f"  ❌ SMTP: {smtp_status.get('error', 'Failed')}\n"
                    else:
                        text += f"  ❌ SMTP: {smtp_status}\n"
                    
                    text += "\n"
                
                response.append({"type": "text", "text": text})
            else:
                # Single account
                text = f"📧 **{result.get('email', 'Unknown')}** ({result.get('provider', 'Unknown')})\n\n"
                
                # IMAP status
                imap_status = result.get('imap', {})
                if isinstance(imap_status, dict):
                    if imap_status.get('success'):
                        text += f"✅ IMAP: Connected successfully\n"
                        if imap_status.get('total_emails') is not None:
                            text += f"   Total emails: {imap_status.get('total_emails', 0)}\n"
                            text += f"   Unread emails: {imap_status.get('unread_emails', 0)}\n"
                    else:
                        text += f"❌ IMAP: {imap_status.get('error', 'Connection failed')}\n"
                else:
                    text += f"❌ IMAP: {imap_status}\n"
                
                # SMTP status
                smtp_status = result.get('smtp', {})
                if isinstance(smtp_status, dict):
                    if smtp_status.get('success'):
                        text += f"✅ SMTP: Connected successfully\n"
                    else:
                        text += f"❌ SMTP: {smtp_status.get('error', 'Connection failed')}\n"
                else:
                    text += f"❌ SMTP: {smtp_status}\n"
                
                response.append({"type": "text", "text": text})
            
            return response
            
        except Exception as e:
            logger.error(f"Check connection failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_list_accounts(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle list_accounts tool"""
        try:
            accounts = ctx.account_manager.list_accounts()
            
            if not accounts:
                return [{"type": "text", "text": "No email accounts configured"}]
            
            # Format account list
            text = f"Found {len(accounts)} configured account(s):\n\n"
            
            for i, acc in enumerate(accounts, 1):
                text += f"{i}. **{acc['email']}**\n"
                text += f"   Provider: {acc['provider']}\n"
                text += f"   ID: {acc['id']}\n"
                if acc.get('is_default'):
                    text += f"   ⭐ Default account\n"
                text += "\n"
            
            return [{"type": "text", "text": text}]
            
        except Exception as e:
            logger.error(f"List accounts failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]