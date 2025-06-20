"""
Connection pool manager for IMAP/SMTP connections
Provides connection reuse and automatic cleanup
"""
import imaplib
import smtplib
import threading
import time
import logging
from typing import Dict, Any, Optional, Tuple
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionPool:
    """
    Thread-safe connection pool for email connections
    Automatically handles connection lifecycle and cleanup
    """
    
    def __init__(self, max_connections_per_account: int = 3, connection_timeout: int = 300):
        """
        Initialize connection pool
        
        Args:
            max_connections_per_account: Maximum connections per email account
            connection_timeout: Seconds before idle connection is closed
        """
        self.max_connections = max_connections_per_account
        self.connection_timeout = connection_timeout
        
        # Pool storage: {account_id: {
        #   'imap': [(connection, last_used), ...],
        #   'smtp': [(connection, last_used), ...]
        # }}
        self._pools = {}
        self._lock = threading.RLock()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()
    
    @contextmanager
    def get_imap_connection(self, account_info: Dict[str, Any]):
        """
        Get IMAP connection from pool or create new one
        
        Usage:
            with pool.get_imap_connection(account) as conn:
                # Use connection
                conn.select('INBOX')
        """
        account_id = account_info['id']
        connection = None
        
        try:
            # Try to get existing connection
            connection = self._get_from_pool(account_id, 'imap')
            
            if connection:
                # Test if connection is still alive
                try:
                    connection.noop()
                    logger.debug(f"Reusing IMAP connection for {account_id}")
                except:
                    logger.debug(f"Stale IMAP connection for {account_id}, creating new")
                    connection = None
            
            # Create new connection if needed
            if not connection:
                connection = self._create_imap_connection(account_info)
                logger.info(f"Created new IMAP connection for {account_id}")
            
            yield connection
            
            # Return to pool if successful
            self._return_to_pool(account_id, 'imap', connection)
            
        except Exception as e:
            # Close connection on error
            if connection:
                try:
                    connection.logout()
                except:
                    pass
            raise e
    
    @contextmanager
    def get_smtp_connection(self, account_info: Dict[str, Any]):
        """
        Get SMTP connection from pool or create new one
        """
        account_id = account_info['id']
        connection = None
        
        try:
            # Try to get existing connection
            connection = self._get_from_pool(account_id, 'smtp')
            
            if connection:
                # Test if connection is still alive
                try:
                    connection.noop()
                    logger.debug(f"Reusing SMTP connection for {account_id}")
                except:
                    logger.debug(f"Stale SMTP connection for {account_id}, creating new")
                    connection = None
            
            # Create new connection if needed
            if not connection:
                connection = self._create_smtp_connection(account_info)
                logger.info(f"Created new SMTP connection for {account_id}")
            
            yield connection
            
            # Return to pool if successful
            self._return_to_pool(account_id, 'smtp', connection)
            
        except Exception as e:
            # Close connection on error
            if connection:
                try:
                    connection.quit()
                except:
                    pass
            raise e
    
    def _get_from_pool(self, account_id: str, conn_type: str) -> Optional[Any]:
        """Get connection from pool"""
        with self._lock:
            if account_id not in self._pools:
                return None
            
            pool = self._pools[account_id].get(conn_type, [])
            if pool:
                connection, _ = pool.pop(0)
                return connection
            
            return None
    
    def _return_to_pool(self, account_id: str, conn_type: str, connection: Any):
        """Return connection to pool"""
        with self._lock:
            if account_id not in self._pools:
                self._pools[account_id] = {'imap': [], 'smtp': []}
            
            pool = self._pools[account_id][conn_type]
            
            # Check pool size limit
            if len(pool) < self.max_connections:
                pool.append((connection, time.time()))
            else:
                # Close oldest connection
                if pool:
                    old_conn, _ = pool.pop(0)
                    self._close_connection(old_conn, conn_type)
                pool.append((connection, time.time()))
    
    def _create_imap_connection(self, account_info: Dict[str, Any]) -> imaplib.IMAP4_SSL:
        """Create new IMAP connection"""
        from ..connection_manager import ConnectionManager
        
        # Use existing ConnectionManager for provider-specific logic
        conn_mgr = ConnectionManager(account_info)
        return conn_mgr.connect_imap()
    
    def _create_smtp_connection(self, account_info: Dict[str, Any]) -> smtplib.SMTP:
        """Create new SMTP connection"""
        from ..connection_manager import ConnectionManager
        
        # Use existing ConnectionManager for provider-specific logic
        conn_mgr = ConnectionManager(account_info)
        return conn_mgr.connect_smtp()
    
    def _close_connection(self, connection: Any, conn_type: str):
        """Safely close a connection"""
        try:
            if conn_type == 'imap':
                connection.logout()
            else:  # smtp
                connection.quit()
        except:
            pass
    
    def _cleanup_loop(self):
        """Background thread to clean up idle connections"""
        while True:
            try:
                time.sleep(30)  # Check every 30 seconds
                self._cleanup_idle_connections()
            except:
                pass
    
    def _cleanup_idle_connections(self):
        """Remove connections idle longer than timeout"""
        current_time = time.time()
        
        with self._lock:
            for account_id in list(self._pools.keys()):
                for conn_type in ['imap', 'smtp']:
                    pool = self._pools[account_id].get(conn_type, [])
                    active_connections = []
                    
                    for conn, last_used in pool:
                        if current_time - last_used > self.connection_timeout:
                            logger.debug(f"Closing idle {conn_type} connection for {account_id}")
                            self._close_connection(conn, conn_type)
                        else:
                            active_connections.append((conn, last_used))
                    
                    self._pools[account_id][conn_type] = active_connections
    
    def close_all(self):
        """Close all connections in pool"""
        with self._lock:
            for account_id in self._pools:
                for conn_type in ['imap', 'smtp']:
                    pool = self._pools[account_id].get(conn_type, [])
                    for conn, _ in pool:
                        self._close_connection(conn, conn_type)
            self._pools.clear()

# Global connection pool instance
_connection_pool = None
_pool_lock = threading.Lock()

def get_connection_pool() -> ConnectionPool:
    """Get or create global connection pool instance"""
    global _connection_pool
    
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = ConnectionPool()
    
    return _connection_pool