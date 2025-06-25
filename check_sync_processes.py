#!/usr/bin/env python3
"""
检查同步相关进程
"""
import subprocess
import sys

def check_processes():
    """检查同步相关的进程"""
    print("=== 检查邮件同步相关进程 ===\n")
    
    # 检查Python进程
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        lines = result.stdout.split('\n')
        
        sync_processes = []
        for line in lines:
            if 'python' in line and ('sync' in line or 'email' in line):
                if 'check_sync_processes' not in line:  # 排除当前脚本
                    sync_processes.append(line)
        
        if sync_processes:
            print(f"找到 {len(sync_processes)} 个同步相关进程:")
            for i, process in enumerate(sync_processes, 1):
                print(f"{i}. {process}")
        else:
            print("✅ 未发现同步相关进程")
            
    except Exception as e:
        print(f"检查进程失败: {e}")
    
    # 检查PID文件
    print("\n=== 检查PID文件 ===")
    from pathlib import Path
    
    pid_files = ['sync_manager.pid', 'email_sync.pid', 'background_sync.pid']
    for pid_file in pid_files:
        if Path(pid_file).exists():
            try:
                with open(pid_file, 'r') as f:
                    pid = f.read().strip()
                print(f"❌ 发现PID文件: {pid_file} (PID: {pid})")
            except:
                print(f"❌ 发现PID文件: {pid_file} (无法读取)")
        else:
            print(f"✅ 无PID文件: {pid_file}")

if __name__ == "__main__":
    check_processes()