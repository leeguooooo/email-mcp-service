#!/usr/bin/env python3
"""
命令行桥接脚本 - 让 n8n 能够调用 MCP 邮件工具
用法: python call_email_tool.py <tool_name> [json_args]
"""
import json
import sys
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

try:
    from src.account_manager import AccountManager
    from src.services.email_service import EmailService
    from src.services.communication_service import CommunicationService
    from src.services.folder_service import FolderService
    from src.services.system_service import SystemService
except ImportError as e:
    print(json.dumps({"error": f"Failed to import modules: {e}"}))
    sys.exit(1)

# 配置日志
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class EmailToolBridge:
    """邮件工具桥接器"""
    
    def __init__(self):
        """初始化桥接器"""
        try:
            self.account_manager = AccountManager()
            self.email_service = EmailService(self.account_manager)
            self.communication_service = CommunicationService(self.account_manager)
            self.folder_service = FolderService(self.account_manager)
            self.system_service = SystemService(self.account_manager)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize services: {e}")
    
    def list_unread_emails(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """获取未读邮件列表"""
        return self.email_service.list_emails(
            limit=args.get('limit', 20),
            unread_only=True,
            folder=args.get('folder', 'INBOX'),
            account_id=args.get('account_id')
        )
    
    def list_emails(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """获取邮件列表"""
        return self.email_service.list_emails(
            limit=args.get('limit', 50),
            unread_only=args.get('unread_only', False),
            folder=args.get('folder', 'INBOX'),
            account_id=args.get('account_id')
        )
    
    def get_email_detail(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """获取邮件详情"""
        if 'email_id' not in args:
            return {"error": "email_id is required"}
        
        return self.email_service.get_email_detail(
            email_id=args['email_id'],
            folder=args.get('folder', 'INBOX'),
            account_id=args.get('account_id')
        )
    
    def search_emails(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """搜索邮件"""
        return self.email_service.search_emails(
            query=args.get('query'),
            search_in=args.get('search_in', 'all'),
            date_from=args.get('date_from'),
            date_to=args.get('date_to'),
            folder=args.get('folder', 'all'),
            unread_only=args.get('unread_only', False),
            has_attachments=args.get('has_attachments'),
            limit=args.get('limit', 50),
            account_id=args.get('account_id')
        )
    
    def mark_emails_read(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """标记邮件为已读"""
        if 'email_ids' not in args:
            return {"error": "email_ids is required"}
        
        return self.email_service.mark_emails(
            email_ids=args['email_ids'],
            mark_as='read',
            folder=args.get('folder', 'INBOX'),
            account_id=args.get('account_id')
        )
    
    def list_accounts(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """列出所有账户"""
        try:
            accounts = self.account_manager.list_accounts()
            return {
                "success": True,
                "accounts": accounts
            }
        except Exception as e:
            return {"error": str(e)}
    
    def check_connection(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """检查连接状态"""
        return self.system_service.check_connection(args.get('account_id'))
    
    def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """调用指定工具"""
        method_name = tool_name.replace('-', '_')
        
        if hasattr(self, method_name):
            try:
                return getattr(self, method_name)(args)
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                return {"error": str(e), "success": False}
        else:
            return {"error": f"Unknown tool: {tool_name}", "success": False}


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python call_email_tool.py <tool_name> [json_args]",
            "available_tools": [
                "list_unread_emails",
                "list_emails", 
                "get_email_detail",
                "search_emails",
                "mark_emails_read",
                "list_accounts",
                "check_connection"
            ]
        }))
        sys.exit(1)
    
    tool_name = sys.argv[1]
    
    # 解析参数
    args = {}
    if len(sys.argv) > 2:
        try:
            args = json.loads(sys.argv[2])
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON arguments: {e}"}))
            sys.exit(1)
    
    # 创建桥接器并调用工具
    try:
        bridge = EmailToolBridge()
        result = bridge.call_tool(tool_name, args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e), "success": False}))
        sys.exit(1)


if __name__ == "__main__":
    main()
