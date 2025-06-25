#!/usr/bin/env python3
"""
数据库优化和维护工具
"""
import sqlite3
import sys
from pathlib import Path
import time

def optimize_database(db_path="email_sync.db"):
    """优化数据库性能"""
    print(f"=== 优化数据库: {db_path} ===\n")
    
    db_file = Path(db_path)
    if not db_file.exists():
        print("❌ 数据库文件不存在")
        return
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        
        # 1. 检查数据库大小
        size_mb = db_file.stat().st_size / (1024 * 1024)
        print(f"1. 数据库大小: {size_mb:.2f} MB")
        
        # 2. 获取表统计信息
        cursor = conn.execute("""
            SELECT name, 
                   (SELECT COUNT(*) FROM sqlite_master AS m2 
                    WHERE m2.name = m1.name AND m2.type = 'table') as count
            FROM sqlite_master AS m1 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        
        print("\n2. 表统计信息:")
        tables = cursor.fetchall()
        for table_name, _ in tables:
            count_cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = count_cursor.fetchone()[0]
            print(f"   - {table_name}: {count} 条记录")
        
        # 3. 检查索引
        print("\n3. 检查索引...")
        cursor = conn.execute("""
            SELECT name, tbl_name FROM sqlite_master 
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
        """)
        indexes = cursor.fetchall()
        print(f"   发现 {len(indexes)} 个索引")
        
        # 4. 分析数据库
        print("\n4. 分析数据库...")
        conn.execute("ANALYZE")
        print("   ✅ 分析完成")
        
        # 5. 清理WAL日志
        print("\n5. 清理WAL日志...")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print("   ✅ WAL日志已清理")
        
        # 6. VACUUM优化（会重建数据库）
        print("\n6. 执行VACUUM优化...")
        conn.execute("VACUUM")
        print("   ✅ VACUUM完成")
        
        # 7. 优化设置
        print("\n7. 应用优化设置...")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=30000000000")
        print("   ✅ 优化设置已应用")
        
        # 关闭连接
        conn.close()
        
        # 检查优化后的大小
        new_size_mb = db_file.stat().st_size / (1024 * 1024)
        saved_mb = size_mb - new_size_mb
        print(f"\n8. 优化结果:")
        print(f"   - 原始大小: {size_mb:.2f} MB")
        print(f"   - 优化后: {new_size_mb:.2f} MB")
        print(f"   - 节省空间: {saved_mb:.2f} MB ({saved_mb/size_mb*100:.1f}%)")
        
        print("\n✅ 数据库优化完成！")
        
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print("❌ 数据库被锁定！")
            print("   请确保没有其他进程在使用数据库")
            print("   运行: pkill -f 'sync_manager|email_sync'")
        else:
            print(f"❌ 数据库错误: {e}")
    except Exception as e:
        print(f"❌ 优化失败: {e}")

def check_integrity(db_path="email_sync.db"):
    """检查数据库完整性"""
    print("\n=== 检查数据库完整性 ===")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        
        if result == "ok":
            print("✅ 数据库完整性检查通过")
        else:
            print(f"❌ 数据库完整性问题: {result}")
        
        conn.close()
    except Exception as e:
        print(f"❌ 完整性检查失败: {e}")

def unlock_database(db_path="email_sync.db"):
    """尝试解锁数据库"""
    print("\n=== 解锁数据库 ===")
    
    # 删除WAL文件
    wal_file = Path(f"{db_path}-wal")
    shm_file = Path(f"{db_path}-shm")
    
    if wal_file.exists():
        wal_file.unlink()
        print("✅ 删除了WAL文件")
    
    if shm_file.exists():
        shm_file.unlink()
        print("✅ 删除了SHM文件")
    
    # 尝试独占访问
    try:
        conn = sqlite3.connect(db_path, isolation_level='EXCLUSIVE')
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("COMMIT")
        conn.close()
        print("✅ 数据库已解锁")
    except Exception as e:
        print(f"❌ 解锁失败: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "unlock":
        unlock_database()
    else:
        optimize_database()
        check_integrity()