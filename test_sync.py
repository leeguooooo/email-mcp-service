#!/usr/bin/env python3
"""
测试邮件同步功能
"""
import sys
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('test_sync.log')
    ]
)

logger = logging.getLogger(__name__)

def test_sync_status():
    """测试同步状态"""
    logger.info("="*60)
    logger.info("测试 1: 检查同步状态")
    logger.info("="*60)
    
    try:
        from src.operations.email_sync import EmailSyncManager
        
        sync_manager = EmailSyncManager()
        status = sync_manager.get_sync_status()
        
        logger.info(f"✅ 同步管理器初始化成功")
        logger.info(f"📊 同步状态: {status}")
        
        sync_manager.close()
        return True
    except Exception as e:
        logger.error(f"❌ 同步状态检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_force_sync():
    """测试强制同步单个账户"""
    logger.info("\n" + "="*60)
    logger.info("测试 2: 强制同步")
    logger.info("="*60)
    
    try:
        from src.account_manager import AccountManager
        from src.operations.email_sync import EmailSyncManager
        
        # 获取第一个账户
        account_mgr = AccountManager()
        accounts = account_mgr.list_accounts()
        
        if not accounts:
            logger.warning("⚠️ 没有配置账户")
            return False
        
        account = accounts[0]
        logger.info(f"📧 测试账户: {account['email']}")
        
        # 执行同步
        sync_manager = EmailSyncManager()
        logger.info(f"🔄 开始同步...")
        
        result = sync_manager.sync_single_account(account['id'], full_sync=False)
        
        logger.info(f"✅ 同步完成!")
        logger.info(f"📊 结果: {result}")
        
        if result.get('success'):
            logger.info(f"   - 文件夹数: {result.get('folders_synced', 0)}")
            logger.info(f"   - 新增邮件: {result.get('emails_added', 0)}")
            logger.info(f"   - 更新邮件: {result.get('emails_updated', 0)}")
        else:
            logger.error(f"   - 错误: {result.get('error')}")
        
        sync_manager.close()
        return result.get('success', False)
        
    except Exception as e:
        logger.error(f"❌ 强制同步失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_search_cached():
    """测试搜索缓存邮件"""
    logger.info("\n" + "="*60)
    logger.info("测试 3: 搜索缓存邮件")
    logger.info("="*60)
    
    try:
        from src.operations.email_sync import EmailSyncManager
        
        sync_manager = EmailSyncManager()
        
        # 获取最近邮件
        logger.info("🔍 获取最近20封邮件...")
        emails = sync_manager.get_recent_emails(limit=20)
        
        if emails:
            logger.info(f"✅ 找到 {len(emails)} 封缓存邮件")
            for i, email in enumerate(emails[:5], 1):
                logger.info(f"   {i}. {email.get('subject', '无主题')}")
                logger.info(f"      发件人: {email.get('sender', '未知')}")
                logger.info(f"      时间: {email.get('date_sent', '未知')}")
        else:
            logger.warning("⚠️ 没有找到缓存邮件，请先执行同步")
        
        sync_manager.close()
        return len(emails) > 0 if emails else False
        
    except Exception as e:
        logger.error(f"❌ 搜索缓存失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_health_monitor():
    """测试健康监控"""
    logger.info("\n" + "="*60)
    logger.info("测试 4: 健康监控")
    logger.info("="*60)
    
    try:
        from src.background.sync_health_monitor import get_health_monitor
        
        monitor = get_health_monitor()
        
        # 获取整体健康状况
        overall = monitor.get_overall_health()
        logger.info(f"✅ 整体健康状况: {overall.get('status')}")
        logger.info(f"📊 统计:")
        logger.info(f"   - 总账户数: {overall.get('total_accounts', 0)}")
        logger.info(f"   - 健康账户: {overall.get('healthy_accounts', 0)}")
        logger.info(f"   - 平均分数: {overall.get('average_health_score', 0):.1f}/100")
        logger.info(f"   - 成功率: {overall.get('success_rate', 0):.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 健康监控测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_connection_pool():
    """测试连接池"""
    logger.info("\n" + "="*60)
    logger.info("测试 5: 连接池统计")
    logger.info("="*60)
    
    try:
        from src.connection_pool import get_connection_pool
        
        pool = get_connection_pool()
        stats = pool.get_stats()
        
        logger.info(f"✅ 连接池统计:")
        logger.info(f"   - 总创建: {stats['stats']['total_created']}")
        logger.info(f"   - 复用次数: {stats['stats']['total_reused']}")
        logger.info(f"   - 已关闭: {stats['stats']['total_closed']}")
        logger.info(f"   - 等待次数: {stats['stats']['connection_waits']}")
        logger.info(f"   - 超时次数: {stats['stats']['wait_timeouts']}")
        logger.info(f"   - 活跃连接: {stats['total_active_connections']}")
        
        if stats['stats']['total_created'] > 0:
            reuse_rate = (stats['stats']['total_reused'] / 
                         (stats['stats']['total_created'] + stats['stats']['total_reused'])) * 100
            logger.info(f"   - 复用率: {reuse_rate:.1f}%")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 连接池测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    logger.info(f"🚀 邮件同步测试开始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📝 日志文件: test_sync.log")
    
    results = []
    
    # 执行测试
    results.append(("同步状态检查", test_sync_status()))
    results.append(("强制同步", test_force_sync()))
    results.append(("搜索缓存", test_search_cached()))
    results.append(("健康监控", test_health_monitor()))
    results.append(("连接池", test_connection_pool()))
    
    # 汇总结果
    logger.info("\n" + "="*60)
    logger.info("📊 测试结果汇总")
    logger.info("="*60)
    
    passed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{status} - {name}")
        if result:
            passed += 1
    
    logger.info(f"\n总计: {passed}/{len(results)} 测试通过")
    
    if passed == len(results):
        logger.info("🎉 所有测试通过!")
        return 0
    else:
        logger.warning(f"⚠️ {len(results) - passed} 个测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(main())

