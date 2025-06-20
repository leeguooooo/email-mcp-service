"""
Synchronization manager for email database
"""
import logging
import threading
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from account_manager import AccountManager
from connection_manager import ConnectionManager
from .email_database import EmailDatabase
from operations.folder_operations import FolderOperations
from operations.email_operations import EmailOperations

logger = logging.getLogger(__name__)

class SyncManager:
    """Manages email synchronization between IMAP servers and local database"""
    
    def __init__(self, db: EmailDatabase, account_manager: AccountManager):
        self.db = db
        self.account_manager = account_manager
        self._sync_threads = {}
        self._stop_event = threading.Event()
        self._sync_lock = threading.Lock()
        
        # Sync configuration
        self.config = {
            'sync_interval': 300,  # 5 minutes
            'initial_days': 30,    # Initial sync for last 30 days
            'max_workers': 5,      # Max parallel sync workers
            'batch_size': 100,     # Emails per batch
            'sync_body_days': 7,   # Sync full body for last 7 days
        }
    
    def start_auto_sync(self):
        """Start automatic synchronization in background"""
        def sync_loop():
            while not self._stop_event.is_set():
                try:
                    self.sync_all_accounts()
                except Exception as e:
                    logger.error(f"Auto sync error: {e}")
                
                # Wait for next sync interval
                self._stop_event.wait(self.config['sync_interval'])
        
        sync_thread = threading.Thread(target=sync_loop, daemon=True)
        sync_thread.start()
        logger.info("Auto sync started")
    
    def stop_auto_sync(self):
        """Stop automatic synchronization"""
        self._stop_event.set()
        logger.info("Auto sync stopped")
    
    def sync_all_accounts(self, full_sync: bool = False) -> Dict[str, Any]:
        """Sync all accounts"""
        start_time = datetime.now()
        results = {
            'success': [],
            'failed': [],
            'total_synced': 0,
            'duration': 0
        }
        
        accounts = self.account_manager.list_accounts()
        
        with ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
            future_to_account = {
                executor.submit(self.sync_account, acc['id'], full_sync): acc
                for acc in accounts
            }
            
            for future in as_completed(future_to_account):
                account = future_to_account[future]
                try:
                    result = future.result()
                    results['success'].append({
                        'account': account['email'],
                        'synced': result['emails_synced']
                    })
                    results['total_synced'] += result['emails_synced']
                except Exception as e:
                    logger.error(f"Failed to sync {account['email']}: {e}")
                    results['failed'].append({
                        'account': account['email'],
                        'error': str(e)
                    })
        
        results['duration'] = (datetime.now() - start_time).total_seconds()
        logger.info(f"Sync completed: {results['total_synced']} emails in {results['duration']:.2f}s")
        
        return results
    
    def sync_account(self, account_id: str, full_sync: bool = False) -> Dict[str, Any]:
        """Sync a single account"""
        with self._sync_lock:
            if account_id in self._sync_threads and self._sync_threads[account_id].is_alive():
                logger.warning(f"Sync already in progress for {account_id}")
                return {'status': 'already_running'}
        
        account = self.account_manager.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")
        
        # Update account in database
        self.db.upsert_account(account)
        
        start_time = datetime.now()
        result = {
            'account_id': account_id,
            'emails_synced': 0,
            'folders_synced': 0,
            'errors': []
        }
        
        try:
            conn_mgr = ConnectionManager(account)
            
            # Sync folders first
            folder_result = self._sync_folders(account_id, conn_mgr)
            result['folders_synced'] = folder_result['count']
            
            # Get folders to sync
            folders = self.db.conn.execute(
                "SELECT * FROM folders WHERE account_id = ?",
                (account_id,)
            ).fetchall()
            
            # Sync each folder
            for folder in folders:
                try:
                    email_count = self._sync_folder_emails(
                        account_id, 
                        dict(folder),
                        conn_mgr,
                        full_sync
                    )
                    result['emails_synced'] += email_count
                except Exception as e:
                    logger.error(f"Failed to sync folder {folder['folder_name']}: {e}")
                    result['errors'].append(f"Folder {folder['folder_name']}: {str(e)}")
            
            # Update last sync time
            self.db.conn.execute(
                "UPDATE accounts SET last_sync_time = ?, sync_status = ? WHERE id = ?",
                (datetime.now(), 'completed', account_id)
            )
            self.db.conn.commit()
            
            # Log sync
            self.db.log_sync(
                account_id=account_id,
                sync_type='full' if full_sync else 'incremental',
                start_time=start_time,
                end_time=datetime.now(),
                emails_synced=result['emails_synced'],
                status='success' if not result['errors'] else 'partial'
            )
            
        except Exception as e:
            logger.error(f"Account sync failed for {account_id}: {e}")
            self.db.conn.execute(
                "UPDATE accounts SET sync_status = ? WHERE id = ?",
                ('failed', account_id)
            )
            self.db.conn.commit()
            
            self.db.log_sync(
                account_id=account_id,
                sync_type='full' if full_sync else 'incremental',
                start_time=start_time,
                end_time=datetime.now(),
                status='failed',
                error_message=str(e)
            )
            raise
        
        return result
    
    def _sync_folders(self, account_id: str, conn_mgr: ConnectionManager) -> Dict[str, Any]:
        """Sync folder structure"""
        folder_ops = FolderOperations(conn_mgr)
        result = folder_ops.list_folders()
        
        if not result.get('success'):
            raise Exception(f"Failed to list folders: {result.get('error')}")
        
        folders = result.get('folders', [])
        
        for folder in folders:
            self.db.upsert_folder(account_id, folder)
        
        return {'count': len(folders)}
    
    def _sync_folder_emails(self, account_id: str, folder: Dict[str, Any], 
                           conn_mgr: ConnectionManager, full_sync: bool = False) -> int:
        """Sync emails in a specific folder"""
        folder_id = folder['id']
        folder_name = folder['folder_name']
        last_sync_uid = folder.get('last_sync_uid', 0) if not full_sync else 0
        
        email_ops = EmailOperations(conn_mgr)
        emails_synced = 0
        
        try:
            # Connect to folder
            with conn_mgr.get_connection() as conn:
                conn.select(folder_name)
                
                # Search for emails to sync
                if last_sync_uid > 0:
                    # Incremental sync: get UIDs greater than last sync
                    search_criteria = f'UID {last_sync_uid + 1}:*'
                else:
                    # Full sync or initial sync: get emails from last N days
                    since_date = datetime.now() - timedelta(days=self.config['initial_days'])
                    search_criteria = f'SINCE {since_date.strftime("%d-%b-%Y")}'
                
                # Search for UIDs
                _, uid_data = conn.uid('search', None, search_criteria)
                uids = uid_data[0].split()
                
                if not uids:
                    return 0
                
                # Process in batches
                for i in range(0, len(uids), self.config['batch_size']):
                    batch_uids = uids[i:i + self.config['batch_size']]
                    
                    # Fetch email headers and metadata
                    uid_list = b','.join(batch_uids)
                    fetch_data = '(UID FLAGS RFC822.SIZE BODY.PEEK[HEADER])'
                    
                    _, messages = conn.uid('fetch', uid_list, fetch_data)
                    
                    for msg_data in messages:
                        if isinstance(msg_data, tuple):
                            try:
                                email_data = self._parse_email_data(msg_data)
                                if email_data:
                                    # Store in database
                                    self.db.upsert_email(email_data, account_id, folder_id)
                                    emails_synced += 1
                                    
                                    # Update last sync UID
                                    if email_data['uid'] > last_sync_uid:
                                        last_sync_uid = email_data['uid']
                            except Exception as e:
                                logger.error(f"Failed to parse email: {e}")
                
                # Update folder's last sync UID
                self.db.conn.execute(
                    "UPDATE folders SET last_sync_uid = ?, message_count = ?, "
                    "unread_count = (SELECT COUNT(*) FROM emails WHERE folder_id = ? AND is_read = 0) "
                    "WHERE id = ?",
                    (last_sync_uid, len(uids), folder_id, folder_id)
                )
                self.db.conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to sync folder {folder_name}: {e}")
            raise
        
        return emails_synced
    
    def _parse_email_data(self, msg_data: tuple) -> Optional[Dict[str, Any]]:
        """Parse IMAP message data into email dictionary"""
        try:
            # Extract response parts
            msg_info = msg_data[0]
            msg_header = msg_data[1]
            
            # Parse flags and UID
            import imaplib
            import email
            from email.header import decode_header
            
            # Parse message info
            msg_dict = imaplib.ParseFlags(msg_info)
            uid = int(msg_dict.get(b'UID', 0))
            flags = msg_dict.get(b'FLAGS', [])
            size = int(msg_dict.get(b'RFC822.SIZE', 0))
            
            # Parse email headers
            email_message = email.message_from_bytes(msg_header)
            
            # Extract basic info
            subject = self._decode_header(email_message.get('Subject', ''))
            from_header = email_message.get('From', '')
            from_addr, from_name = email.utils.parseaddr(from_header)
            
            # Parse date
            date_str = email_message.get('Date', '')
            try:
                date_tuple = email.utils.parsedate_to_datetime(date_str)
                date = date_tuple.isoformat() if date_tuple else None
            except:
                date = None
            
            # Parse recipients
            to_addrs = []
            for addr in email_message.get_all('To', []):
                to_addrs.extend([a[1] for a in email.utils.getaddresses([addr])])
            
            cc_addrs = []
            for addr in email_message.get_all('Cc', []):
                cc_addrs.extend([a[1] for a in email.utils.getaddresses([addr])])
            
            return {
                'uid': uid,
                'message_id': email_message.get('Message-ID', ''),
                'subject': subject,
                'from': from_addr,
                'from_name': from_name,
                'to': to_addrs,
                'cc': cc_addrs,
                'date': date,
                'size': size,
                'unread': b'\\Seen' not in flags,
                'flagged': b'\\Flagged' in flags,
                'headers': dict(email_message.items())
            }
            
        except Exception as e:
            logger.error(f"Failed to parse email data: {e}")
            return None
    
    def _decode_header(self, header: str) -> str:
        """Decode email header handling various encodings"""
        if not header:
            return ''
        
        from email.header import decode_header
        
        decoded_parts = []
        for part, encoding in decode_header(header):
            if isinstance(part, bytes):
                try:
                    decoded_parts.append(part.decode(encoding or 'utf-8'))
                except:
                    decoded_parts.append(part.decode('utf-8', errors='replace'))
            else:
                decoded_parts.append(str(part))
        
        return ' '.join(decoded_parts)
    
    def sync_email_body(self, email_id: int) -> bool:
        """Sync full email body on demand"""
        try:
            # Get email info
            cursor = self.db.conn.execute("""
                SELECT e.*, a.*, f.folder_name 
                FROM emails e
                JOIN accounts a ON e.account_id = a.id
                JOIN folders f ON e.folder_id = f.id
                WHERE e.id = ?
            """, (email_id,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            email = dict(row)
            account = self.account_manager.get_account(email['account_id'])
            conn_mgr = ConnectionManager(account)
            
            # Fetch full email
            with conn_mgr.get_connection() as conn:
                conn.select(email['folder_name'])
                
                # Fetch body
                _, msg_data = conn.uid('fetch', str(email['uid']), '(BODY.PEEK[])')
                
                if msg_data and msg_data[0]:
                    import email
                    email_message = email.message_from_bytes(msg_data[0][1])
                    
                    # Extract body
                    body_text = ''
                    body_html = ''
                    
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        if content_type == 'text/plain' and not body_text:
                            body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        elif content_type == 'text/html' and not body_html:
                            body_html = part.get_payload(decode=True).decode('utf-8', errors='replace')
                    
                    # Update database
                    with self.db.transaction() as db_conn:
                        db_conn.execute("""
                            INSERT OR REPLACE INTO email_contents 
                            (email_id, body_text, body_html)
                            VALUES (?, ?, ?)
                        """, (email_id, body_text, body_html))
                        
                        db_conn.execute(
                            "UPDATE emails SET sync_status = 'full' WHERE id = ?",
                            (email_id,)
                        )
                    
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to sync email body: {e}")
        
        return False