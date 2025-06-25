"""
数据库连接池 - 避免并发锁定问题
"""
import sqlite3
import threading
import queue
import logging
from typing import Optional, Any
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

class DatabasePool:
    """SQLite数据库连接池"""
    
    def __init__(self, db_path: str = "email_sync.db", pool_size: int = 5):
        """
        初始化连接池
        
        Args:
            db_path: 数据库路径
            pool_size: 连接池大小
        """
        self.db_path = Path(db_path)
        self.pool_size = pool_size
        self._pool = queue.Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """初始化连接池"""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            self._pool.put(conn)
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建数据库连接"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0  # 30秒超时
        )
        conn.row_factory = sqlite3.Row
        
        # 优化设置
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA busy_timeout=30000")  # 30秒忙等待
        
        return conn
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接（上下文管理器）
        
        使用方式:
            with pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM emails")
        """
        conn = None
        try:
            # 获取连接（等待最多30秒）
            conn = self._pool.get(timeout=30)
            yield conn
        except queue.Empty:
            logger.error("Failed to get database connection from pool")
            raise RuntimeError("Database connection pool exhausted")
        finally:
            if conn:
                try:
                    # 回滚未提交的事务
                    conn.rollback()
                except:
                    pass
                # 归还连接到池
                self._pool.put(conn)
    
    def execute(self, query: str, params: tuple = (), commit: bool = True) -> Any:
        """
        执行SQL查询
        
        Args:
            query: SQL查询语句
            params: 查询参数
            commit: 是否自动提交
            
        Returns:
            查询结果或影响的行数
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            result = cursor.execute(query, params)
            
            if commit and query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                conn.commit()
                return cursor.lastrowid if query.strip().upper().startswith('INSERT') else cursor.rowcount
            else:
                return cursor.fetchall()
    
    def execute_many(self, query: str, params_list: list, commit: bool = True) -> int:
        """
        批量执行SQL查询
        
        Args:
            query: SQL查询语句
            params_list: 参数列表
            commit: 是否自动提交
            
        Returns:
            影响的总行数
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, params_list)
            
            if commit:
                conn.commit()
            
            return cursor.rowcount
    
    def close(self):
        """关闭连接池"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# 全局连接池实例
_db_pool = None

def get_db_pool(db_path: str = "email_sync.db", pool_size: int = 5) -> DatabasePool:
    """获取数据库连接池单例"""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool(db_path, pool_size)
    return _db_pool

def close_db_pool():
    """关闭数据库连接池"""
    global _db_pool
    if _db_pool:
        _db_pool.close()
        _db_pool = None