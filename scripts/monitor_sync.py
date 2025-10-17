#!/usr/bin/env python3
"""
实时监控邮件同步状态
用法: python scripts/monitor_sync.py
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import sys

# 导入路径配置
try:
    from src.config.paths import EMAIL_SYNC_DB, SYNC_CONFIG_JSON, SYNC_HEALTH_HISTORY_JSON
except ImportError:
    # 如果导入失败，使用相对于项目根目录的默认路径
    EMAIL_SYNC_DB = "data/email_sync.db"
    SYNC_CONFIG_JSON = "data/sync_config.json"
    SYNC_HEALTH_HISTORY_JSON = "data/sync_health_history.json"

def format_time_ago(timestamp_str):
    """格式化时间差"""
    try:
        if not timestamp_str:
            return "从未同步"
        
        # 处理不同的时间格式
        if 'T' in timestamp_str:
            ts = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            ts = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        
        now = datetime.now()
        if ts.tzinfo:
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        
        delta = now - ts
        
        if delta.total_seconds() < 60:
            return f"{int(delta.total_seconds())} 秒前"
        elif delta.total_seconds() < 3600:
            return f"{int(delta.total_seconds() / 60)} 分钟前"
        elif delta.total_seconds() < 86400:
            return f"{int(delta.total_seconds() / 3600)} 小时前"
        else:
            return f"{int(delta.total_seconds() / 86400)} 天前"
    except Exception as e:
        return f"解析失败: {timestamp_str}"

def check_sync_status():
    """检查同步状态"""
    print("=" * 80)
    print("📊 MCP Email Service - 同步状态监控")
    print("=" * 80)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 1. 检查配置
    config_file = Path(SYNC_CONFIG_JSON)
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            sync_config = config.get('sync', {})
            enabled = sync_config.get('enabled', False)
            interval = sync_config.get('interval_minutes', 15)
            
            print("📋 同步配置:")
            print(f"   ├─ 状态: {'✅ 已启用' if enabled else '❌ 已禁用'}")
            print(f"   ├─ 同步间隔: {interval} 分钟")
            print(f"   ├─ 完全同步: 每 {sync_config.get('full_sync_hours', 24)} 小时")
            print(f"   └─ 自动启动: {'✅ 是' if sync_config.get('auto_start', False) else '❌ 否'}\n")
        except Exception as e:
            print(f"⚠️  配置文件读取失败: {e}\n")
    else:
        print("⚠️  配置文件不存在\n")
    
    # 2. 检查同步历史
    history_file = Path(SYNC_HEALTH_HISTORY_JSON)
    if history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            print("📜 最近同步历史:")
            sync_history = history.get('sync_history', [])[-5:]  # 最近5次
            
            if sync_history:
                for item in reversed(sync_history):
                    account = item.get('account_id', 'unknown')
                    timestamp = item.get('timestamp', '')
                    status = item.get('status', 'unknown')
                    emails = item.get('emails_synced', 0)
                    duration = item.get('duration_seconds', 0)
                    
                    status_icon = "✅" if status == "success" else "❌"
                    time_ago = format_time_ago(timestamp)
                    
                    print(f"   {status_icon} {account}: {emails} 封邮件, "
                          f"{duration:.1f}秒 ({time_ago})")
                print()
            else:
                print("   ⚠️  暂无同步历史\n")
            
            # 健康状态
            print("🏥 账户健康状态:")
            health_status = history.get('health_status', {})
            for account_id, status in health_status.items():
                score = status.get('health_score', 0)
                success_rate = status.get('success_rate', 0)
                total = status.get('total_syncs', 0)
                last_error = status.get('last_error')
                
                score_icon = "🟢" if score >= 80 else ("🟡" if score >= 50 else "🔴")
                
                print(f"   {score_icon} {account_id}:")
                print(f"      ├─ 健康分数: {score:.0f}/100")
                print(f"      ├─ 成功率: {success_rate:.1f}%")
                print(f"      ├─ 同步次数: {total}")
                if last_error:
                    print(f"      └─ 最后错误: {last_error}")
            print()
            
        except Exception as e:
            print(f"⚠️  历史文件读取失败: {e}\n")
    else:
        print("⚠️  同步历史不存在（可能从未同步过）\n")
    
    # 3. 检查数据库
    db_file = Path(EMAIL_SYNC_DB)
    if db_file.exists():
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # 获取最近同步时间
            cursor.execute("""
                SELECT 
                    account_id,
                    COUNT(*) as total_emails,
                    MAX(last_synced) as last_sync_time
                FROM emails
                GROUP BY account_id
                ORDER BY last_sync_time DESC
            """)
            
            results = cursor.fetchall()
            
            print("💾 数据库状态:")
            if results:
                for account_id, total, last_sync in results:
                    time_ago = format_time_ago(last_sync)
                    print(f"   📧 {account_id}: {total} 封邮件 (最后同步: {time_ago})")
                print()
            else:
                print("   ⚠️  数据库中暂无邮件\n")
            
            conn.close()
        except Exception as e:
            print(f"⚠️  数据库读取失败: {e}\n")
    else:
        print("⚠️  数据库文件不存在\n")
    
    # 4. 预计下次同步时间
    if config_file.exists() and history_file.exists():
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            sync_history = history.get('sync_history', [])
            if sync_history:
                last_sync_str = sync_history[-1].get('timestamp', '')
                if last_sync_str:
                    last_sync = datetime.fromisoformat(last_sync_str.replace('Z', '+00:00'))
                    next_sync = last_sync + timedelta(minutes=interval)
                    now = datetime.now()
                    if last_sync.tzinfo:
                        from datetime import timezone
                        now = now.replace(tzinfo=timezone.utc)
                    
                    if next_sync > now:
                        remaining = (next_sync - now).total_seconds()
                        minutes = int(remaining / 60)
                        seconds = int(remaining % 60)
                        print(f"⏰ 预计下次同步: {minutes} 分 {seconds} 秒后\n")
                    else:
                        print("⏰ 预计下次同步: 即将开始（已超时）\n")
        except Exception as e:
            pass
    
    print("=" * 80)
    print("💡 提示:")
    print("   - 如果长时间没有新的同步记录，请检查 MCP 服务是否正在运行")
    print("   - 可以重复运行此脚本来查看实时状态")
    print("   - 监控命令: watch -n 10 python scripts/monitor_sync.py")
    print("=" * 80)

if __name__ == "__main__":
    try:
        check_sync_status()
    except KeyboardInterrupt:
        print("\n\n👋 监控已停止")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

