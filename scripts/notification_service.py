#!/usr/bin/env python3
"""
通知服务 - 支持多种 webhook 推送方式
支持：钉钉、飞书、企业微信、Slack、自定义 webhook 等
"""
import json
import sys
import os
import time
import hashlib
import sqlite3
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
import requests
from datetime import datetime, timedelta

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NotificationConfig:
    """通知配置"""
    webhook_url: str
    webhook_type: str = "custom"  # dingtalk, feishu, wechat, slack, custom
    secret: Optional[str] = None  # 钉钉、飞书等需要的签名密钥
    retry_times: int = 3
    retry_delay: int = 5  # 秒
    timeout: int = 10
    rate_limit: int = 10  # 每分钟最大发送次数
    template: Optional[str] = None  # 消息模板


@dataclass
class EmailNotification:
    """邮件通知内容"""
    email_id: str
    subject: str
    sender: str
    date: str
    priority_score: float
    reason: str
    category: str
    account_id: Optional[str] = None
    body_preview: Optional[str] = None
    suggested_action: Optional[str] = None


class NotificationService:
    """通知服务"""
    
    def __init__(self, config_path: Optional[str] = None, db_path: Optional[str] = None):
        """
        初始化通知服务
        
        Args:
            config_path: 配置文件路径
            db_path: 去重数据库路径
        """
        self.config_path = config_path or "notification_config.json"
        self.db_path = db_path or "notification_history.db"
        self.config = self._load_config()
        self._init_database()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "webhooks": [
                {
                    "name": "default",
                    "webhook_url": "",
                    "webhook_type": "custom",
                    "secret": None,
                    "retry_times": 3,
                    "retry_delay": 5,
                    "timeout": 10,
                    "rate_limit": 10,
                    "enabled": True,
                    "template": "default"
                }
            ],
            "deduplication": {
                "enabled": True,
                "window_hours": 24,  # 24小时内不重复通知同一封邮件
                "cleanup_days": 7    # 清理7天前的记录
            },
            "templates": {
                "default": {
                    "title": "重要邮件提醒",
                    "content": "收到重要邮件：\\n\\n**主题**: {subject}\\n**发件人**: {sender}\\n**时间**: {date}\\n**重要性**: {priority_score:.1%}\\n**原因**: {reason}\\n\\n{body_preview}"
                },
                "dingtalk": {
                    "msgtype": "markdown",
                    "markdown": {
                        "title": "重要邮件提醒",
                        "text": "## 重要邮件提醒\\n\\n**主题**: {subject}\\n\\n**发件人**: {sender}\\n\\n**时间**: {date}\\n\\n**重要性**: {priority_score:.1%}\\n\\n**分析原因**: {reason}\\n\\n**预览**: {body_preview}\\n\\n---\\n\\n> 邮件ID: {email_id}"
                    }
                },
                "feishu": {
                    "msg_type": "interactive",
                    "card": {
                        "elements": [
                            {
                                "tag": "div",
                                "text": {
                                    "content": "**重要邮件提醒**\\n\\n主题: {subject}\\n发件人: {sender}\\n时间: {date}\\n重要性: {priority_score:.1%}\\n\\n{reason}",
                                    "tag": "lark_md"
                                }
                            }
                        ],
                        "header": {
                            "title": {
                                "content": "📧 重要邮件",
                                "tag": "plain_text"
                            }
                        }
                    }
                },
                "wechat": {
                    "msgtype": "markdown",
                    "markdown": {
                        "content": "## 重要邮件提醒\\n\\n**主题**: {subject}\\n**发件人**: {sender}\\n**时间**: {date}\\n**重要性**: <font color=\"warning\">{priority_score:.1%}</font>\\n**原因**: {reason}\\n\\n{body_preview}"
                    }
                },
                "slack": {
                    "text": "重要邮件提醒",
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": "📧 重要邮件提醒"
                            }
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": "*主题:*\\n{subject}"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": "*发件人:*\\n{sender}"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": "*时间:*\\n{date}"
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": "*重要性:*\\n{priority_score:.1%}"
                                }
                            ]
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "*分析原因:* {reason}\\n\\n*预览:* {body_preview}"
                            }
                        }
                    ]
                }
            }
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    # 深度合并配置
                    self._deep_merge(default_config, user_config)
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
        else:
            # 创建默认配置文件
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"Created default config at {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to create config file: {e}")
        
        return default_config
    
    def _deep_merge(self, base: Dict, update: Dict) -> None:
        """深度合并字典"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _init_database(self):
        """初始化去重数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建通知历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS notification_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email_id TEXT NOT NULL,
                    email_hash TEXT NOT NULL,
                    webhook_name TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    UNIQUE(email_hash, webhook_name)
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_email_hash_webhook 
                ON notification_history(email_hash, webhook_name)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sent_at 
                ON notification_history(sent_at)
            ''')
            
            conn.commit()
            conn.close()
            
            # 清理旧记录
            self._cleanup_old_records()
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    def _cleanup_old_records(self):
        """清理旧的通知记录"""
        try:
            cleanup_days = self.config.get("deduplication", {}).get("cleanup_days", 7)
            cutoff_date = datetime.now() - timedelta(days=cleanup_days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM notification_history WHERE sent_at < ?",
                (cutoff_date.isoformat(),)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old notification records")
                
        except Exception as e:
            logger.error(f"Failed to cleanup old records: {e}")
    
    def _generate_email_hash(self, notification: EmailNotification) -> str:
        """生成邮件的唯一哈希值用于去重"""
        # 使用邮件ID、主题、发件人生成哈希
        content = f"{notification.email_id}:{notification.subject}:{notification.sender}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _is_duplicate(self, notification: EmailNotification, webhook_name: str) -> bool:
        """检查是否为重复通知"""
        if not self.config.get("deduplication", {}).get("enabled", True):
            return False
        
        try:
            email_hash = self._generate_email_hash(notification)
            window_hours = self.config.get("deduplication", {}).get("window_hours", 24)
            cutoff_time = datetime.now() - timedelta(hours=window_hours)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM notification_history 
                WHERE email_hash = ? AND webhook_name = ? AND sent_at > ? AND success = TRUE
            ''', (email_hash, webhook_name, cutoff_time.isoformat()))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count > 0
            
        except Exception as e:
            logger.error(f"Failed to check duplicate: {e}")
            return False
    
    def _record_notification(self, notification: EmailNotification, webhook_name: str, 
                           success: bool, error_message: Optional[str] = None):
        """记录通知发送结果"""
        try:
            email_hash = self._generate_email_hash(notification)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO notification_history 
                (email_id, email_hash, webhook_name, success, error_message)
                VALUES (?, ?, ?, ?, ?)
            ''', (notification.email_id, email_hash, webhook_name, success, error_message))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to record notification: {e}")
    
    def _format_message(self, notification: EmailNotification, template_name: str) -> Dict[str, Any]:
        """格式化消息内容"""
        templates = self.config.get("templates", {})
        template = templates.get(template_name, templates.get("default", {}))
        
        # 准备模板变量
        template_vars = {
            "email_id": notification.email_id,
            "subject": notification.subject,
            "sender": notification.sender,
            "date": notification.date,
            "priority_score": notification.priority_score,
            "reason": notification.reason,
            "category": notification.category,
            "body_preview": notification.body_preview or "无预览",
            "suggested_action": notification.suggested_action or "无建议",
            "account_id": notification.account_id or "默认账户"
        }
        
        # 递归格式化模板
        def format_recursive(obj):
            if isinstance(obj, str):
                try:
                    return obj.format(**template_vars)
                except KeyError as e:
                    logger.warning(f"Template variable not found: {e}")
                    return obj
            elif isinstance(obj, dict):
                return {k: format_recursive(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [format_recursive(item) for item in obj]
            else:
                return obj
        
        return format_recursive(template)
    
    def _generate_dingtalk_signature(self, secret: str, timestamp: int) -> str:
        """生成钉钉签名"""
        import hmac
        import base64
        
        string_to_sign = f"{timestamp}\\n{secret}"
        hmac_code = hmac.new(
            secret.encode('utf-8'),
            string_to_sign.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode('utf-8')
        return sign
    
    def _send_webhook(self, webhook_config: Dict[str, Any], message: Dict[str, Any]) -> bool:
        """发送 webhook 请求"""
        webhook_type = webhook_config.get("webhook_type", "custom")
        webhook_url = webhook_config["webhook_url"]
        secret = webhook_config.get("secret")
        timeout = webhook_config.get("timeout", 10)
        
        # 处理钉钉签名
        if webhook_type == "dingtalk" and secret:
            timestamp = int(time.time() * 1000)
            sign = self._generate_dingtalk_signature(secret, timestamp)
            webhook_url += f"&timestamp={timestamp}&sign={sign}"
        
        # 处理飞书签名
        elif webhook_type == "feishu" and secret:
            timestamp = str(int(time.time()))
            string_to_sign = f"{timestamp}\\n{secret}"
            sign = hashlib.sha256(string_to_sign.encode('utf-8')).hexdigest()
            message["timestamp"] = timestamp
            message["sign"] = sign
        
        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "MCP-Email-Notification-Service/1.0"
            }
            
            response = requests.post(
                webhook_url,
                json=message,
                headers=headers,
                timeout=timeout
            )
            
            response.raise_for_status()
            
            # 检查响应内容
            if response.text:
                try:
                    result = response.json()
                    # 钉钉返回格式检查
                    if webhook_type == "dingtalk" and result.get("errcode") != 0:
                        logger.error(f"DingTalk error: {result}")
                        return False
                    # 飞书返回格式检查
                    elif webhook_type == "feishu" and result.get("code") != 0:
                        logger.error(f"Feishu error: {result}")
                        return False
                except json.JSONDecodeError:
                    pass  # 有些 webhook 不返回 JSON
            
            logger.info(f"Webhook sent successfully to {webhook_config['name']}")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook request failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending webhook: {e}")
            return False
    
    def send_notification(self, notification: EmailNotification, 
                         webhook_names: Optional[List[str]] = None) -> Dict[str, bool]:
        """
        发送通知
        
        Args:
            notification: 邮件通知内容
            webhook_names: 指定的 webhook 名称列表，None 表示发送到所有启用的 webhook
            
        Returns:
            字典，键为 webhook 名称，值为发送是否成功
        """
        results = {}
        webhooks = self.config.get("webhooks", [])
        
        for webhook_config in webhooks:
            webhook_name = webhook_config.get("name", "unknown")
            
            # 检查是否在指定列表中
            if webhook_names and webhook_name not in webhook_names:
                continue
            
            # 检查是否启用
            if not webhook_config.get("enabled", True):
                logger.info(f"Webhook {webhook_name} is disabled, skipping")
                continue
            
            # 检查是否重复
            if self._is_duplicate(notification, webhook_name):
                logger.info(f"Duplicate notification for {webhook_name}, skipping")
                results[webhook_name] = True  # 认为成功（因为已经发送过了）
                continue
            
            # 格式化消息
            template_name = webhook_config.get("template", webhook_config.get("webhook_type", "default"))
            message = self._format_message(notification, template_name)
            
            # 发送通知（带重试）
            retry_times = webhook_config.get("retry_times", 3)
            retry_delay = webhook_config.get("retry_delay", 5)
            success = False
            last_error = None
            
            for attempt in range(retry_times):
                try:
                    success = self._send_webhook(webhook_config, message)
                    if success:
                        break
                    else:
                        last_error = "Webhook request failed"
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Attempt {attempt + 1} failed for {webhook_name}: {e}")
                
                if attempt < retry_times - 1:
                    time.sleep(retry_delay)
            
            # 记录结果
            self._record_notification(notification, webhook_name, success, last_error)
            results[webhook_name] = success
            
            if success:
                logger.info(f"Notification sent successfully to {webhook_name}")
            else:
                logger.error(f"Failed to send notification to {webhook_name}: {last_error}")
        
        return results
    
    def send_batch_notifications(self, notifications: List[EmailNotification],
                               webhook_names: Optional[List[str]] = None) -> Dict[str, Dict[str, bool]]:
        """
        批量发送通知
        
        Args:
            notifications: 邮件通知列表
            webhook_names: 指定的 webhook 名称列表
            
        Returns:
            嵌套字典，第一层键为邮件ID，第二层键为 webhook 名称，值为发送是否成功
        """
        results = {}
        
        for notification in notifications:
            results[notification.email_id] = self.send_notification(notification, webhook_names)
        
        return results
    
    def get_notification_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取通知统计信息"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 总体统计
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                    COUNT(DISTINCT email_hash) as unique_emails
                FROM notification_history 
                WHERE sent_at > ?
            ''', (cutoff_date.isoformat(),))
            
            total, success_count, unique_emails = cursor.fetchone()
            
            # 按 webhook 统计
            cursor.execute('''
                SELECT 
                    webhook_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
                FROM notification_history 
                WHERE sent_at > ?
                GROUP BY webhook_name
            ''', (cutoff_date.isoformat(),))
            
            webhook_stats = {}
            for row in cursor.fetchall():
                webhook_name, total_count, success_count_webhook = row
                webhook_stats[webhook_name] = {
                    "total": total_count,
                    "success": success_count_webhook,
                    "success_rate": success_count_webhook / total_count if total_count > 0 else 0
                }
            
            conn.close()
            
            return {
                "period_days": days,
                "total_notifications": total or 0,
                "successful_notifications": success_count or 0,
                "unique_emails": unique_emails or 0,
                "success_rate": (success_count / total) if total > 0 else 0,
                "webhook_stats": webhook_stats
            }
            
        except Exception as e:
            logger.error(f"Failed to get notification stats: {e}")
            return {"error": str(e)}


