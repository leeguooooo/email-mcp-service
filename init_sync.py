#!/usr/bin/env python3
"""
邮件数据库初始化和同步工具
用于首次设置和手动触发同步
"""

import sys
import json
import logging
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_config():
    """检查配置文件是否存在"""
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

def check_accounts():
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

def init_database():
    """初始化数据库并进行首次同步"""
    try:
        logger.info("开始初始化邮件数据库...")
        
        # 导入同步模块
        from operations.email_sync import EmailSyncManager
        
        # 创建同步管理器
        sync_manager = EmailSyncManager()
        
        # 执行首次同步（会自动获取6个月历史）
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

def start_background_sync():
    """启动后台自动同步"""
    try:
        logger.info("启动后台自动同步...")
        
        from background.sync_scheduler import start_background_sync
        scheduler = start_background_sync()
        
        logger.info("✅ 后台同步已启动")
        logger.info("   - 增量同步: 每15分钟")
        logger.info("   - 完全同步: 每天凌晨2点")
        
        # 保持运行
        logger.info("按 Ctrl+C 停止...")
        try:
            import time
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("停止后台同步...")
            scheduler.stop_scheduler()
            logger.info("✅ 后台同步已停止")
            
    except Exception as e:
        logger.error(f"❌ 启动后台同步失败: {e}")
        return False

def main():
    """主入口"""
    # 支持命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "init":
            # 直接初始化数据库
            if check_config() and check_accounts():
                init_database()
            return
            
        elif command == "daemon":
            # 后台守护进程模式
            if check_config() and check_accounts():
                logger.info("启动邮件同步守护进程...")
                logger.info("使用 Ctrl+C 停止，或者在新终端运行: pkill -f init_sync.py")
                start_background_sync()
            return
            
        elif command == "help":
            print("MCP Email Service 邮件同步工具")
            print("用法:")
            print("  python init_sync.py         - 交互式模式")
            print("  python init_sync.py init    - 直接初始化数据库")
            print("  python init_sync.py daemon  - 后台守护进程模式")
            print("  python init_sync.py help    - 显示帮助")
            return
    
    # 交互式模式
    print("=== MCP Email Service 邮件同步工具 ===\n")
    
    # 1. 检查配置文件
    if not check_config():
        sys.exit(1)
    
    # 2. 检查账户配置
    if not check_accounts():
        sys.exit(1)
    
    # 3. 询问用户操作
    print("\n请选择操作:")
    print("1. 初始化数据库并首次同步")
    print("2. 启动后台守护进程（持续运行）")
    print("3. 仅初始化数据库")
    print("0. 退出")
    
    try:
        choice = input("\n请输入选择 (0-3): ").strip()
        
        if choice == "1":
            if init_database():
                print("\n是否启动后台守护进程? (y/n): ", end="")
                if input().lower().startswith('y'):
                    logger.info("启动后台守护进程...")
                    logger.info("使用 Ctrl+C 停止")
                    start_background_sync()
        elif choice == "2":
            logger.info("启动后台守护进程...")
            logger.info("使用 Ctrl+C 停止")
            start_background_sync()
        elif choice == "3":
            init_database()
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