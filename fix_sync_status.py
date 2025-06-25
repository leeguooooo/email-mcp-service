#!/usr/bin/env python3
"""
修复同步状态和时区显示
"""
import sys
from pathlib import Path
from datetime import datetime
import pytz
import json

# 添加src目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from database.email_sync_db import EmailSyncDatabase
from account_manager import AccountManager
from operations.email_sync import EmailSyncManager

def fix_sync_status():
    """修复同步状态"""
    print("=== 修复同步状态 ===\n")
    
    # 1. 获取账户管理器的账户列表
    am = AccountManager()
    accounts = am.list_accounts()
    print(f"从AccountManager获取到 {len(accounts)} 个账户:")
    for acc in accounts:
        print(f"  - {acc['email']} (ID: {acc['id']}, Provider: {acc['provider']})")
    
    # 2. 检查数据库中的账户
    print("\n数据库中的账户状态:")
    db = EmailSyncDatabase(use_pool=False)
    
    # 先显示当前状态
    results = db.execute("SELECT * FROM accounts", commit=False)
    db_accounts = {}
    for row in results.fetchall():
        db_accounts[row['id']] = row
        print(f"  - {row['email']} (ID: {row['id']})")
        print(f"    Last Sync: {row['last_sync']}")
        print(f"    Total Emails: {row['total_emails']}")
    
    # 3. 修复账户信息
    print("\n修复账户信息...")
    for acc in accounts:
        acc_id = acc['id']
        if acc_id in db_accounts:
            # 更新账户信息
            print(f"  更新: {acc['email']}")
            db.execute("""
                UPDATE accounts 
                SET email = ?, provider = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (acc['email'], acc['provider'], acc_id))
        else:
            # 添加缺失的账户
            print(f"  添加: {acc['email']}")
            db.add_or_update_account(acc_id, acc['email'], acc['provider'])
    
    # 4. 统计邮件数量
    print("\n更新邮件统计...")
    for acc in accounts:
        acc_id = acc['id']
        # 统计该账户的邮件数
        result = db.execute("""
            SELECT COUNT(*) as count 
            FROM emails 
            WHERE account_id = ? AND is_deleted = FALSE
        """, (acc_id,), commit=False)
        
        count = result.fetchone()['count'] if not db.use_pool else result[0]['count']
        
        # 更新账户的邮件数
        db.execute("""
            UPDATE accounts 
            SET total_emails = ?
            WHERE id = ?
        """, (count, acc_id))
        
        print(f"  {acc['email']}: {count} 封邮件")
    
    db.close()
    print("\n✅ 修复完成!")

def show_sync_status_with_timezone():
    """显示带时区的同步状态"""
    print("\n=== 同步状态（本地时间）===\n")
    
    # 获取本地时区
    try:
        import tzlocal
        local_tz = tzlocal.get_localzone()
    except:
        # 如果没有tzlocal，使用系统时区
        local_tz = pytz.timezone('Asia/Tokyo')  # 你在日本
    
    db = EmailSyncDatabase(use_pool=False)
    status = db.get_sync_status()
    
    for acc in status['accounts']:
        print(f"📧 {acc['email']} ({acc['provider']})")
        
        if acc['last_sync']:
            # 解析UTC时间
            utc_time = datetime.fromisoformat(acc['last_sync'].replace('Z', '+00:00'))
            # 转换为本地时间
            local_time = utc_time.replace(tzinfo=pytz.UTC).astimezone(local_tz)
            print(f"   最后同步: {local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        else:
            print(f"   最后同步: 从未同步")
        
        print(f"   邮件数量: {acc['total_emails']}")
        print(f"   同步状态: {acc['sync_status']}")
        print()
    
    db.close()

def update_sync_handlers_timezone():
    """更新sync_handlers以显示本地时间"""
    print("\n创建时区感知的配置...")
    
    # 创建时区配置
    timezone_config = {
        "timezone": "auto",  # auto = 使用本地时区
        "display_format": "%Y-%m-%d %H:%M:%S %Z"
    }
    
    config_file = Path("timezone_config.json")
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(timezone_config, f, indent=2)
    
    print(f"✅ 创建了 {config_file}")

if __name__ == "__main__":
    try:
        fix_sync_status()
        show_sync_status_with_timezone()
        update_sync_handlers_timezone()
    except ImportError as e:
        if "pytz" in str(e) or "tzlocal" in str(e):
            print("\n需要安装时区库:")
            print("uv pip install pytz tzlocal")
        else:
            raise