"""
同步相关的MCP工具处理器
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.tool_handlers import ToolContext
from background.sync_scheduler import get_scheduler
from background.sync_config import get_config_manager
from operations.email_sync import EmailSyncManager

logger = logging.getLogger(__name__)

class SyncHandlers:
    """同步工具处理器"""
    
    @staticmethod
    def handle_sync_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """统一的邮件同步工具处理器"""
        action = args.get('action', 'status')
        
        if action == 'start':
            return SyncHandlers._handle_start_sync(args, ctx)
        elif action == 'stop':
            return SyncHandlers._handle_stop_sync(args, ctx)
        elif action == 'force':
            return SyncHandlers._handle_force_sync(args, ctx)
        elif action == 'status':
            return SyncHandlers._handle_sync_status(args, ctx)
        elif action == 'search':
            return SyncHandlers._handle_search_cached_emails(args, ctx)
        elif action == 'recent':
            return SyncHandlers._handle_get_recent_cached_emails(args, ctx)
        elif action == 'config':
            return SyncHandlers._handle_config_management(args, ctx)
        else:
            return [{
                "type": "text",
                "text": f"❌ 未知操作: {action}。支持的操作: start, stop, force, status, search, recent, config"
            }]
    
    @staticmethod
    def _handle_start_sync(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """启动邮件同步"""
        try:
            scheduler = get_scheduler()
            
            if scheduler.running:
                return [{
                    "type": "text",
                    "text": "📧 同步调度器已在运行中"
                }]
            
            scheduler.start_scheduler()
            
            # 获取状态信息
            status = scheduler.get_sync_status()
            
            return [{
                "type": "text", 
                "text": (
                    "🚀 邮件同步调度器已启动\n"
                    f"• 增量同步间隔: {status['config'].get('sync_interval_minutes', 15)}分钟\n"
                    f"• 配置账户数: {status.get('accounts_searched', 0)}\n"
                    f"• 下次同步: {status['next_jobs'][0]['next_run'] if status['next_jobs'] else '待定'}"
                )
            }]
            
        except Exception as e:
            logger.error(f"Start sync failed: {e}")
            return [{
                "type": "text",
                "text": f"❌ 启动同步失败: {str(e)}"
            }]
    
    @staticmethod
    def _handle_stop_sync(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """停止邮件同步"""
        try:
            scheduler = get_scheduler()
            
            if not scheduler.running:
                return [{
                    "type": "text",
                    "text": "⏹️ 同步调度器已经停止"
                }]
            
            scheduler.stop_scheduler()
            
            return [{
                "type": "text",
                "text": "⏹️ 邮件同步调度器已停止"
            }]
            
        except Exception as e:
            logger.error(f"Stop sync failed: {e}")
            return [{
                "type": "text", 
                "text": f"❌ 停止同步失败: {str(e)}"
            }]
    
    @staticmethod
    def _handle_force_sync(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """强制立即同步"""
        try:
            full_sync = args.get('full_sync', False)
            account_id = args.get('account_id')
            
            scheduler = get_scheduler()
            
            if account_id:
                # 单账户同步
                sync_manager = EmailSyncManager()
                result = sync_manager.sync_single_account(account_id, full_sync)
                sync_manager.close()
            else:
                # 全部账户同步
                result = scheduler.force_sync(full_sync)
            
            if result.get('success'):
                sync_type = "完全同步" if full_sync else "增量同步"
                account_info = f"账户 {account_id}" if account_id else "所有账户"
                
                return [{
                    "type": "text",
                    "text": (
                        f"✅ {sync_type}完成 ({account_info})\n"
                        f"• 新增邮件: {result.get('emails_added', 0)}\n"
                        f"• 更新邮件: {result.get('emails_updated', 0)}\n" 
                        f"• 同步时间: {result.get('sync_time', 0):.1f}秒"
                    )
                }]
            else:
                return [{
                    "type": "text",
                    "text": f"❌ 同步失败: {result.get('error', '未知错误')}"
                }]
                
        except Exception as e:
            logger.error(f"Force sync failed: {e}")
            return [{
                "type": "text",
                "text": f"❌ 强制同步失败: {str(e)}"
            }]
    
    @staticmethod
    def _handle_sync_status(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """获取同步状态"""
        try:
            scheduler = get_scheduler()
            status = scheduler.get_sync_status()
            
            # 格式化状态信息
            scheduler_status = "🟢 运行中" if status['scheduler_running'] else "🔴 已停止"
            
            response_text = f"📊 邮件同步状态\n\n"
            response_text += f"调度器状态: {scheduler_status}\n"
            
            # 账户信息
            accounts = status.get('accounts', [])
            if accounts:
                response_text += f"\n📧 账户信息 ({len(accounts)}个):\n"
                for account in accounts[:5]:  # 最多显示5个账户
                    last_sync = account.get('last_sync')
                    if last_sync:
                        last_sync_str = datetime.fromisoformat(last_sync).strftime('%m-%d %H:%M')
                    else:
                        last_sync_str = "从未同步"
                    
                    response_text += f"• {account['email']}: {account.get('total_emails', 0)}封邮件, 最后同步: {last_sync_str}\n"
                
                if len(accounts) > 5:
                    response_text += f"... 还有 {len(accounts) - 5} 个账户\n"
            
            # 同步统计
            total_emails = status.get('total_emails', 0)
            if total_emails > 0:
                response_text += f"\n📈 统计信息:\n"
                response_text += f"• 总邮件数: {total_emails:,}\n"
                
                db_size = status.get('database_size', 0)
                if db_size > 0:
                    db_size_mb = db_size / (1024 * 1024)
                    response_text += f"• 数据库大小: {db_size_mb:.1f} MB\n"
            
            # 下次同步时间
            next_jobs = status.get('next_jobs', [])
            if next_jobs:
                response_text += f"\n⏰ 计划任务:\n"
                for job in next_jobs[:3]:  # 最多显示3个任务
                    if job.get('next_run'):
                        next_run = datetime.fromisoformat(job['next_run']).strftime('%m-%d %H:%M')
                        response_text += f"• 下次同步: {next_run}\n"
                        break
            
            # 最后同步时间
            last_sync_times = status.get('last_sync_times', {})
            if last_sync_times:
                response_text += f"\n🕐 最后同步:\n"
                for sync_type, time_str in last_sync_times.items():
                    if time_str:
                        time_formatted = datetime.fromisoformat(time_str).strftime('%m-%d %H:%M')
                        response_text += f"• {sync_type}: {time_formatted}\n"
            
            return [{"type": "text", "text": response_text}]
            
        except Exception as e:
            logger.error(f"Get sync status failed: {e}")
            return [{
                "type": "text",
                "text": f"❌ 获取同步状态失败: {str(e)}"
            }]
    
    @staticmethod
    def _handle_search_cached_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """搜索缓存的邮件"""
        try:
            query = args.get('query', '')
            account_id = args.get('account_id')
            limit = args.get('limit', 20)
            
            if not query:
                return [{
                    "type": "text",
                    "text": "❌ 请提供搜索关键词"
                }]
            
            sync_manager = EmailSyncManager()
            emails = sync_manager.search_cached_emails(query, account_id, limit)
            sync_manager.close()
            
            if not emails:
                return [{
                    "type": "text", 
                    "text": f"🔍 未找到包含 '{query}' 的缓存邮件"
                }]
            
            # 格式化邮件列表
            response_text = f"🔍 找到 {len(emails)} 封缓存邮件 (关键词: '{query}')\n\n"
            
            for i, email in enumerate(emails, 1):
                date_sent = email.get('date_sent')
                if date_sent:
                    date_str = datetime.fromisoformat(date_sent).strftime('%m-%d %H:%M')
                else:
                    date_str = "未知时间"
                
                read_mark = "✅" if email.get('is_read') else "📧"
                flag_mark = " ⭐" if email.get('is_flagged') else ""
                
                response_text += f"{read_mark} {email.get('subject', '无主题')}{flag_mark}\n"
                response_text += f"   发件人: {email.get('sender', '未知')}\n"
                response_text += f"   时间: {date_str} | 账户: {email.get('account_email', '未知')}\n"
                response_text += f"   文件夹: {email.get('folder_name', '未知')}\n\n"
            
            return [{"type": "text", "text": response_text}]
            
        except Exception as e:
            logger.error(f"Search cached emails failed: {e}")
            return [{
                "type": "text",
                "text": f"❌ 搜索缓存邮件失败: {str(e)}"
            }]
    
    @staticmethod
    def _handle_get_recent_cached_emails(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """获取最近的缓存邮件"""
        try:
            account_id = args.get('account_id')
            limit = args.get('limit', 20)
            
            sync_manager = EmailSyncManager()
            emails = sync_manager.get_recent_emails(account_id, limit)
            sync_manager.close()
            
            if not emails:
                return [{
                    "type": "text",
                    "text": "📭 暂无缓存邮件"
                }]
            
            # 格式化邮件列表
            account_info = f"账户 {account_id}" if account_id else "所有账户"
            response_text = f"📬 最近 {len(emails)} 封邮件 ({account_info})\n\n"
            
            for email in emails:
                date_sent = email.get('date_sent')
                if date_sent:
                    date_str = datetime.fromisoformat(date_sent).strftime('%m-%d %H:%M')
                else:
                    date_str = "未知时间"
                
                read_mark = "✅" if email.get('is_read') else "📧"
                flag_mark = " ⭐" if email.get('is_flagged') else ""
                
                response_text += f"{read_mark} {email.get('subject', '无主题')}{flag_mark}\n"
                response_text += f"   发件人: {email.get('sender', '未知')}\n"
                response_text += f"   时间: {date_str} | 账户: {email.get('account_email', '未知')}\n\n"
            
            return [{"type": "text", "text": response_text}]
            
        except Exception as e:
            logger.error(f"Get recent cached emails failed: {e}")
            return [{
                "type": "text",
                "text": f"❌ 获取最近邮件失败: {str(e)}"
            }]
    
    @staticmethod
    def _handle_config_management(args: Dict[str, Any], ctx: ToolContext) -> List[Dict[str, Any]]:
        """统一的配置管理"""
        try:
            config_manager = get_config_manager()
            config_updates = args.get('config_updates')
            
            if config_updates:
                # 更新配置
                updates = {}
                
                # 转换配置结构
                if 'interval_minutes' in config_updates:
                    updates['sync'] = {'interval_minutes': config_updates['interval_minutes']}
                
                if 'full_sync_hours' in config_updates:
                    if 'sync' not in updates:
                        updates['sync'] = {}
                    updates['sync']['full_sync_hours'] = config_updates['full_sync_hours']
                
                if 'enabled' in config_updates:
                    if 'sync' not in updates:
                        updates['sync'] = {}
                    updates['sync']['enabled'] = config_updates['enabled']
                
                if 'max_concurrent_accounts' in config_updates:
                    updates['performance'] = {'max_concurrent_accounts': config_updates['max_concurrent_accounts']}
                
                if 'cleanup_days' in config_updates:
                    updates['cleanup'] = {'days_to_keep': config_updates['cleanup_days']}
                
                if not updates:
                    return [{
                        "type": "text",
                        "text": "❌ 未提供有效的配置更新参数"
                    }]
                
                # 更新配置
                success = config_manager.update_config(updates)
                
                if success:
                    # 如果调度器正在运行，重新启动以应用新配置
                    scheduler = get_scheduler()
                    if scheduler.running:
                        scheduler.stop_scheduler()
                        scheduler.start_scheduler()
                    
                    return [{
                        "type": "text",
                        "text": "✅ 同步配置已更新并应用"
                    }]
                else:
                    return [{
                        "type": "text",
                        "text": "❌ 配置更新失败，请检查参数"
                    }]
            else:
                # 获取配置
                summary = config_manager.get_config_summary()
                
                response_text = "⚙️ 邮件同步配置\n\n"
                response_text += f"• 同步启用: {'是' if summary['sync_enabled'] else '否'}\n"
                response_text += f"• 增量同步间隔: {summary['sync_interval_minutes']} 分钟\n"
                response_text += f"• 完全同步间隔: {summary['full_sync_hours']} 小时\n"
                response_text += f"• 静默时间: {'启用' if summary['quiet_hours_enabled'] else '禁用'}\n"
                response_text += f"• 最大并发账户: {summary['max_concurrent_accounts']}\n"
                response_text += f"• 自动清理: {'启用' if summary['cleanup_enabled'] else '禁用'}\n"
                
                if summary['cleanup_enabled']:
                    response_text += f"• 邮件保留天数: {summary['days_to_keep']} 天\n"
                
                response_text += f"• 数据库路径: {summary['db_path']}\n"
                response_text += f"• 日志级别: {summary['log_level']}\n"
                
                return [{"type": "text", "text": response_text}]
                
        except Exception as e:
            logger.error(f"Config management failed: {e}")
            return [{
                "type": "text",
                "text": f"❌ 配置管理失败: {str(e)}"
            }]