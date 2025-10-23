#!/usr/bin/env python3
"""
邮箱账户配置脚本
支持配置多个邮箱账户
"""
import json
import os
import sys
import imaplib
from pathlib import Path
from getpass import getpass

def load_existing_config():
    """加载现有配置"""
    # 使用 data/ 目录下的 accounts.json
    config_file = Path(__file__).parent / 'data' / 'accounts.json'
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"accounts": {}, "default_account": None}
    return {"accounts": {}, "default_account": None}

def save_config(config):
    """保存配置"""
    # 使用 data/ 目录下的 accounts.json
    config_file = Path(__file__).parent / 'data' / 'accounts.json'
    # 确保 data 目录存在
    config_file.parent.mkdir(exist_ok=True)
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    print(f"\n✅ 配置已保存到: {config_file}")

def print_providers():
    """打印支持的邮箱提供商"""
    print("\n📧 支持的邮箱提供商:")
    print("1. 163邮箱 (完全支持)")
    print("2. Gmail (需要应用专用密码)")
    print("3. QQ邮箱 (需要授权码)")
    print("4. Outlook/Hotmail")
    print("5. 自定义邮箱服务器")

def get_provider_config(provider):
    """获取提供商特定的配置指南"""
    guides = {
        '163': """
163邮箱配置步骤:
1. 登录 https://mail.163.com
2. 点击右上角设置 → POP3/SMTP/IMAP
3. 开启 IMAP/SMTP 服务
4. 完成手机验证后获取授权码
⚠️  使用授权码，不是邮箱密码！
""",
        'gmail': """
Gmail配置步骤:
1. 开启两步验证: https://myaccount.google.com/security
2. 生成应用专用密码: https://myaccount.google.com/apppasswords
3. 选择"邮件"和您的设备
4. 使用生成的16位密码
""",
        'qq': """
QQ邮箱配置步骤:
1. 登录 https://mail.qq.com
2. 设置 → 账户 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务
3. 开启 IMAP/SMTP 服务
4. 生成授权码（需要发送短信）
⚠️  使用授权码，不是QQ密码！
""",
        'outlook': """
Outlook/Hotmail配置步骤:
1. 使用您的Microsoft账户邮箱地址
2. 直接使用邮箱密码登录
3. 如果开启了两步验证，需要生成应用密码
4. 访问: https://account.microsoft.com/security
""",
        'custom': """
自定义邮箱配置需要提供:
- IMAP服务器地址和端口
- SMTP服务器地址和端口（可选）
- 邮箱地址和密码
"""
    }
    return guides.get(provider, "")

def add_account(config):
    """添加新账户"""
    print("\n➕ 添加新邮箱账户")
    print_providers()
    
    provider_map = {'1': '163', '2': 'gmail', '3': 'qq', '4': 'outlook', '5': 'custom'}
    choice = input("\n请选择邮箱类型 (1-5): ").strip()
    provider = provider_map.get(choice)
    
    if not provider:
        print("❌ 无效的选择")
        return
    
    # 显示配置指南
    guide = get_provider_config(provider)
    if guide:
        print(guide)
    
    # 输入基本信息
    email = input("邮箱地址: ").strip()
    if not email:
        print("❌ 邮箱地址不能为空")
        return
    
    # 生成账户ID
    account_id = email.split('@')[0] + '_' + provider
    if account_id in config['accounts']:
        print(f"⚠️  账户 {email} 已存在")
        if input("是否覆盖? (y/n): ").lower() != 'y':
            return
    
    # 输入密码/授权码
    password = getpass(f"{'授权码' if provider in ['163', 'qq'] else '密码'}: ")
    if not password:
        print("❌ 密码/授权码不能为空")
        return
    
    # 构建账户配置
    account_config = {
        "email": email,
        "password": password,
        "provider": provider,
        "description": input("账户描述 (可选): ").strip() or f"{provider}邮箱"
    }
    
    # 自定义邮箱需要额外配置
    if provider == 'custom':
        account_config['imap_server'] = input("IMAP服务器地址: ").strip()
        imap_port = input("IMAP端口 (默认993): ").strip()
        account_config['imap_port'] = int(imap_port) if imap_port else 993
        
        if input("是否配置SMTP服务器? (y/n): ").lower() == 'y':
            account_config['smtp_server'] = input("SMTP服务器地址: ").strip()
            smtp_port = input("SMTP端口 (默认465): ").strip()
            account_config['smtp_port'] = int(smtp_port) if smtp_port else 465
    
    # 保存配置
    config['accounts'][account_id] = account_config
    
    # 设置默认账户
    if not config['default_account'] or input("设置为默认账户? (y/n): ").lower() == 'y':
        config['default_account'] = account_id
    
    print(f"\n✅ 账户 {email} 添加成功！")

