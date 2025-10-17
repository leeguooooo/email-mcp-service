#!/usr/bin/env python3
"""测试 email lookup fallback 功能"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.account_manager import AccountManager
from src.legacy_operations import get_email_detail, fetch_emails

def test_email_lookup_fallback():
    """测试使用邮箱地址查找账户"""
    print("=" * 60)
    print("测试: Email Lookup Fallback")
    print("=" * 60)
    
    account_mgr = AccountManager()
    
    # 测试 1: 使用真实 ID（应该工作）
    print("\n1️⃣  使用真实 ID: leeguoo_qq")
    account = account_mgr.get_account("leeguoo_qq")
    if account and account.get('id') == 'leeguoo_qq':
        print(f"   ✅ 成功: {account.get('email')}")
    else:
        print(f"   ❌ 失败")
        return False
    
    # 测试 2: 使用邮箱地址（应该回退查找）
    print("\n2️⃣  使用邮箱地址: leeguoo@qq.com")
    account = account_mgr.get_account("leeguoo@qq.com")
    if account and account.get('id') == 'leeguoo_qq':
        print(f"   ✅ 成功: 解析到 ID = {account.get('id')}")
    else:
        print(f"   ❌ 失败: 未能解析到正确的 ID")
        return False
    
    # 测试 3: 在实际操作中使用邮箱地址
    print("\n3️⃣  使用邮箱地址调用 get_email_detail")
    try:
        # 先获取一个邮件 ID
        result = fetch_emails(limit=1, account_id="leeguoo_qq")
        if result.get('emails'):
            email_id = result['emails'][0]['id']
            
            # 使用邮箱地址作为 account_id
            detail = get_email_detail(email_id, account_id="leeguoo@qq.com")
            
            if 'error' not in detail:
                print(f"   ✅ 成功获取邮件")
                print(f"   主题: {detail.get('subject', 'N/A')[:50]}")
                print(f"   返回的 account_id: {detail.get('account_id')}")
                return True
            else:
                print(f"   ❌ 失败: {detail.get('error')}")
                return False
        else:
            print("   ⚠️  没有邮件可测试")
            return True
    except Exception as e:
        print(f"   ❌ 异常: {e}")
        return False

def test_env_account_id():
    """测试环境变量账户的 ID"""
    print("\n" + "=" * 60)
    print("测试: 环境变量账户 ID")
    print("=" * 60)
    
    account_mgr = AccountManager()
    
    # 检查是否有环境变量账户
    import os
    if os.getenv('EMAIL_ADDRESS'):
        print("\n发现环境变量账户")
        account = account_mgr.get_account()  # 获取默认账户
        
        if account and account.get('id'):
            print(f"   ✅ 环境变量账户有 ID: {account.get('id')}")
            return True
        else:
            print(f"   ❌ 环境变量账户没有 ID")
            return False
    else:
        print("\n   ⚠️  没有配置环境变量账户，跳过")
        return True

if __name__ == '__main__':
    print("\n" + "🧪 " * 20)
    print("Email Lookup Fallback 测试")
    print("🧪 " * 20 + "\n")
    
    # 测试 1: Email lookup fallback
    success1 = test_email_lookup_fallback()
    
    # 测试 2: 环境变量账户 ID
    success2 = test_env_account_id()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"Email Lookup Fallback:  {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"Environment Account ID: {'✅ PASS' if success2 else '❌ FAIL'}")
    
    if success1 and success2:
        print("\n🎉 所有测试通过！")
        print("\n✨ 新功能确认:")
        print("   • 可以使用邮箱地址作为 account_id")
        print("   • 自动解析到真实的账户键名")
        print("   • 环境变量账户有明确的 ID")
        sys.exit(0)
    else:
        print("\n⚠️  部分测试失败")
        sys.exit(1)


