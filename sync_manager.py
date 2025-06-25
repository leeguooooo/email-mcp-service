#!/usr/bin/env python3
"""
统一的邮件同步管理工具
确保只有一个后台同步进程运行
"""

import sys
import os
import json
import logging
import signal
import time
from pathlib import Path
from typing import Dict, Any, Optional

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SyncManager:
    """统一的同步管理器 - 单例模式"""
    
    _instance = None
    _lock_file = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.pid_file = Path("sync_manager.pid")
        self.scheduler = None
        self.running = False
        self._initialized = True
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def _is_running(self) -> bool:
        """检查是否已有同步进程在运行"""
        if not self.pid_file.exists():
            return False
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 检查进程是否存在
            try:
                os.kill(pid, 0)  # 不发送信号，只检查进程是否存在
                return True
            except OSError:
                # 进程不存在，删除pid文件
                self.pid_file.unlink()
                return False
        except (ValueError, FileNotFoundError):
            return False
    
    def _create_pid_file(self):
        """创建PID文件"""
        with open(self.pid_file, 'w') as f:
            f.write(str(os.getpid()))
    
    def _remove_pid_file(self):
        """删除PID文件"""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def check_config(self) -> bool:
        """检查配置文件"""
        config_file = Path("sync_config.json")
        if not config_file.exists():
            logger.info("创建配置文件...")
            example_file = Path("sync_config.json.example")
            if example_file.exists():
                import shutil
                shutil.copy(example_file, config_file)
                logger.info("✅ 配置文件已创建: sync_config.json")
            else:
                logger.error("❌ 找不到 sync_config.json.example 文件")
                return False
        return True
    
    def check_accounts(self) -> bool:
        """检查账户配置"""
        accounts_file = Path("accounts.json")
        if not accounts_file.exists():
            logger.error("❌ 找不到 accounts.json 文件")
            logger.info("请先运行: uv run python setup.py")
            return False
        
        try:
            with open(accounts_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                accounts = data.get('accounts', [])
                if not accounts:
                    logger.error("❌ 没有配置邮箱账户")
                    logger.info("请先运行: uv run python setup.py")
                    return False
                logger.info(f"✅ 找到 {len(accounts)} 个邮箱账户")
                return True
        except Exception as e:
            logger.error(f"❌ 读取账户配置失败: {e}")
            return False
    
    def init_database(self) -> bool:
        """初始化数据库"""
        try:
            logger.info("开始初始化邮件数据库...")
            
            from operations.email_sync import EmailSyncManager
            sync_manager = EmailSyncManager()
            
            logger.info("开始首次同步 (将获取最近6个月的邮件)...")
            result = sync_manager.sync_all_accounts(full_sync=False, max_workers=2)
            
            if result.get('success'):
                logger.info(f"✅ 同步成功!")
                logger.info(f"   - 同步账户: {result['accounts_synced']}/{result['total_accounts']}")
                logger.info(f"   - 新增邮件: {result['emails_added']}")
                logger.info(f"   - 更新邮件: {result['emails_updated']}")
                logger.info(f"   - 用时: {result['sync_time']:.1f}秒")
                return True
            else:
                logger.error(f"❌ 同步失败: {result.get('error', '未知错误')}")
                return False
        except Exception as e:
            logger.error(f"❌ 初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start_daemon(self) -> bool:
        """启动守护进程"""
        if self._is_running():
            logger.warning("❌ 同步进程已在运行")
            return False
        
        try:
            self._create_pid_file()
            
            from background.sync_scheduler import get_scheduler
            self.scheduler = get_scheduler()
            self.scheduler.start_scheduler()
            self.running = True
            
            logger.info("✅ 后台同步守护进程已启动")
            logger.info(f"   - 进程ID: {os.getpid()}")
            logger.info("   - 增量同步: 每15分钟")
            logger.info("   - 完全同步: 每天凌晨2点")
            logger.info("   - 使用 Ctrl+C 或 kill 命令停止")
            
            return True
        except Exception as e:
            logger.error(f"❌ 启动守护进程失败: {e}")
            self._remove_pid_file()
            return False
    
    def stop_daemon(self) -> bool:
        """停止守护进程"""
        if not self._is_running():
            logger.info("没有运行中的同步进程")
            return True
        
        try:
            # 读取PID
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # 发送终止信号
            os.kill(pid, signal.SIGTERM)
            
            # 等待进程结束
            for _ in range(10):  # 最多等待10秒
                if not self._is_running():
                    logger.info("✅ 同步进程已停止")
                    return True
                time.sleep(1)
            
            # 强制终止
            os.kill(pid, signal.SIGKILL)
            self._remove_pid_file()
            logger.info("✅ 同步进程已强制停止")
            return True
            
        except Exception as e:
            logger.error(f"❌ 停止进程失败: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        status = {
            'daemon_running': self._is_running(),
            'pid': None,
            'sync_status': None
        }
        
        if status['daemon_running']:
            try:
                with open(self.pid_file, 'r') as f:
                    status['pid'] = int(f.read().strip())
            except:
                pass
        
        try:
            from background.sync_scheduler import get_scheduler
            scheduler = get_scheduler()
            status['sync_status'] = scheduler.get_sync_status()
        except Exception as e:
            status['sync_error'] = str(e)
        
        return status
    
    def force_sync(self, full_sync: bool = False) -> Dict[str, Any]:
        """强制同步"""
        try:
            if self._is_running():
                from background.sync_scheduler import get_scheduler
                scheduler = get_scheduler()
                return scheduler.force_sync(full_sync)
            else:
                # 如果守护进程未运行，直接执行同步
                from operations.email_sync import EmailSyncManager
                sync_manager = EmailSyncManager()
                return sync_manager.sync_all_accounts(full_sync=full_sync, max_workers=2)
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def stop(self):
        """停止同步管理器"""
        if self.running and self.scheduler:
            self.scheduler.stop_scheduler()
            self.running = False
        self._remove_pid_file()
    
    def keep_alive(self):
        """保持进程运行"""
        try:
            while self.running:
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            logger.info("收到中断信号，停止同步...")
            self.stop()

def main():
    """主入口"""
    manager = SyncManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "init":
            # 初始化数据库
            if manager.check_config() and manager.check_accounts():
                manager.init_database()
            
        elif command == "start":
            # 启动守护进程
            if manager.check_config() and manager.check_accounts():
                if manager.start_daemon():
                    manager.keep_alive()
            
        elif command == "stop":
            # 停止守护进程
            manager.stop_daemon()
            
        elif command == "status":
            # 查看状态
            status = manager.get_status()
            print(json.dumps(status, indent=2, ensure_ascii=False))
            
        elif command == "sync":
            # 强制同步
            full_sync = len(sys.argv) > 2 and sys.argv[2] == "full"
            result = manager.force_sync(full_sync)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
        elif command == "help":
            print("MCP Email Service 同步管理工具")
            print("用法:")
            print("  python sync_manager.py init          - 初始化数据库")
            print("  python sync_manager.py start         - 启动守护进程")
            print("  python sync_manager.py stop          - 停止守护进程")
            print("  python sync_manager.py status        - 查看状态")
            print("  python sync_manager.py sync          - 强制增量同步")
            print("  python sync_manager.py sync full     - 强制完全同步")
            print("  python sync_manager.py help          - 显示帮助")
            
        else:
            print(f"未知命令: {command}")
            print("使用 'python sync_manager.py help' 查看帮助")
            sys.exit(1)
    else:
        # 交互式模式
        print("=== MCP Email Service 同步管理工具 ===\n")
        
        if not manager.check_config() or not manager.check_accounts():
            sys.exit(1)
        
        # 显示当前状态
        status = manager.get_status()
        if status['daemon_running']:
            print(f"✅ 同步守护进程正在运行 (PID: {status.get('pid', 'unknown')})")
        else:
            print("❌ 同步守护进程未运行")
        
        print("\n请选择操作:")
        print("1. 初始化数据库")
        print("2. 启动守护进程")
        print("3. 停止守护进程")
        print("4. 查看状态")
        print("5. 强制同步")
        print("0. 退出")
        
        try:
            choice = input("\n请输入选择 (0-5): ").strip()
            
            if choice == "1":
                manager.init_database()
            elif choice == "2":
                if manager.start_daemon():
                    manager.keep_alive()
            elif choice == "3":
                manager.stop_daemon()
            elif choice == "4":
                status = manager.get_status()
                print(json.dumps(status, indent=2, ensure_ascii=False))
            elif choice == "5":
                full = input("是否完全同步? (y/n): ").lower().startswith('y')
                result = manager.force_sync(full)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            elif choice == "0":
                print("退出")
                sys.exit(0)
            else:
                print("无效选择")
                sys.exit(1)
                
        except KeyboardInterrupt:
            print("\n\n操作已取消")
            sys.exit(0)
        except Exception as e:
            logger.error(f"运行出错: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()