def list_accounts(config):
    """列出所有账户"""
    if not config['accounts']:
        print("\n📭 还没有配置任何账户")
        return
    
    print("\n📧 已配置的邮箱账户:")
    for account_id, account in config['accounts'].items():
        default_mark = " ⭐" if account_id == config['default_account'] else ""
        print(f"\n• {account_id}{default_mark}")
        print(f"  邮箱: {account['email']}")
        print(f"  类型: {account['provider']}")
        print(f"  描述: {account.get('description', '无')}")

def remove_account(config):
    """删除账户"""
    if not config['accounts']:
        print("\n📭 还没有配置任何账户")
        return
    
    list_accounts(config)
    account_id = input("\n请输入要删除的账户ID: ").strip()
    
    if account_id in config['accounts']:
        if input(f"确认删除 {config['accounts'][account_id]['email']}? (y/n): ").lower() == 'y':
            del config['accounts'][account_id]
            if config['default_account'] == account_id:
                config['default_account'] = list(config['accounts'].keys())[0] if config['accounts'] else None
            print("✅ 删除成功")
    else:
        print("❌ 账户不存在")

def set_default_account(config):
    """设置默认账户"""
    if not config['accounts']:
        print("\n📭 还没有配置任何账户")
        return
    
    list_accounts(config)
    account_id = input("\n请输入要设为默认的账户ID: ").strip()
    
    if account_id in config['accounts']:
        config['default_account'] = account_id
        print(f"✅ 已将 {config['accounts'][account_id]['email']} 设为默认账户")
    else:
        print("❌ 账户不存在")

def test_single_connection(email, password, provider="other"):
    """测试单个账户的IMAP连接"""
    # Provider-specific IMAP settings
    imap_settings = {
        "163": ("imap.163.com", 993),
        "gmail": ("imap.gmail.com", 993),
        "qq": ("imap.qq.com", 993),
        "outlook": ("outlook.office365.com", 993),
        "hotmail": ("outlook.office365.com", 993),
    }
    
    # Determine IMAP server
    if provider in imap_settings:
        imap_host, imap_port = imap_settings[provider]
    else:
        # Try to guess from email domain
        domain = email.split('@')[1].lower()
        if domain == "163.com":
            imap_host, imap_port = imap_settings["163"]
        elif domain == "gmail.com":
            imap_host, imap_port = imap_settings["gmail"]
        elif domain == "qq.com":
            imap_host, imap_port = imap_settings["qq"]
        elif domain in ["outlook.com", "hotmail.com"]:
            imap_host, imap_port = imap_settings["outlook"]
        else:
            return False, f"未知的邮箱提供商: {domain}"
    
    try:
        # Connect to IMAP server
        imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        
        # Special handling for 163.com
        if provider == "163" or email.endswith("@163.com"):
            try:
                # Send IMAP ID command manually
                id_args = [
                    "name", "Mozilla Thunderbird",
                    "version", "91.0", 
                    "vendor", "Mozilla",
                    "support-url", "https://support.mozilla.org/"
                ]
                
                tag = imap._new_tag()
                id_string = " ".join(f'"{arg}"' for arg in id_args)
                command = f'{tag.decode()} ID ({id_string})'
                imap.send(command.encode() + b'\r\n')
                
                # Read response
                while True:
                    resp = imap.readline()
                    resp_str = resp.decode().strip()
                    if resp_str.startswith(tag.decode()):
                        break
                    elif resp_str.startswith('*'):
                        continue
                    else:
                        break
            except:
                pass  # Continue even if IMAP ID fails
        
        # Login
        imap.login(email, password)
        
        # List folders to verify connection
        status, folders = imap.list()
        
        if status == 'OK':
            # Try to select INBOX
            status, data = imap.select('INBOX', readonly=True)
            message_count = data[0].decode() if status == 'OK' else "未知"
            imap.logout()
            return True, f"连接成功! 收件箱有 {message_count} 封邮件"
        else:
            imap.logout()
            return False, "无法获取邮箱文件夹列表"
            
    except imaplib.IMAP4.error as e:
        error_msg = str(e)
        if "AUTHENTICATIONFAILED" in error_msg:
            hint = ""
            if provider == "gmail" or email.endswith("@gmail.com"):
                hint = "\n💡 Gmail需要使用应用专用密码，而不是常规密码"
            elif provider == "qq" or email.endswith("@qq.com"):
                hint = "\n💡 QQ邮箱需要使用授权码，而不是QQ密码"
            return False, f"认证失败: {error_msg}{hint}"
        return False, f"IMAP错误: {error_msg}"
    except Exception as e:
        return False, f"连接错误: {type(e).__name__}: {str(e)}"

