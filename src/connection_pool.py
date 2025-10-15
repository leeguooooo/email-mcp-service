"""
IMAP Connection Pool - 复用连接避免频繁创建
"""
import imaplib
import logging
import threading
import time
from typing import Dict, Any, Optional
from queue import Queue, Empty
from datetime import datetime, timedelta
from contextlib import contextmanager

from .connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

class PooledConnection:
    """连接池中的连接对象"""
    def __init__(self, account_id: str, conn: imaplib.IMAP4_SSL, conn_mgr: ConnectionManager):
        self.account_id = account_id
        self.conn = conn
        self.conn_mgr = conn_mgr
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.in_use = False
        self.health_check_failures = 0
        
    def is_healthy(self) -> bool:
        """检查连接是否健康"""
        try:
            # 尝试NOOP命令
            status, _ = self.conn.noop()
            if status == 'OK':
                self.health_check_failures = 0
                return True
            else:
                self.health_check_failures += 1
                return False
        except Exception as e:
            logger.warning(f"Connection health check failed: {e}")
            self.health_check_failures += 1
            return False
    
    def is_expired(self, max_age_minutes: int = 30) -> bool:
        """检查连接是否过期"""
        age = (datetime.now() - self.created_at).total_seconds() / 60
        return age > max_age_minutes
    
    def close(self):
        """关闭连接"""
        try:
            self.conn_mgr.close_imap(self.conn)
        except Exception as e:
            logger.warning(f"Failed to close connection: {e}")


