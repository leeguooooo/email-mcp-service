#!/usr/bin/env python3
"""
快速修复工具 - 解决常见问题
"""
import os
import sys
from pathlib import Path

def fix_all():
    """执行所有修复"""
    print("=== MCP Email Service 快速修复工具 ===\n")
    
    # 1. 清理数据库锁
    print("1. 清理数据库锁...")
    wal_file = Path("email_sync.db-wal")
    shm_file = Path("email_sync.db-shm")
    
    if wal_file.exists():
        wal_file.unlink()
        print("   ✅ 删除了WAL文件")
    
    if shm_file.exists():
        shm_file.unlink()
        print("   ✅ 删除了SHM文件")
    
    # 2. 停止所有同步进程
    print("\n2. 停止同步进程...")
    os.system("pkill -f 'sync_manager|email_sync|init_sync' 2>/dev/null || true")
    print("   ✅ 已发送停止信号")
    
    # 3. 删除PID文件
    print("\n3. 清理PID文件...")
    for pid_file in Path(".").glob("*.pid"):
        pid_file.unlink()
        print(f"   ✅ 删除 {pid_file}")
    
    # 4. 测试数据库连接
    print("\n4. 测试数据库连接...")
    try:
        sys.path.insert(0, 'src')
        from database.email_sync_db import EmailSyncDatabase
        
        db = EmailSyncDatabase(use_pool=False)  # 使用直接连接测试
        status = db.get_sync_status()
        db.close()
        
        print(f"   ✅ 数据库连接正常")
        print(f"   - 账户数: {len(status['accounts'])}")
        print(f"   - 邮件数: {status['total_emails']}")
    except Exception as e:
        print(f"   ❌ 数据库测试失败: {e}")
    
    # 5. 测试邮箱连接
    print("\n5. 测试邮箱连接...")
    try:
        from legacy_operations import check_connection
        result = check_connection()
        
        if result.get('success'):
            print(f"   ✅ 邮箱连接正常")
            for acc in result.get('accounts', []):
                imap_ok = "✅" if acc.get('imap', {}).get('success') else "❌"
                smtp_ok = "✅" if acc.get('smtp', {}).get('success') else "❌"
                print(f"   - {acc['email']}: IMAP {imap_ok}, SMTP {smtp_ok}")
        else:
            print(f"   ❌ 连接测试失败: {result.get('error')}")
    except Exception as e:
        print(f"   ❌ 连接测试异常: {e}")
    
    print("\n✅ 修复完成！")
    print("\n建议后续操作:")
    print("1. 启动同步: uv run python sync_manager.py start")
    print("2. 查看状态: uv run python sync_manager.py status")
    print("3. 优化数据库: uv run python optimize_db.py")

if __name__ == "__main__":
    fix_all()