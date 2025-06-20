"""
Database integration for MCP Email Service
Shows how to use the local SQLite database for improved performance
"""
import logging
from typing import Dict, Any, List, Optional

from database import EmailDatabase, SyncManager
from account_manager import AccountManager
from mcp_tools import MCPTools

logger = logging.getLogger(__name__)

class DatabaseIntegratedEmailService:
    """Email service with local database caching"""
    
    def __init__(self):
        self.account_manager = AccountManager()
        self.db = EmailDatabase()
        self.sync_manager = SyncManager(self.db, self.account_manager)
        
        # Initialize database with existing accounts
        self._init_accounts()
        
        # Start auto sync
        self.sync_manager.start_auto_sync()
    
    def _init_accounts(self):
        """Initialize database with configured accounts"""
        accounts = self.account_manager.list_accounts()
        for account in accounts:
            self.db.upsert_account(account)
    
    def list_emails_cached(self, 
                          limit: int = 50,
                          unread_only: bool = False,
                          folder: Optional[str] = None,
                          account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        List emails from local database (fast)
        Falls back to remote fetch if database is empty
        """
        # Try database first
        emails = self.db.get_email_list(
            account_id=account_id,
            folder=folder,
            unread_only=unread_only,
            limit=limit
        )
        
        if emails:
            # Get account statistics
            stats = self._get_account_stats(account_id)
            
            return {
                'emails': emails,
                'total_emails': stats['total_emails'],
                'total_unread': stats['total_unread'],
                'accounts_count': stats['accounts_count'],
                'source': 'cache'
            }
        else:
            # Database empty, trigger sync
            logger.info("Database empty, triggering sync...")
            self.sync_manager.sync_all_accounts()
            
            # Try again from database
            emails = self.db.get_email_list(
                account_id=account_id,
                folder=folder,
                unread_only=unread_only,
                limit=limit
            )
            
            if emails:
                stats = self._get_account_stats(account_id)
                return {
                    'emails': emails,
                    'total_emails': stats['total_emails'],
                    'total_unread': stats['total_unread'],
                    'accounts_count': stats['accounts_count'],
                    'source': 'cache_after_sync'
                }
            else:
                # Fall back to direct fetch
                from legacy_operations import fetch_emails
                return fetch_emails(limit, unread_only, folder, account_id)
    
    def search_emails_cached(self,
                            query: str,
                            account_id: Optional[str] = None,
                            limit: int = 50) -> Dict[str, Any]:
        """
        Search emails using local database (fast)
        Uses FTS5 full-text search if available
        """
        emails = self.db.search_emails(query, account_id, limit)
        
        return {
            'emails': emails,
            'total_found': len(emails),
            'source': 'cache'
        }
    
    def get_email_detail_cached(self, email_id: str) -> Dict[str, Any]:
        """
        Get email details from cache, sync body if needed
        """
        # Parse email_id (format: accountId_folderId_uid)
        parts = email_id.split('_')
        if len(parts) < 3:
            return {'error': 'Invalid email ID format'}
        
        # Find email in database
        cursor = self.db.conn.execute("""
            SELECT id FROM emails 
            WHERE account_id = ? AND folder_id = ? AND uid = ?
        """, (parts[0], int(parts[1]), int(parts[2])))
        
        row = cursor.fetchone()
        if not row:
            # Not in cache, fall back to remote
            from legacy_operations import get_email_detail
            return get_email_detail(email_id)
        
        db_email_id = row[0]
        email = self.db.get_email_detail(db_email_id)
        
        if not email:
            return {'error': 'Email not found'}
        
        # Check if we have the body
        if not email.get('body_text') and not email.get('body_html'):
            # Sync body on demand
            logger.info(f"Syncing body for email {db_email_id}")
            if self.sync_manager.sync_email_body(db_email_id):
                # Reload with body
                email = self.db.get_email_detail(db_email_id)
        
        return email
    
    def _get_account_stats(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """Get email statistics from database"""
        if account_id:
            cursor = self.db.conn.execute("""
                SELECT COUNT(*) as total, 
                       SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread
                FROM emails WHERE account_id = ?
            """, (account_id,))
            row = cursor.fetchone()
            return {
                'total_emails': row[0],
                'total_unread': row[1] or 0,
                'accounts_count': 1
            }
        else:
            cursor = self.db.conn.execute("""
                SELECT COUNT(DISTINCT account_id) as accounts,
                       COUNT(*) as total,
                       SUM(CASE WHEN is_read = 0 THEN 1 ELSE 0 END) as unread
                FROM emails
            """)
            row = cursor.fetchone()
            return {
                'accounts_count': row[0],
                'total_emails': row[1],
                'total_unread': row[2] or 0
            }
    
    def mark_email_cached(self, email_id: str, is_read: bool) -> Dict[str, Any]:
        """
        Mark email as read/unread
        Updates cache immediately and queues remote update
        """
        # Update local database first
        parts = email_id.split('_')
        if len(parts) >= 3:
            cursor = self.db.conn.execute("""
                SELECT id FROM emails 
                WHERE account_id = ? AND folder_id = ? AND uid = ?
            """, (parts[0], int(parts[1]), int(parts[2])))
            
            row = cursor.fetchone()
            if row:
                self.db.update_email_flags(row[0], is_read=is_read)
        
        # Then update remote
        from legacy_operations import mark_email_read
        from operations.email_operations import EmailOperations
        from connection_manager import ConnectionManager
        
        account_id = parts[0] if parts else None
        account = self.account_manager.get_account(account_id)
        
        if is_read:
            return mark_email_read(email_id)
        else:
            conn_mgr = ConnectionManager(account)
            email_ops = EmailOperations(conn_mgr)
            return email_ops.mark_email_unread(email_id)
    
    def sync_now(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Trigger manual synchronization
        """
        if account_id:
            return self.sync_manager.sync_account(account_id)
        else:
            return self.sync_manager.sync_all_accounts()
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status and statistics"""
        stats = self.db.get_stats()
        
        # Add human-readable sizes
        stats['db_size_mb'] = stats['db_size_bytes'] / (1024 * 1024)
        
        # Get recent sync log
        cursor = self.db.conn.execute("""
            SELECT a.email, s.* 
            FROM sync_log s
            JOIN accounts a ON s.account_id = a.id
            ORDER BY s.end_time DESC
            LIMIT 10
        """)
        
        stats['recent_syncs'] = [dict(row) for row in cursor.fetchall()]
        
        return stats
    
    def cleanup(self):
        """Cleanup resources"""
        self.sync_manager.stop_auto_sync()
        self.db.close()


# Example integration with MCP tools
def create_cached_mcp_tools():
    """
    Create MCP tools that use cached database
    Returns modified tool handlers
    """
    service = DatabaseIntegratedEmailService()
    
    # Override list_emails to use cache
    def list_emails_handler(args, context):
        result = service.list_emails_cached(
            limit=args.get('limit', 50),
            unread_only=args.get('unread_only', False),
            folder=args.get('folder'),
            account_id=args.get('account_id')
        )
        
        # Format for MCP response
        if 'error' in result:
            return [{"type": "text", "text": f"Error: {result['error']}"}]
        
        # Include cache info
        cache_info = f" (from {result.get('source', 'remote')})" if 'source' in result else ""
        
        text = f"Found {len(result['emails'])} emails{cache_info}\\n\\n"
        for email in result['emails']:
            text += f"{'[UNREAD] ' if email.get('unread') else ''}{email['subject']}\\n"
            text += f"  From: {email['from']}\\n"
            text += f"  Date: {email['date']}\\n\\n"
        
        return [{"type": "text", "text": text}]
    
    # Override search_emails to use cache
    def search_emails_handler(args, context):
        result = service.search_emails_cached(
            query=args.get('query', ''),
            account_id=args.get('account_id'),
            limit=args.get('limit', 50)
        )
        
        if 'error' in result:
            return [{"type": "text", "text": f"Error: {result['error']}"}]
        
        cache_info = f" (from {result.get('source', 'remote')})" if 'source' in result else ""
        
        text = f"Found {len(result['emails'])} emails{cache_info}\\n\\n"
        for email in result['emails']:
            text += f"{email['subject']}\\n"
            text += f"  From: {email['from']}\\n\\n"
        
        return [{"type": "text", "text": text}]
    
    return {
        'list_emails': list_emails_handler,
        'search_emails': search_emails_handler,
        'sync_now': lambda args, ctx: [{"type": "text", "text": str(service.sync_now(args.get('account_id')))}],
        'sync_status': lambda args, ctx: [{"type": "text", "text": str(service.get_sync_status())}]
    }


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Create service
    service = DatabaseIntegratedEmailService()
    
    # Initial sync
    print("Starting initial sync...")
    result = service.sync_now()
    print(f"Synced {result['total_synced']} emails")
    
    # List emails from cache
    print("\\nListing emails from cache:")
    emails = service.list_emails_cached(limit=10, unread_only=True)
    print(f"Found {len(emails['emails'])} unread emails (source: {emails.get('source', 'unknown')})")
    
    # Search emails
    print("\\nSearching emails:")
    results = service.search_emails_cached("important")
    print(f"Found {len(results['emails'])} emails matching 'important'")
    
    # Get stats
    print("\\nDatabase statistics:")
    stats = service.get_sync_status()
    print(f"Total accounts: {stats['total_accounts']}")
    print(f"Total emails: {stats['total_emails']}")
    print(f"Total unread: {stats['total_unread']}")
    print(f"Database size: {stats['db_size_mb']:.2f} MB")
    
    # Cleanup
    service.cleanup()