def test_connections(config):
    """测试所有账户的连接"""
    if not config['accounts']:
        print("\n📭 还没有配置任何账户")
        return
    
    print(f"\n🚀 开始测试 {len(config['accounts'])} 个账户的连接...")
    print("=" * 50)
    
    success_count = 0
    failed_accounts = []
    
    for account_id, account in config['accounts'].items():
        email = account.get("email")
        password = account.get("password")
        provider = account.get("provider", "other")
        
        print(f"\n🔍 测试账户: {account_id}")
        print(f"📧 邮箱: {email}")
        
        if not email or not password:
            print("❌ 缺少邮箱或密码")
            failed_accounts.append((account_id, "配置不完整"))
            continue
        
        success, message = test_single_connection(email, password, provider)
        if success:
            print(f"✅ {message}")
            success_count += 1
        else:
            print(f"❌ {message}")
            failed_accounts.append((account_id, message))
    
    print("\n" + "=" * 50)
    print("📊 测试汇总:")
    print(f"✅ 成功: {success_count}/{len(config['accounts'])}")
    print(f"❌ 失败: {len(failed_accounts)}/{len(config['accounts'])}")
    
    if failed_accounts:
        print("\n❌ 失败的账户:")
        for account_id, error in failed_accounts:
            print(f"  • {account_id}: {error}")
    
    input("\n按回车键继续...")

def migrate_from_env():
    """从环境变量迁移配置"""
    from dotenv import load_dotenv
    load_dotenv()
    
    email = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('EMAIL_PASSWORD')
    provider = os.getenv('EMAIL_PROVIDER', '163')
    
    if email and password:
        config = load_existing_config()
        
        # 检查是否已经导入过该邮箱
        for account_id, account in config['accounts'].items():
            if account['email'] == email:
                # 已经存在，不再提示
                return False
        
        print(f"\n🔄 检测到环境变量配置:")
        print(f"邮箱: {email}")
        print(f"提供商: {provider}")
        
        if input("是否导入到账户配置? (y/n): ").lower() == 'y':
            account_id = f"env_{provider}"
            config['accounts'][account_id] = {
                "email": email,
                "password": password,
                "provider": provider,
                "description": "从环境变量导入"
            }
            if not config['default_account']:
                config['default_account'] = account_id
            save_config(config)
            print("✅ 导入成功！")
            return True
    return False

def main():
    """主函数"""
    print("🎯 MCP Email Service - 邮箱账户配置工具")
    print("=" * 50)
    
    # 检查是否有环境变量配置
    migrate_from_env()
    
    config = load_existing_config()
    
    while True:
        print("\n📋 请选择操作:")
        print("1. 添加邮箱账户")
        print("2. 查看所有账户")
        print("3. 删除账户")
        print("4. 设置默认账户")
        print("5. 测试连接")
        print("6. 保存并退出")
        print("0. 退出不保存")
        
        choice = input("\n请选择 (0-6): ").strip()
        
        if choice == '1':
            add_account(config)
        elif choice == '2':
            list_accounts(config)
        elif choice == '3':
            remove_account(config)
        elif choice == '4':
            set_default_account(config)
        elif choice == '5':
            test_connections(config)
        elif choice == '6':
            save_config(config)
            print("\n👋 再见！")
            break
        elif choice == '0':
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效的选择")

if __name__ == "__main__":
    main()