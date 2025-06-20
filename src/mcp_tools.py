"""
MCP tool definitions and handlers - Refactored clean version
"""
import logging
import os
import asyncio
from typing import Dict, Any, List, Optional

from core.tool_registry import tool_registry
from core.tool_schemas import *
from core.tool_handlers import ToolContext, EmailToolHandlers
from core.communication_handlers import CommunicationHandlers
from core.organization_handlers import OrganizationHandlers
from core.system_handlers import SystemHandlers
from account_manager import AccountManager

logger = logging.getLogger(__name__)

# Multi-language support
MESSAGES = {
    'zh': {
        'no_email': '📭 没有找到邮件',
        'email_sent': '✅ 邮件发送成功，已发送给 {} 个收件人',
        'error': '❌ 错误：',
        'operation_failed': '❌ 操作失败：',
        'operation_success': '✅ 操作成功完成',
        'found_emails': '📧 找到 {} 封邮件 (总计 {} 封，未读 {} 封)',
        'from_accounts': '📊 来自 {} 个邮箱账户',
        'unread_mark': '🔴 ',
        'read_mark': '📧 ',
        'from': '📤 ',
        'date': '📅 ',
        'id': '🆔 ',
        'account': '📮 ',
        'fetch_time': '⏱️ 获取耗时：{:.2f} 秒',
        'failed_accounts': '⚠️ 部分账户获取失败：',
        'account_stats': '📊 各账户统计：',
        'emails_count': '{} 封 (总 {}, 未读 {})',
        'found_folders': '📁 找到 {} 个文件夹',
        'messages': '条消息'
    },
    'en': {
        'no_email': '📭 No emails found',
        'email_sent': '✅ Email sent successfully to {} recipient(s)',
        'error': '❌ Error: ',
        'operation_failed': '❌ Operation failed: ',
        'operation_success': '✅ Operation completed successfully',
        'found_emails': '📧 Found {} emails (total: {}, unread: {})',
        'from_accounts': '📊 From {} email accounts',
        'unread_mark': '🔴 ',
        'read_mark': '📧 ',
        'from': '📤 ',
        'date': '📅 ',
        'id': '🆔 ',
        'account': '📮 ',
        'fetch_time': '⏱️ Fetch time: {:.2f} seconds',
        'failed_accounts': '⚠️ Failed to fetch from some accounts:',
        'account_stats': '📊 Account statistics:',
        'emails_count': '{} emails (total: {}, unread: {})',
        'found_folders': '📁 Found {} folders',
        'messages': 'messages'
    }
}

def get_user_language():
    """Get user's preferred language from environment or default to Chinese"""
    lang = os.getenv('MCP_LANGUAGE', 'zh')
    return lang

def get_message(key: str, *args, **kwargs):
    """Get localized message"""
    lang = get_user_language()
    messages = MESSAGES.get(lang, MESSAGES['zh'])
    msg = messages.get(key, key)
    if args or kwargs:
        return msg.format(*args, **kwargs)
    return msg

class MCPTools:
    """Refactored MCP tools with clean architecture"""
    
    def __init__(self, server):
        self.server = server
        self.account_manager = AccountManager()
        self.context = ToolContext(self.account_manager, get_message)
        self._register_all_tools()
        self._setup_server_handlers()
    
    def _register_all_tools(self):
        """Register all tools with their handlers"""
        
        # Email tools
        tool_registry.register(
            "list_emails",
            "List emails from inbox (supports multi-account). Returns newest emails first. For unread emails, automatically checks multiple folders.",
            LIST_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_list_emails)
        
        tool_registry.register(
            "get_email_detail",
            "Get detailed content of a specific email including body and attachments",
            GET_EMAIL_DETAIL_SCHEMA
        )(EmailToolHandlers.handle_get_email_detail)
        
        tool_registry.register(
            "mark_emails",
            "Mark one or more emails as read or unread",
            MARK_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_mark_emails)
        
        tool_registry.register(
            "delete_emails",
            "Delete one or more emails (move to trash or permanently delete)",
            DELETE_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_delete_emails)
        
        tool_registry.register(
            "search_emails",
            "Search emails with various criteria across all accounts or specific account",
            SEARCH_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_search_emails)
        
        # Communication tools
        tool_registry.register(
            "send_email",
            "Send a new email with optional attachments",
            SEND_EMAIL_SCHEMA
        )(CommunicationHandlers.handle_send_email)
        
        tool_registry.register(
            "reply_email",
            "Reply to an email (preserves thread)",
            REPLY_EMAIL_SCHEMA
        )(CommunicationHandlers.handle_reply_email)
        
        tool_registry.register(
            "forward_email",
            "Forward an email to other recipients",
            FORWARD_EMAIL_SCHEMA
        )(CommunicationHandlers.handle_forward_email)
        
        # Organization tools
        tool_registry.register(
            "list_folders",
            "List all email folders/labels in the account",
            LIST_FOLDERS_SCHEMA
        )(OrganizationHandlers.handle_list_folders)
        
        tool_registry.register(
            "move_emails_to_folder",
            "Move emails to a different folder",
            MOVE_EMAILS_TO_FOLDER_SCHEMA
        )(OrganizationHandlers.handle_move_emails_to_folder)
        
        tool_registry.register(
            "flag_email",
            "Flag/star or unflag an email",
            FLAG_EMAIL_SCHEMA
        )(OrganizationHandlers.handle_flag_email)
        
        tool_registry.register(
            "get_email_attachments",
            "Extract attachments from an email",
            GET_EMAIL_ATTACHMENTS_SCHEMA
        )(OrganizationHandlers.handle_get_email_attachments)
        
        # System tools
        tool_registry.register(
            "check_connection",
            "Test email server connections (IMAP and SMTP) for all configured accounts",
            CHECK_CONNECTION_SCHEMA
        )(SystemHandlers.handle_check_connection)
        
        tool_registry.register(
            "list_accounts",
            "List all configured email accounts",
            LIST_ACCOUNTS_SCHEMA
        )(SystemHandlers.handle_list_accounts)
    
    def _setup_server_handlers(self):
        """Setup MCP server handlers"""
        
        @self.server.list_tools()
        async def handle_list_tools():
            return tool_registry.list_tools()
        
        @self.server.call_tool()
        async def handle_call_tool(name, arguments):
            return await self.call_tool(name, arguments)
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Call a registered tool"""
        try:
            logger.info(f"Calling tool: {name}")
            
            # Get handler from registry
            handler = tool_registry.get_handler(name)
            if not handler:
                return [{
                    "type": "text",
                    "text": f"Unknown tool: {name}"
                }]
            
            # Call handler with context
            if asyncio.iscoroutinefunction(handler):
                result = await handler(arguments, self.context)
            else:
                result = handler(arguments, self.context)
            
            return result
            
        except Exception as e:
            logger.error(f"Tool {name} failed with error: {e}", exc_info=True)
            return [{
                "type": "text",
                "text": f"{get_message('operation_failed')}{str(e)}"
            }]