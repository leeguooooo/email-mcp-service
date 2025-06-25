"""
混合工具处理器 - 集成本地缓存和远程查询
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from core.tool_handlers import ToolContext, EmailToolHandlers
from operations.hybrid_manager import HybridEmailManager
from operations.email_operations import EmailOperations
from operations.search_operations import SearchOperations

logger = logging.getLogger(__name__)

class HybridEmailToolHandlers(EmailToolHandlers):
    """支持混合查询的邮件工具处理器"""
    
    # 类级别的混合管理器实例（单例）
    _hybrid_manager = None
    
    @classmethod
    def get_hybrid_manager(cls) -> HybridEmailManager:
        """获取混合管理器单例"""
        if cls._hybrid_manager is None:
            cls._hybrid_manager = HybridEmailManager(freshness_threshold_minutes=5)
        return cls._hybrid_manager
    
    @staticmethod
    def handle_list_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """处理list_emails - 使用混合查询"""
        try:
            account_id = args.get('account_id')
            folder = args.get('folder', 'INBOX')
            limit = args.get('limit', 100)
            # 最少显示50封
            if limit < 50:
                limit = 50
            unread_only = args.get('unread_only', True)
            use_cache = args.get('use_cache', None)  # 新参数：控制缓存使用
            
            # 转换use_cache到freshness_required
            if use_cache is not None:
                freshness_required = not use_cache
            else:
                freshness_required = None  # 自动判断
            
            # 使用混合管理器
            hybrid_mgr = HybridEmailToolHandlers.get_hybrid_manager()
            
            # 对于未读邮件的特殊处理
            if unread_only and not account_id and folder == 'INBOX':
                # 多账户未读邮件 - 需要更新的数据
                freshness_required = True
            
            emails = hybrid_mgr.list_emails(
                account_id=account_id,
                folder=folder,
                limit=limit,
                unread_only=unread_only,
                freshness_required=freshness_required
            )
            
            # 格式化结果
            result = {
                'emails': emails,
                'total': len(emails),
                'unread_count': sum(1 for e in emails if not e.get('is_read', False)),
                'from_cache': emails[0].get('_from_cache', False) if emails else False
            }
            
            # 如果有警告，添加到结果中
            if emails and emails[0].get('_warning'):
                result['warning'] = emails[0]['_warning']
            
            return HybridEmailToolHandlers._format_email_list(result, ctx)
            
        except Exception as e:
            logger.error(f"Hybrid list emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_search_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """处理search_emails - 使用混合查询"""
        try:
            query = args['query']
            account_id = args.get('account_id')
            search_in = args.get('search_in', 'all')
            date_from = args.get('date_from')
            date_to = args.get('date_to')
            limit = args.get('limit', 100)
            use_cache = args.get('use_cache', None)
            
            # 转换use_cache到freshness_required
            if use_cache is not None:
                freshness_required = not use_cache
            else:
                freshness_required = None
            
            # 使用混合管理器
            hybrid_mgr = HybridEmailToolHandlers.get_hybrid_manager()
            
            emails = hybrid_mgr.search_emails(
                query=query,
                account_id=account_id,
                search_in=search_in,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
                freshness_required=freshness_required
            )
            
            # 格式化结果
            result = {
                'emails': emails,
                'total': len(emails),
                'query': query
            }
            
            if not emails:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('no_email')}\n搜索条件: {query}"
                }]
            
            # 格式化邮件列表
            text_parts = [
                f"🔍 搜索 '{query}' 找到 {len(emails)} 封邮件\n"
            ]
            
            for email in emails[:limit]:
                status = "🔴" if not email.get('is_read', False) else "📧"
                date_str = email.get('date_sent', 'Unknown date')
                if isinstance(date_str, datetime):
                    date_str = date_str.strftime('%Y-%m-%d %H:%M')
                
                text_parts.append(
                    f"\n{status} {email.get('subject', 'No subject')}\n"
                    f"   📤 {email.get('sender', 'Unknown sender')}\n"
                    f"   📅 {date_str}\n"
                    f"   🆔 {email.get('uid', email.get('id', 'Unknown'))}\n"
                    f"   📮 {email.get('account_email', 'Unknown account')}"
                )
            
            return [{
                "type": "text",
                "text": "\n".join(text_parts)
            }]
            
        except Exception as e:
            logger.error(f"Hybrid search emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_mark_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """处理mark_emails - 使用写透式更新"""
        try:
            email_ids = args['email_ids']
            mark_as = args['mark_as']
            account_id = args.get('account_id')
            
            # 使用混合管理器
            hybrid_mgr = HybridEmailToolHandlers.get_hybrid_manager()
            
            result = hybrid_mgr.mark_emails(
                email_ids=email_ids,
                mark_as=mark_as,
                account_id=account_id
            )
            
            if result.get('success'):
                marked_count = result.get('marked_count', len(email_ids))
                return [{
                    "type": "text",
                    "text": f"✅ 成功标记 {marked_count} 封邮件为{mark_as}"
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('operation_failed')}{result.get('error', 'Unknown error')}"
                }]
                
        except Exception as e:
            logger.error(f"Hybrid mark emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_delete_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """处理delete_emails - 使用写透式更新"""
        try:
            email_ids = args['email_ids']
            account_id = args.get('account_id')
            permanent = args.get('permanent', False)
            
            # 使用混合管理器
            hybrid_mgr = HybridEmailToolHandlers.get_hybrid_manager()
            
            result = hybrid_mgr.delete_emails(
                email_ids=email_ids,
                account_id=account_id,
                permanent=permanent
            )
            
            if result.get('success'):
                deleted_count = result.get('deleted_count', len(email_ids))
                action = "永久删除" if permanent else "移到垃圾箱"
                return [{
                    "type": "text",
                    "text": f"✅ 成功{action} {deleted_count} 封邮件"
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"{ctx.get_message('operation_failed')}{result.get('error', 'Unknown error')}"
                }]
                
        except Exception as e:
            logger.error(f"Hybrid delete emails failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def handle_get_freshness_status(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """获取数据新鲜度状态"""
        try:
            hybrid_mgr = HybridEmailToolHandlers.get_hybrid_manager()
            status = hybrid_mgr.get_freshness_status()
            
            text_parts = ["📊 邮件缓存新鲜度状态\n"]
            
            for account_id, account_status in status.items():
                text_parts.append(f"\n📮 账户: {account_status['email']}")
                
                for folder, folder_status in account_status.get('folders', {}).items():
                    freshness = "🟢 新鲜" if folder_status['is_fresh'] else "🔴 需更新"
                    text_parts.append(
                        f"   📁 {folder}: {freshness} "
                        f"(更新于 {folder_status['age_minutes']} 分钟前)"
                    )
            
            return [{
                "type": "text",
                "text": "\n".join(text_parts)
            }]
            
        except Exception as e:
            logger.error(f"Get freshness status failed: {e}")
            return [{
                "type": "text",
                "text": f"{ctx.get_message('operation_failed')}{str(e)}"
            }]
    
    @staticmethod
    def _format_email_list(result: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """格式化邮件列表结果 - 精简格式"""
        emails = result.get('emails', [])
        
        if not emails:
            return [{
                "type": "text",
                "text": ctx.get_message('no_email')
            }]
        
        # Group emails by account
        emails_by_account = {}
        for email in emails:
            # Extract account from email field or use default
            account_email = email.get('account_email', email.get('to_email', 'Unknown'))
            if account_email not in emails_by_account:
                emails_by_account[account_email] = []
            emails_by_account[account_email].append(email)
        
        # Build concise output
        output_lines = []
        
        # Summary line
        total_emails = len(emails)
        total_unread = sum(1 for e in emails if not e.get('is_read', True))
        output_lines.append(f"📧 {total_emails} 封邮件 ({total_unread} 未读)")
        
        # Add cache status if available
        if result.get('from_cache'):
            output_lines.append("📦 来自缓存")
        if result.get('warning'):
            output_lines.append(f"⚠️ {result['warning']}")
        
        output_lines.append("")
        
        # Format each account's emails
        for account, account_emails in emails_by_account.items():
            # Account header with count
            unread_count = sum(1 for e in account_emails if not e.get('is_read', True))
            output_lines.append(f"📮 {account} ({len(account_emails)}封，{unread_count}未读)")
            output_lines.append("")
            
            # Email entries - ultra-concise single line format
            for email in account_emails[:50]:  # Limit per account
                # Use symbols: 🔴 for unread, nothing for read
                mark = "🔴" if not email.get('is_read', True) else "  "
                
                # Get email ID (might be uid or message_id)
                email_id = str(email.get('uid', email.get('message_id', 'no-id')))
                if len(email_id) > 8:
                    email_id = email_id[:8]
                
                # Truncate subject if too long
                subject = email.get('subject', 'No subject')
                if len(subject) > 50:
                    subject = subject[:47] + "..."
                
                # Extract sender name
                sender = email.get('sender', email.get('from', 'Unknown'))
                if '<' in sender:
                    sender = sender.split('<')[0].strip()
                if len(sender) > 15:
                    sender = sender[:12] + "..."
                
                # Format date/time
                date_str = email.get('date_sent', '')
                try:
                    if date_str:
                        from datetime import datetime
                        # Parse ISO format
                        if 'T' in date_str:
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            date_str = dt.strftime('%m-%d %H:%M')
                        else:
                            # Already formatted
                            if len(date_str) > 16:
                                date_str = date_str[:16]
                except:
                    if len(date_str) > 16:
                        date_str = date_str[:16]
                
                # Build compact line with brackets for ID
                line = f"{mark}[{email_id}] {subject} | {sender} | {date_str}"
                output_lines.append(line)
            
            if len(account_emails) > 50:
                output_lines.append(f"  ... 还有 {len(account_emails) - 50} 封")
            
            output_lines.append("")  # Empty line between accounts
        
        return [{
            "type": "text",
            "text": "\n".join(output_lines).strip()
        }]