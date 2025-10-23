#!/usr/bin/env python3
"""
Connection test script for MCP Email Service
Tests IMAP connection for all configured accounts
"""

import json
import imaplib
import sys
from pathlib import Path

def test_connection(email, password, provider="other"):
    """Test IMAP connection for a single account"""
    print(f"\n🔍 Testing connection for: {email}")
    
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
            print(f"❌ Unknown provider for {domain}, skipping...")
            return False
    
    print(f"📧 IMAP Server: {imap_host}:{imap_port}")
    
    try:
        # Connect to IMAP server
        print("🔌 Connecting to IMAP server...")
        imap = imaplib.IMAP4_SSL(imap_host, imap_port)
        
        # Special handling for 163.com
        if provider == "163" or email.endswith("@163.com"):
            print("🔐 Using IMAP ID for 163.com...")
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
                        if 'OK' in resp_str:
                            print("✅ IMAP ID sent successfully")
                        break
                    elif resp_str.startswith('*'):
                        continue
                    else:
                        break
            except Exception as e:
                print(f"⚠️  IMAP ID failed: {e}, continuing anyway...")
        
        # Login
        print("🔑 Attempting login...")
        imap.login(email, password)
        
        # List folders to verify connection
        print("📁 Listing folders...")
        status, folders = imap.list()
        
        if status == 'OK':
            print(f"✅ SUCCESS! Connection established for {email}")
            print(f"📊 Found {len(folders)} folders")
            
            # Try to select INBOX
            status, data = imap.select('INBOX')
            if status == 'OK':
                print(f"📥 INBOX has {data[0].decode()} messages")
            
            imap.logout()
            return True
        else:
            print(f"❌ Failed to list folders for {email}")
            imap.logout()
            return False
            
    except imaplib.IMAP4.error as e:
        print(f"❌ IMAP Error: {str(e)}")
        if "AUTHENTICATIONFAILED" in str(e):
            print("💡 Hint: Check your password/auth code")
            if provider == "gmail" or email.endswith("@gmail.com"):
                print("💡 Gmail requires an app-specific password, not your regular password")
            elif provider == "qq" or email.endswith("@qq.com"):
                print("💡 QQ邮箱 requires an authorization code, not your regular password")
        return False
    except Exception as e:
        print(f"❌ Connection Error: {type(e).__name__}: {str(e)}")
        return False

def main():
    """Test all configured accounts"""
    # 脚本在scripts/目录下，需要回到项目根目录找到data/accounts.json
    project_root = Path(__file__).parent.parent
    accounts_file = project_root / "data" / "accounts.json"
    
    if not accounts_file.exists():
        print("❌ No accounts.json file found!")
        print("💡 Run 'uv run python setup.py' first to configure accounts")
        return
    
    try:
        with open(accounts_file, 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Error reading accounts.json: {e}")
        return
    
    accounts = config.get("accounts", {})
    if not accounts:
        print("❌ No accounts configured!")
        print("💡 Run 'uv run python setup.py' to add accounts")
        return
    
    print(f"🚀 Testing {len(accounts)} configured account(s)...")
    print("=" * 50)
    
    success_count = 0
    failed_accounts = []
    
    for account_id, account in accounts.items():
        email = account.get("email")
        password = account.get("password")
        provider = account.get("provider", "other")
        
        if not email or not password:
            print(f"⚠️  Skipping account with missing email or password")
            continue
        
        if test_connection(email, password, provider):
            success_count += 1
        else:
            failed_accounts.append(email)
    
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY:")
    print(f"✅ Successful: {success_count}/{len(accounts)}")
    print(f"❌ Failed: {len(failed_accounts)}/{len(accounts)}")
    
    if failed_accounts:
        print("\n❌ Failed accounts:")
        for email in failed_accounts:
            print(f"  - {email}")
        print("\n💡 Tips for failed accounts:")
        print("  1. Check your password/auth code")
        print("  2. Gmail needs app-specific password")
        print("  3. QQ邮箱 needs authorization code")
        print("  4. Enable IMAP in your email settings")
        print("  5. Check for 2FA or security restrictions")

if __name__ == "__main__":
    main()