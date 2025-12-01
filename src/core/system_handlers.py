"""
System tool handlers - Account management, connection checks
Uses service layer to reduce coupling with implementation details
"""
import logging
import subprocess
from typing import Dict, Any, List
from pathlib import Path
from .tool_handlers import ToolContext

logger = logging.getLogger(__name__)

class SystemHandlers:
    """Handlers for system-related tools"""
    
    @staticmethod
    def handle_check_connection(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle check_connection tool"""
        try:
            result = ctx.system_service.check_connection()
            
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
                    if imap_status.get('success'):
                        text += f"  ✅ IMAP: Connected\n"
                    else:
                        text += f"  ❌ IMAP: {imap_status.get('error', 'Failed')}\n"
                    
                    # SMTP status
                    smtp_status = acc.get('smtp', {})
                    if smtp_status.get('success'):
                        text += f"  ✅ SMTP: Connected\n"
                    else:
                        text += f"  ❌ SMTP: {smtp_status.get('error', 'Failed')}\n"
                    
                    text += "\n"
                
                response.append({"type": "text", "text": text})
            else:
                # Single account
                text = f"📧 **{result.get('email', 'Unknown')}** ({result.get('provider', 'Unknown')})\n\n"
                
                # IMAP status
                imap_status = result.get('imap', {})
                if imap_status.get('success'):
                    text += f"✅ IMAP: Connected successfully\n"
                    if imap_status.get('mailbox_status'):
                        status = imap_status['mailbox_status']
                        text += f"   Total emails: {status.get('total', 0)}\n"
                        text += f"   Unread emails: {status.get('unread', 0)}\n"
                else:
                    text += f"❌ IMAP: {imap_status.get('error', 'Connection failed')}\n"
                
                # SMTP status
                smtp_status = result.get('smtp', {})
                if smtp_status.get('success'):
                    text += f"✅ SMTP: Connected successfully\n"
                else:
                    text += f"❌ SMTP: {smtp_status.get('error', 'Connection failed')}\n"
                
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
            result = ctx.system_service.list_accounts()
            
            if not result.get('success'):
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('error')}{result.get('error', 'Failed to list accounts')}"
                }]
            
            accounts = result.get('accounts', [])
            
            if not accounts:
                return [{"type": "text", "text": "No email accounts configured"}]
            
            # Format account list
            text = f"Found {len(accounts)} configured account(s):\n\n"
            
            for i, acc in enumerate(accounts, 1):
                text += f"{i}. **{acc['email']}**\n"
                text += f"   Provider: {acc['provider']}\n"
                if acc.get('imap_host'):
                    text += f"   IMAP: {acc['imap_host']}\n"
                if acc.get('smtp_host'):
                    text += f"   SMTP: {acc['smtp_host']}\n"
                text += "\n"
            
            return [{"type": "text", "text": text}]
            
        except Exception as e:
            logger.error(f"List accounts failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]

    @staticmethod
    def handle_get_version(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """Handle get_version tool"""
        try:
            from ..config.version import __version__
            version = __version__
            git_hash = "unknown"
            try:
                repo_root = Path(__file__).resolve().parent.parent
                git_hash = subprocess.check_output(
                    ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL
                ).decode().strip()
            except Exception:
                pass
            
            text = f"Version: {version}"
            if git_hash:
                text += f"\nGit: {git_hash}"
            return [{"type": "text", "text": text}]
        except Exception as e:
            logger.error(f"Get version failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
