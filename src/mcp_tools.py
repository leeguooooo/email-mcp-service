"""
MCP tool definitions and handlers - Refactored clean version
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional

from .core.tool_registry import tool_registry
from .core.tool_schemas import (
    LIST_EMAILS_SCHEMA,
    GET_EMAIL_DETAIL_SCHEMA,
    MARK_EMAILS_SCHEMA,
    MARK_EMAIL_READ_SCHEMA,
    MARK_EMAIL_UNREAD_SCHEMA,
    BATCH_MARK_READ_SCHEMA,
    DELETE_EMAIL_SCHEMA,
    DELETE_EMAILS_SCHEMA,
    BATCH_DELETE_EMAILS_SCHEMA,
    SEARCH_EMAILS_SCHEMA,
    SEND_EMAIL_SCHEMA,
    REPLY_EMAIL_SCHEMA,
    FORWARD_EMAIL_SCHEMA,
    LIST_FOLDERS_SCHEMA,
    MOVE_EMAILS_TO_FOLDER_SCHEMA,
    FLAG_EMAIL_SCHEMA,
    GET_EMAIL_ATTACHMENTS_SCHEMA,
    CHECK_CONNECTION_SCHEMA,
    LIST_ACCOUNTS_SCHEMA,
    ANALYZE_CONTACTS_SCHEMA,
    GET_CONTACT_TIMELINE_SCHEMA,
    LIST_UNREAD_FOLDERS_SCHEMA,
    GET_EMAIL_HEADERS_SCHEMA,
    GET_RECENT_ACTIVITY_SCHEMA,
    GET_VERSION_SCHEMA
)
from .core.tool_handlers import ToolContext, EmailToolHandlers
from .core.communication_handlers import CommunicationHandlers
from .core.organization_handlers import OrganizationHandlers
from .core.system_handlers import SystemHandlers
from .account_manager import AccountManager
from .config.messages import get_message

logger = logging.getLogger(__name__)

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
        
        def make_single_mark_handler(mark_as: str):
            """Create handler that marks a single email"""
            def handler(args: Dict[str, Any], ctx: ToolContext):
                payload = {
                    "email_ids": [args["email_id"]],
                    "mark_as": mark_as,
                    "folder": args.get("folder", "INBOX")
                }
                account_id = args.get("account_id")
                if account_id:
                    payload["account_id"] = account_id
                return EmailToolHandlers.handle_mark_emails(payload, ctx)
            return handler
        
        def make_batch_mark_handler(mark_as: str):
            """Create handler that marks multiple emails"""
            def handler(args: Dict[str, Any], ctx: ToolContext):
                payload = {
                    "email_ids": args["email_ids"],
                    "mark_as": mark_as,
                    "folder": args.get("folder", "INBOX")
                }
                account_id = args.get("account_id")
                if account_id:
                    payload["account_id"] = account_id
                return EmailToolHandlers.handle_mark_emails(payload, ctx)
            return handler
        
        def delete_single_handler(args: Dict[str, Any], ctx: ToolContext):
            """Delete a single email by delegating to batch handler"""
            payload = {
                "email_ids": [args["email_id"]],
                "folder": args.get("folder", "INBOX"),
                "permanent": args.get("permanent", False),
                "trash_folder": args.get("trash_folder", "Trash")
            }
            account_id = args.get("account_id")
            if account_id:
                payload["account_id"] = account_id
            return EmailToolHandlers.handle_delete_emails(payload, ctx)
        
        def batch_delete_handler(args: Dict[str, Any], ctx: ToolContext):
            """Delete multiple emails"""
            return EmailToolHandlers.handle_delete_emails(args, ctx)
        
        # Email tools
        tool_registry.register(
            "list_emails",
            "List emails from inbox (supports multi-account). UIDs are scoped to each account—pass account_id for deterministic follow-up actions. Performs live IMAP fetch; failures usually indicate network or credential issues.",
            LIST_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_list_emails)
        
        tool_registry.register(
            "get_email_detail",
            "Get detailed content of a specific email including body and attachments. Requires IMAP connectivity to download the latest message content.",
            GET_EMAIL_DETAIL_SCHEMA
        )(EmailToolHandlers.handle_get_email_detail)
        
        tool_registry.register(
            "mark_emails",
            "Mark one or more emails as read or unread. Pass account_id when operating within a single account, or provide email_accounts mapping for mixed-account batches.",
            MARK_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_mark_emails)
        
        tool_registry.register(
            "mark_email_read",
            "Mark a single email as read (account_id optional but recommended to avoid cross-account lookup).",
            MARK_EMAIL_READ_SCHEMA
        )(make_single_mark_handler("read"))
        
        tool_registry.register(
            "mark_email_unread",
            "Mark a single email as unread (account_id optional but recommended).",
            MARK_EMAIL_UNREAD_SCHEMA
        )(make_single_mark_handler("unread"))
        
        tool_registry.register(
            "batch_mark_read",
            "Mark multiple emails as read",
            BATCH_MARK_READ_SCHEMA
        )(make_batch_mark_handler("read"))
        
        tool_registry.register(
            "delete_emails",
            "Delete one or more emails (move to trash or permanently delete). Provide account_id or email_accounts mapping so each UID can be routed to the right mailbox.",
            DELETE_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_delete_emails)
        
        tool_registry.register(
            "delete_email",
            "Delete a single email (move to trash or permanently delete). account_id optional but recommended.",
            DELETE_EMAIL_SCHEMA
        )(delete_single_handler)
        
        tool_registry.register(
            "batch_delete_emails",
            "Delete multiple emails (move to trash or permanently delete)",
            BATCH_DELETE_EMAILS_SCHEMA
        )(batch_delete_handler)
        
        tool_registry.register(
            "search_emails",
            "Search emails with various criteria across all accounts or specific account. Returned UIDs must be used with the same account; specify account_id for precise targeting.",
            SEARCH_EMAILS_SCHEMA
        )(EmailToolHandlers.handle_search_emails)
        
        # Communication tools
        tool_registry.register(
            "send_email",
            "Send a new email with optional attachments via SMTP. Ensure the account has SMTP server configuration and valid credentials.",
            SEND_EMAIL_SCHEMA
        )(CommunicationHandlers.handle_send_email)
        
        tool_registry.register(
            "reply_email",
            "Reply to an email (preserves thread). Requires SMTP access for the originating account.",
            REPLY_EMAIL_SCHEMA
        )(CommunicationHandlers.handle_reply_email)
        
        tool_registry.register(
            "forward_email",
            "Forward an email to other recipients using SMTP credentials of the selected account.",
            FORWARD_EMAIL_SCHEMA
        )(CommunicationHandlers.handle_forward_email)
        
        # Organization tools
        tool_registry.register(
            "list_folders",
            "List all email folders/labels in the account (IMAP). Provide account_id to target a specific mailbox.",
            LIST_FOLDERS_SCHEMA
        )(OrganizationHandlers.handle_list_folders)
        
        tool_registry.register(
            "move_emails_to_folder",
            "Move emails to a different folder. Requires IMAP access; pass account_id (or use per-email mapping in mark/delete first) so UIDs match the correct account.",
            MOVE_EMAILS_TO_FOLDER_SCHEMA
        )(OrganizationHandlers.handle_move_emails_to_folder)
        
        tool_registry.register(
            "flag_email",
            "Flag/star or unflag an email. Runs against the live mailbox—account_id recommended to avoid cross-account lookups.",
            FLAG_EMAIL_SCHEMA
        )(OrganizationHandlers.handle_flag_email)
        
        tool_registry.register(
            "get_email_attachments",
            "Extract attachments from an email by downloading them over IMAP. Requires a reachable mailbox and may incur network latency.",
            GET_EMAIL_ATTACHMENTS_SCHEMA
        )(OrganizationHandlers.handle_get_email_attachments)
        
        # Contact Analysis tools
        tool_registry.register(
            "analyze_contacts",
            "Analyze contact frequency and communication patterns using the local sync database. Works only after emails have been synchronized to the cache.",
            ANALYZE_CONTACTS_SCHEMA
        )(OrganizationHandlers.handle_analyze_contacts)
        
        tool_registry.register(
            "get_contact_timeline",
            "Get communication timeline with a specific contact from the local sync cache (no live IMAP).",
            GET_CONTACT_TIMELINE_SCHEMA
        )(OrganizationHandlers.handle_get_contact_timeline)
        
        # New atomic tools for granular operations
        tool_registry.register(
            "list_unread_folders",
            "List folders with unread counts per configured account. Requires live IMAP connectivity; returns empty list when the mailbox cannot be reached.",
            LIST_UNREAD_FOLDERS_SCHEMA
        )(EmailToolHandlers.handle_list_unread_folders)
        
        tool_registry.register(
            "get_email_headers",
            "Fetch only email headers (From, To, Subject, Date, Message-ID, etc.) without downloading the body. account_id recommended so the UID lookup hits the right mailbox.",
            GET_EMAIL_HEADERS_SCHEMA
        )(EmailToolHandlers.handle_get_email_headers)
        
        tool_registry.register(
            "get_recent_activity",
            "Return recent sync activity/health per account based on local cache data.",
            GET_RECENT_ACTIVITY_SCHEMA
        )(EmailToolHandlers.handle_get_recent_activity)
        
        # System tools
        tool_registry.register(
            "check_connection",
            "Test email server connections (IMAP and SMTP) for all configured accounts using stored credentials.",
            CHECK_CONNECTION_SCHEMA
        )(SystemHandlers.handle_check_connection)
        
        tool_registry.register(
            "list_accounts",
            "List all configured email accounts",
            LIST_ACCOUNTS_SCHEMA
        )(SystemHandlers.handle_list_accounts)
        
        tool_registry.register(
            "get_version",
            "Get MCP Email Service version and git commit",
            GET_VERSION_SCHEMA
        )(SystemHandlers.handle_get_version)
        
        # Unified sync tool (optional dependency)
        try:
            from .core.sync_handlers import SyncHandlers
            from .core.tool_schemas import SYNC_EMAILS_SCHEMA, GET_SYNC_HEALTH_SCHEMA, GET_CONNECTION_POOL_STATS_SCHEMA, GET_SYNC_HISTORY_SCHEMA
            
            tool_registry.register(
                "sync_emails",
                "Unified email synchronization tool: start/stop scheduler, force sync, get status, search cache, manage config (action: start|stop|force|status|search|recent|config). Operates on the local sync service and databases.",
                SYNC_EMAILS_SCHEMA
            )(SyncHandlers.handle_sync_emails)
            
            # Sync health monitoring tools
            tool_registry.register(
                "get_sync_health",
                "Get sync health status for all accounts or a specific account based on cached sync metrics (no live IMAP).",
                GET_SYNC_HEALTH_SCHEMA
            )(SyncHandlers.handle_get_sync_health)
            
            tool_registry.register(
                "get_sync_history",
                "Get synchronization history for all accounts or a specific account within specified hours from the local sync logs.",
                GET_SYNC_HISTORY_SCHEMA
            )(SyncHandlers.handle_get_sync_history)
            
            tool_registry.register(
                "get_connection_pool_stats",
                "Get IMAP connection pool statistics from the local sync service, including connection reuse rate and active connections (no remote calls).",
                GET_CONNECTION_POOL_STATS_SCHEMA
            )(SyncHandlers.handle_get_connection_pool_stats)
        except (ModuleNotFoundError, ImportError) as exc:
            logger.warning("Skipping sync tool registration: %s", exc)

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return all registered tool definitions"""
        return [tool.model_dump() for tool in tool_registry.list_tools()]
    
    def _format_success_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Format a human-friendly success message for common tools"""
        if tool_name == "send_email":
            recipients = result.get('recipients') or result.get('to') or []
            if isinstance(recipients, int):
                recipient_count = recipients
            else:
                recipient_count = len(recipients)
            return get_message('email_sent', recipient_count)
        
        if tool_name == "search_emails":
            displayed = result.get('displayed')
            if displayed is None:
                displayed = len(result.get('emails', []))
            total = result.get('total_found', result.get('total', displayed))
            return f"Found {displayed} emails (total: {total})"
        
        if tool_name == "list_folders":
            folders = result.get('folders', [])
            lines = [f"Found {len(folders)} folders"]
            for folder in folders:
                folder_name = folder.get('name', 'Unknown')
                count = folder.get('message_count')
                if count is not None:
                    lines.append(f"{folder_name} ({count} messages)")
                else:
                    lines.append(folder_name)
            return "\n".join(lines)
        
        return get_message('operation_success')
    
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
