#!/usr/bin/env python3
"""
测试混合查询模式
"""
import sys
from pathlib import Path

# 添加src目录到Python路径
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from operations.hybrid_manager import HybridEmailManager
from core.hybrid_config import get_hybrid_config

def test_hybrid_mode():
    """测试混合模式功能"""
    print("=== 测试混合查询模式 ===\n")
    
    # 1. 检查配置
    config = get_hybrid_config()
    print(f"1. 混合模式状态: {'✅ 已启用' if config.is_enabled else '❌ 已禁用'}")
    print(f"   数据新鲜度阈值: {config.get_freshness_threshold()} 分钟\n")
    
    if not config.is_enabled:
        print("混合模式未启用，请编辑 hybrid_config.json 启用")
        return
    
    # 2. 初始化混合管理器
    hybrid_mgr = HybridEmailManager(freshness_threshold_minutes=5)
    print("2. 混合管理器初始化成功\n")
    
    # 3. 测试列表邮件（使用缓存）
    print("3. 测试列表邮件（优先使用缓存）")
    emails = hybrid_mgr.list_emails(
        folder="INBOX",
        limit=5,
        unread_only=False,
        freshness_required=False  # 使用缓存
    )
    print(f"   获取到 {len(emails)} 封邮件")
    if emails and emails[0].get('_from_cache'):
        print("   ✅ 数据来自本地缓存")
    
    # 4. 测试列表邮件（强制更新）
    print("\n4. 测试列表邮件（强制从远程获取）")
    emails_fresh = hybrid_mgr.list_emails(
        folder="INBOX",
        limit=5,
        unread_only=False,
        freshness_required=True  # 强制更新
    )
    print(f"   获取到 {len(emails_fresh)} 封邮件")
    
    # 5. 测试搜索功能
    print("\n5. 测试搜索邮件")
    search_results = hybrid_mgr.search_emails(
        query="test",
        limit=5,
        freshness_required=None  # 自动判断
    )
    print(f"   搜索到 {len(search_results)} 封邮件")
    
    # 6. 测试数据新鲜度状态
    print("\n6. 数据新鲜度状态")
    freshness_status = hybrid_mgr.get_freshness_status()
    for account_id, status in freshness_status.items():
        print(f"   账户: {status['email']}")
        for folder, folder_status in status.get('folders', {}).items():
            fresh_icon = "🟢" if folder_status['is_fresh'] else "🔴"
            print(f"     {fresh_icon} {folder}: {folder_status['age_minutes']} 分钟前更新")
    
    # 7. 测试写操作
    if emails:
        print("\n7. 测试标记邮件（写透式更新）")
        email_id = emails[0].get('uid') or emails[0].get('id')
        if email_id:
            result = hybrid_mgr.mark_emails([email_id], "read")
            if result.get('success'):
                print("   ✅ 标记成功（远程和本地都已更新）")
            else:
                print(f"   ❌ 标记失败: {result.get('error')}")
    
    print("\n测试完成！")

if __name__ == "__main__":
    test_hybrid_mode()