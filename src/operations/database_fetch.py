"""
Database-based email fetching for accurate read/unread status
"""
import logging
from typing import Dict, Any, List
from datetime import datetime

from database.email_sync_db import EmailSyncDatabase

logger = logging.getLogger(__name__)

def fetch_emails_from_database(limit: int = 50, unread_only: bool = False, 
                              account_id: str = None) -> Dict[str, Any]:
    """
    Fetch emails directly from local database
    
    This is more accurate for read/unread status than IMAP
    """
    # 最少显示50封
    if limit < 50:
        limit = 50
    
    try:
        db = EmailSyncDatabase(use_pool=False)
        
        # Build query with deduplication
        sql = """
            WITH unique_emails AS (
                SELECT 
                    e.id, e.uid, e.message_id, e.subject, e.sender, e.sender_email,
                    e.recipients, e.date_sent, e.is_read, e.is_flagged,
                    e.has_attachments, e.size_bytes, e.account_id,
                    f.name as folder_name, a.email as account_email,
                    ROW_NUMBER() OVER (PARTITION BY e.message_id, e.account_id ORDER BY e.date_sent DESC) as rn
                FROM emails e
                JOIN folders f ON e.folder_id = f.id
                JOIN accounts a ON e.account_id = a.id
                WHERE e.is_deleted = FALSE
        """
        
        params = []
        
        if unread_only:
            sql += " AND e.is_read = FALSE"
        
        if account_id:
            sql += " AND e.account_id = ?"
            params.append(account_id)
        
        sql += """
            )
            SELECT * FROM unique_emails
            WHERE rn = 1
            ORDER BY date_sent DESC
            LIMIT ?
        """
        params.append(limit)
        
        results = db.execute(sql, tuple(params), commit=False)
        emails_data = [dict(row) for row in results.fetchall()]
        
        # Format emails to match expected structure
        emails = []
        for row in emails_data:
            # Format date
            date_sent = row.get('date_sent', '')
            if date_sent:
                try:
                    dt = datetime.fromisoformat(date_sent)
                    date_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    date_str = date_sent
            else:
                date_str = ''
            
            email = {
                'id': str(row.get('id', '')),  # Use database ID instead of UID
                'subject': row.get('subject', 'No subject'),
                'from': row.get('sender', 'Unknown'),
                'date': date_str,
                'unread': not row.get('is_read', True),
                'account': row.get('account_email', 'Unknown'),
                'has_attachments': row.get('has_attachments', False),
                'flagged': row.get('is_flagged', False),
                'folder': row.get('folder_name', 'INBOX')
            }
            emails.append(email)
        
        # Get total counts
        total_sql = """
            SELECT 
                COUNT(DISTINCT message_id || account_id) as total,
                SUM(CASE WHEN is_read = FALSE THEN 1 ELSE 0 END) as unread
            FROM emails
            WHERE is_deleted = FALSE
        """
        if account_id:
            total_sql += " AND account_id = ?"
            total_results = db.execute(total_sql, (account_id,), commit=False)
        else:
            total_results = db.execute(total_sql, commit=False)
        
        totals = total_results.fetchone()
        
        result = {
            'emails': emails,
            'total_emails': totals['total'] if totals else len(emails),
            'total_unread': totals['unread'] if totals else sum(1 for e in emails if e['unread']),
            'source': 'database',
            'fetch_time': 0.1  # Fast database fetch
        }
        
        # Add account info if fetching all accounts
        if not account_id:
            accounts_sql = """
                SELECT 
                    a.email,
                    COUNT(DISTINCT e.message_id) as total,
                    SUM(CASE WHEN e.is_read = FALSE THEN 1 ELSE 0 END) as unread
                FROM accounts a
                LEFT JOIN emails e ON a.id = e.account_id AND e.is_deleted = FALSE
                GROUP BY a.email
            """
            accounts_results = db.execute(accounts_sql, commit=False)
            accounts_info = []
            for acc in accounts_results.fetchall():
                accounts_info.append({
                    'account': acc['email'],
                    'total': acc['total'] or 0,
                    'unread': acc['unread'] or 0,
                    'fetched': len([e for e in emails if e['account'] == acc['email']])
                })
            
            result['accounts_count'] = len(accounts_info)
            result['accounts_info'] = accounts_info
        
        db.close()
        return result
        
    except Exception as e:
        logger.error(f"Database fetch failed: {e}")
        return {
            'error': str(e),
            'emails': [],
            'total_emails': 0,
            'total_unread': 0
        }