def main():
    """主函数 - 命令行接口"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python notification_service.py <command> [args...]",
            "commands": {
                "send": "Send notification from JSON data",
                "batch": "Send batch notifications from JSON array",
                "stats": "Get notification statistics",
                "test": "Test webhook configuration"
            },
            "examples": {
                "send": "python notification_service.py send '{\"email_id\":\"123\",\"subject\":\"Test\",\"sender\":\"test@example.com\",\"date\":\"2024-01-15\",\"priority_score\":0.8,\"reason\":\"Test notification\",\"category\":\"test\"}'",
                "stats": "python notification_service.py stats 7"
            }
        }))
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        service = NotificationService()
        
        if command == "send":
            if len(sys.argv) < 3:
                print(json.dumps({"error": "Missing notification data"}))
                sys.exit(1)
            
            notification_data = json.loads(sys.argv[2])
            notification = EmailNotification(**notification_data)
            
            webhook_names = None
            if len(sys.argv) > 3:
                webhook_names = sys.argv[3].split(',')
            
            results = service.send_notification(notification, webhook_names)
            print(json.dumps({
                "success": True,
                "results": results,
                "total_webhooks": len(results),
                "successful_webhooks": sum(1 for success in results.values() if success)
            }))
        
        elif command == "batch":
            if len(sys.argv) < 3:
                print(json.dumps({"error": "Missing notifications data"}))
                sys.exit(1)
            
            notifications_data = json.loads(sys.argv[2])
            notifications = [EmailNotification(**data) for data in notifications_data]
            
            webhook_names = None
            if len(sys.argv) > 3:
                webhook_names = sys.argv[3].split(',')
            
            results = service.send_batch_notifications(notifications, webhook_names)
            print(json.dumps({
                "success": True,
                "results": results,
                "total_emails": len(notifications)
            }))
        
        elif command == "stats":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            stats = service.get_notification_stats(days)
            print(json.dumps(stats, indent=2))
        
        elif command == "test":
            # 发送测试通知
            test_notification = EmailNotification(
                email_id="test_" + str(int(time.time())),
                subject="测试通知",
                sender="test@example.com",
                date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                priority_score=0.8,
                reason="这是一个测试通知",
                category="test",
                body_preview="这是测试邮件的预览内容..."
            )
            
            results = service.send_notification(test_notification)
            print(json.dumps({
                "success": True,
                "test_results": results
            }))
        
        else:
            print(json.dumps({"error": f"Unknown command: {command}"}))
            sys.exit(1)
    
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