class IMAPConnectionPool:
    """IMAP连接池"""
    
    def __init__(self, max_connections_per_account: int = 3, 
                 connection_max_age_minutes: int = 30,
                 cleanup_interval_seconds: int = 300):
        """
        初始化连接池
        
        Args:
            max_connections_per_account: 每个账户最大连接数
            connection_max_age_minutes: 连接最大存活时间（分钟）
            cleanup_interval_seconds: 清理间隔（秒）
        """
        self.max_connections_per_account = max_connections_per_account
        self.connection_max_age_minutes = connection_max_age_minutes
        self.cleanup_interval_seconds = cleanup_interval_seconds
        
        # 账户ID -> 连接队列
        self._pools: Dict[str, Queue] = {}
        # 账户ID -> 已创建连接数
        self._connection_counts: Dict[str, int] = {}
        # 全局锁
        self._lock = threading.Lock()
        
        # 统计信息
        self.stats = {
            'total_created': 0,
            'total_reused': 0,
            'total_closed': 0,
            'health_check_failures': 0,
            'connection_waits': 0,
            'wait_timeouts': 0
        }
        
        # 启动清理线程
        self._cleanup_thread = threading.Thread(target=self._cleanup_worker, daemon=True)
        self._cleanup_thread.start()
        
    @contextmanager
    def get_connection(self, account_id: str, account_config: Dict[str, Any]):
        """
        获取连接（上下文管理器）
        
        Usage:
            with pool.get_connection(account_id, config) as conn:
                conn.select('INBOX')
                ...
        """
        pooled_conn = self._acquire_connection(account_id, account_config)
        try:
            yield pooled_conn.conn
        finally:
            self._release_connection(pooled_conn)
    
    def _acquire_connection(self, account_id: str, account_config: Dict[str, Any]) -> PooledConnection:
        """获取一个可用连接"""
        with self._lock:
            # 确保账户有连接队列
            if account_id not in self._pools:
                self._pools[account_id] = Queue()
                self._connection_counts[account_id] = 0
        
        # 尝试从池中获取空闲连接
        try:
            pooled_conn = self._pools[account_id].get_nowait()
            
            # 检查连接是否健康且未过期
            if pooled_conn.is_expired(self.connection_max_age_minutes):
                logger.info(f"Connection expired for {account_id}, creating new one")
                pooled_conn.close()
                with self._lock:
                    self._connection_counts[account_id] -= 1
                    self.stats['total_closed'] += 1
                # 创建新连接（过期连接不计入限制）
                return self._create_new_connection(account_id, account_config)
            
            if not pooled_conn.is_healthy():
                logger.warning(f"Unhealthy connection for {account_id}, creating new one")
                pooled_conn.close()
                with self._lock:
                    self._connection_counts[account_id] -= 1
                    self.stats['total_closed'] += 1
                    self.stats['health_check_failures'] += 1
                # 创建新连接（不健康连接不计入限制）
                return self._create_new_connection(account_id, account_config)
            
            # 连接可用，标记为使用中
            pooled_conn.in_use = True
            pooled_conn.last_used = datetime.now()
            
            with self._lock:
                self.stats['total_reused'] += 1
            
            logger.debug(f"Reusing connection for {account_id}")
            return pooled_conn
            
        except Empty:
            # 池中没有空闲连接，检查是否可以创建新连接
            with self._lock:
                current_count = self._connection_counts.get(account_id, 0)
                
                # 如果未达到限制，可以创建新连接
                if current_count < self.max_connections_per_account:
                    # 在锁内创建，避免竞态条件
                    return self._create_new_connection(account_id, account_config)
            
            # 达到限制，需要等待连接释放
            logger.warning(
                f"Max connections ({self.max_connections_per_account}) "
                f"reached for {account_id}, waiting for available connection..."
            )
            
            with self._lock:
                self.stats['connection_waits'] += 1
            
            # 阻塞等待连接释放（带超时）
            wait_timeout = 60  # 最多等待60秒
            try:
                pooled_conn = self._pools[account_id].get(timeout=wait_timeout)
                
                # 再次检查连接健康状态
                if pooled_conn.is_expired(self.connection_max_age_minutes) or not pooled_conn.is_healthy():
                    logger.info(f"Waited connection is invalid for {account_id}, closing and retrying")
                    pooled_conn.close()
                    with self._lock:
                        self._connection_counts[account_id] -= 1
                        self.stats['total_closed'] += 1
                    # 递归重试（此时应该有空位了）
                    return self._acquire_connection(account_id, account_config)
                
                # 连接可用
                pooled_conn.in_use = True
                pooled_conn.last_used = datetime.now()
                
                with self._lock:
                    self.stats['total_reused'] += 1
                
                logger.info(f"Acquired connection after waiting for {account_id}")
                return pooled_conn
                
            except Empty:
                # 等待超时，抛出异常
                with self._lock:
                    self.stats['wait_timeouts'] += 1
                
                error_msg = (
                    f"Connection pool exhausted for {account_id}: "
                    f"max {self.max_connections_per_account} connections in use, "
                    f"waited {wait_timeout}s with no connection released"
                )
                logger.error(error_msg)
                raise RuntimeError(error_msg)
    
    def _create_new_connection(self, account_id: str, account_config: Dict[str, Any]) -> PooledConnection:
        """创建新的IMAP连接"""
        try:
            conn_mgr = ConnectionManager(account_config)
            conn = conn_mgr.connect_imap()
            
            pooled_conn = PooledConnection(account_id, conn, conn_mgr)
            pooled_conn.in_use = True
            
            with self._lock:
                self._connection_counts[account_id] = \
                    self._connection_counts.get(account_id, 0) + 1
                self.stats['total_created'] += 1
            
            logger.info(f"Created new connection for {account_id} "
                       f"(total: {self._connection_counts[account_id]})")
            return pooled_conn
            
        except Exception as e:
            logger.error(f"Failed to create connection for {account_id}: {e}")
            raise
    
    def _release_connection(self, pooled_conn: PooledConnection):
        """释放连接回池中"""
        if not pooled_conn:
            return
        
        pooled_conn.in_use = False
        pooled_conn.last_used = datetime.now()
        
        # 将连接放回队列
        try:
            self._pools[pooled_conn.account_id].put(pooled_conn)
            logger.debug(f"Released connection for {pooled_conn.account_id}")
        except Exception as e:
            logger.error(f"Failed to release connection: {e}")
            # 如果无法放回，关闭连接
            pooled_conn.close()
            with self._lock:
                self._connection_counts[pooled_conn.account_id] -= 1
                self.stats['total_closed'] += 1
    
    def _cleanup_worker(self):
        """清理工作线程：定期清理过期和不健康的连接"""
        while True:
            try:
                time.sleep(self.cleanup_interval_seconds)
                self._cleanup_expired_connections()
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
    
    def _cleanup_expired_connections(self):
        """清理过期连接"""
        logger.debug("Running connection pool cleanup")
        
        with self._lock:
            account_ids = list(self._pools.keys())
        
        for account_id in account_ids:
            cleaned = 0
            queue = self._pools[account_id]
            temp_conns = []
            
            # 从队列中取出所有连接
            while True:
                try:
                    pooled_conn = queue.get_nowait()
                    
                    # 检查是否需要清理
                    if (pooled_conn.is_expired(self.connection_max_age_minutes) or
                        not pooled_conn.is_healthy()):
                        pooled_conn.close()
                        cleaned += 1
                        with self._lock:
                            self._connection_counts[account_id] -= 1
                            self.stats['total_closed'] += 1
                    else:
                        temp_conns.append(pooled_conn)
                        
                except Empty:
                    break
            
            # 将有效连接放回队列
            for conn in temp_conns:
                queue.put(conn)
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} expired connections for {account_id}")
    
    def close_all(self):
        """关闭所有连接"""
        logger.info("Closing all connections in pool")
        
        with self._lock:
            for account_id, queue in self._pools.items():
                while True:
                    try:
                        pooled_conn = queue.get_nowait()
                        pooled_conn.close()
                        self.stats['total_closed'] += 1
                    except Empty:
                        break
                
                self._connection_counts[account_id] = 0
            
            self._pools.clear()
            self._connection_counts.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        with self._lock:
            return {
                'stats': self.stats.copy(),
                'active_accounts': len(self._pools),
                'connections_per_account': self._connection_counts.copy(),
                'total_active_connections': sum(self._connection_counts.values()),
                'config': {
                    'max_connections_per_account': self.max_connections_per_account,
                    'connection_max_age_minutes': self.connection_max_age_minutes,
                    'cleanup_interval_seconds': self.cleanup_interval_seconds
                }
            }


# 全局连接池实例
_connection_pool_instance: Optional[IMAPConnectionPool] = None

def get_connection_pool() -> IMAPConnectionPool:
    """获取全局连接池实例"""
    global _connection_pool_instance
    if _connection_pool_instance is None:
        _connection_pool_instance = IMAPConnectionPool()
    return _connection_pool_instance

