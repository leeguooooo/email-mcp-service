#!/usr/bin/env python3
"""
邮件监控主控制脚本 - 整合邮件获取与通知发送
这是一个完整的流程脚本，可以被本地定时任务或其他自动化工具调用
"""
import json
import sys
import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import subprocess

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.config.paths import EMAIL_MONITOR_CONFIG_JSON, NOTIFICATION_CONFIG_JSON

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EmailMonitor:
    """邮件监控器 - 整合所有组件"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化邮件监控器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path or EMAIL_MONITOR_CONFIG_JSON
        self.config = self._load_config()
        self.scripts_dir = Path(__file__).parent
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        def _relative_config_path(path_value: str) -> str:
            try:
                return str(Path(path_value).relative_to(repo_root))
            except ValueError:
                return path_value

        default_config = {
            "email": {
                "fetch_limit": 20,
                "unread_only": True,
                "account_id": None,
                "folder": "INBOX"
            },
            "notification": {
                "enabled": True,
                "config_path": _relative_config_path(NOTIFICATION_CONFIG_JSON),
                "webhook_names": None  # None 表示发送到所有启用的 webhook
            },
            "deduplication": {
                "enabled": True,
                "method": "content_hash",  # content_hash, email_id, subject_sender
                "window_hours": 24
            },
            "logging": {
                "level": "INFO",
                "file": "email_monitor.log"
            }
        }
        
        if not os.path.exists(self.config_path):
            legacy_path = repo_root / "email_monitor_config.json"
            if legacy_path.exists():
                try:
                    Path(self.config_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(self.config_path).write_text(
                        legacy_path.read_text(encoding="utf-8"),
                        encoding="utf-8"
                    )
                    logger.info("Migrated legacy email_monitor_config.json to %s", self.config_path)
                except Exception as e:
                    logger.warning(f"Failed to migrate legacy config: {e}")

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
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
    
    def _run_script(self, script_name: str, args: List[str]) -> Dict[str, Any]:
        """运行脚本并返回结果"""
        script_path = self.scripts_dir / script_name
        
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")
        
        try:
            # 构建命令
            cmd = [sys.executable, str(script_path)] + args
            
            # 运行脚本
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
                cwd=repo_root
            )
            
            if result.returncode != 0:
                logger.error(f"Script {script_name} failed with code {result.returncode}")
                logger.error(f"stderr: {result.stderr}")
                return {
                    "success": False,
                    "error": f"Script failed: {result.stderr}",
                    "returncode": result.returncode
                }
            
            # 解析输出
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.warning(f"Script {script_name} output is not valid JSON: {result.stdout}")
                return {
                    "success": True,
                    "output": result.stdout,
                    "raw": True
                }
        
        except subprocess.TimeoutExpired:
            logger.error(f"Script {script_name} timed out")
            return {"success": False, "error": "Script timed out"}
        except Exception as e:
            logger.error(f"Failed to run script {script_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def fetch_emails(self) -> Dict[str, Any]:
        """获取邮件列表"""
        email_config = self.config.get("email", {})
        
        # 构建参数
        args = {
            "limit": email_config.get("fetch_limit", 20),
            "unread_only": email_config.get("unread_only", True),
            "folder": email_config.get("folder", "INBOX")
        }
        
        if email_config.get("account_id"):
            args["account_id"] = email_config["account_id"]
        
        from src.account_manager import AccountManager
        from src.services.email_service import EmailService

        svc = EmailService(AccountManager())
        result = svc.list_emails(
            limit=args["limit"],
            unread_only=args["unread_only"],
            folder=args["folder"],
            account_id=args.get("account_id"),
            use_cache=False
        )
        
        if not result.get("success", False):
            logger.error(f"Failed to fetch emails: {result.get('error')}")
            return result
        
        emails = result.get("emails", [])
        logger.info(f"Fetched {len(emails)} emails")
        
        return {
            "success": True,
            "emails": emails,
            "count": len(emails)
        }
    
    def build_notification_results(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建默认通知结果（不过滤）"""
        return {
            "success": True,
            "total_emails": len(emails),
            "important_emails": len(emails),
            "results": [
                {
                    "email_id": email.get("id", ""),
                    "is_important": True,
                    "priority_score": 0.8,
                    "reason": "未启用过滤，全部通知",
                    "category": "general",
                    "suggested_action": "none"
                }
                for email in emails
            ]
        }
    
    def send_notifications(self, emails: List[Dict[str, Any]], 
                          filter_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """发送通知"""
        if not self.config.get("notification", {}).get("enabled", True):
            logger.info("Notifications are disabled")
            return {"success": True, "message": "Notifications disabled"}
        
        # 筛选出重要邮件
        important_emails = []
        email_dict = {email.get("id", ""): email for email in emails}
        
        for filter_result in filter_results:
            if filter_result.get("is_important", False):
                email_id = filter_result["email_id"]
                email = email_dict.get(email_id)
                if email:
                    # 合并邮件数据和过滤结果
                    notification_data = {
                        "email_id": email_id,
                        "subject": email.get("subject", ""),
                        "sender": email.get("from", ""),
                        "date": email.get("date", ""),
                        "priority_score": filter_result.get("priority_score", 0.8),
                        "reason": filter_result.get("reason", ""),
                        "category": filter_result.get("category", "general"),
                        "account_id": email.get("account_id"),
                        "body_preview": email.get("body_preview", email.get("body", ""))[:200],
                        "suggested_action": filter_result.get("suggested_action", "none")
                    }
                    important_emails.append(notification_data)
        
        if not important_emails:
            logger.info("No important emails to notify")
            return {"success": True, "message": "No important emails"}
        
        # 准备通知参数
        notification_config = self.config.get("notification", {})
        args = [json.dumps(important_emails)]
        
        webhook_names = notification_config.get("webhook_names")
        if webhook_names:
            args.append(",".join(webhook_names))
        
        # 发送批量通知
        result = self._run_script("notification_service.py", ["batch"] + args)
        
        if result.get("success", False):
            logger.info(f"Sent notifications for {len(important_emails)} important emails")
        else:
            logger.error(f"Failed to send notifications: {result.get('error')}")
        
        return result
    
    def run_monitoring_cycle(self) -> Dict[str, Any]:
        """运行一次完整的监控周期"""
        logger.info("Starting email monitoring cycle")
        
        try:
            # 1. 获取邮件
            fetch_result = self.fetch_emails()
            if not fetch_result.get("success", False):
                return {
                    "success": False,
                    "error": "Failed to fetch emails",
                    "important_emails": [],
                    "details": {
                        "emails": fetch_result.get("emails", []),
                        "fetch_result": fetch_result,
                    },
                }
            
            emails = fetch_result.get("emails", [])
            if not emails:
                logger.info("No emails to process")
                return {
                    "success": True,
                    "message": "No emails to process",
                    "stats": {
                        "fetched_emails": 0,
                        "important_emails": 0,
                        "notifications_sent": 0
                    },
                    "important_emails": [],
                    "details": {
                        "emails": [],
                        "fetch_result": fetch_result,
                    },
                }
            
            # 2. 生成通知结果（不过滤）
            filter_result = self.build_notification_results(emails)
            
            filter_results = filter_result.get("results", [])
            important_count = sum(1 for r in filter_results if r.get("is_important", False))
            important_ids = {
                r.get("email_id")
                for r in filter_results
                if r.get("is_important", False) and r.get("email_id")
            }
            important_emails = [e for e in emails if e.get("id") in important_ids]
            
            # 3. 发送通知
            notification_result = self.send_notifications(emails, filter_results)
            
            # 4. 统计结果
            stats = {
                "fetched_emails": len(emails),
                "important_emails": important_count,
                "notifications_sent": len([r for r in filter_results if r.get("is_important", False)]),
                "filter_success": filter_result.get("success", False),
                "notification_success": notification_result.get("success", False)
            }
            
            logger.info(f"Monitoring cycle completed: {stats}")
            
            return {
                "success": True,
                "message": "Monitoring cycle completed successfully",
                "stats": stats,
                "important_emails": important_emails,
                "details": {
                    "emails": emails,
                    "fetch_result": fetch_result,
                    "filter_result": filter_result,
                    "notification_result": notification_result
                }
            }
        
        except Exception as e:
            logger.error(f"Monitoring cycle failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """获取监控状态"""
        try:
            # 检查各个组件的状态
            status = {
                "config_loaded": bool(self.config),
                "scripts_available": {},
                "last_run": None,
                "configuration": {
                    "email_config": self.config.get("email", {}),
                    "notification_enabled": self.config.get("notification", {}).get("enabled", False)
                }
            }
            
            # 检查脚本文件
            required_scripts = [
                "notification_service.py"
            ]
            
            for script in required_scripts:
                script_path = self.scripts_dir / script
                status["scripts_available"][script] = script_path.exists()
            
            return {
                "success": True,
                "status": status
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


def main():
    """主函数 - 命令行接口"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python email_monitor.py <command> [args...]",
            "commands": {
                "run": "Run one monitoring cycle",
                "status": "Get monitoring status",
                "test": "Test individual components",
                "config": "Show current configuration"
            },
            "examples": {
                "run": "python email_monitor.py run",
                "status": "python email_monitor.py status",
                "test": "python email_monitor.py test fetch|notify"
            }
        }))
        sys.exit(1)
    
    command = sys.argv[1]
    config_path = None
    
    # 检查是否指定了配置文件
    if "--config" in sys.argv:
        config_index = sys.argv.index("--config")
        if config_index + 1 < len(sys.argv):
            config_path = sys.argv[config_index + 1]
    
    try:
        monitor = EmailMonitor(config_path)
        
        if command == "run":
            result = monitor.run_monitoring_cycle()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif command == "status":
            result = monitor.get_status()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif command == "config":
            print(json.dumps(monitor.config, indent=2, ensure_ascii=False))
        
        elif command == "test":
            component = sys.argv[2] if len(sys.argv) > 2 else "all"
            
            if component in ["fetch", "all"]:
                print("Testing email fetch...")
                result = monitor.fetch_emails()
                print(json.dumps(result, indent=2, ensure_ascii=False))
            
            if component in ["filter", "all"] and len(sys.argv) > 2:
                print("Filtering is no longer available; skipping.")

            if component in ["notify", "all"]:
                print("Testing notification...")
                # 发送测试通知
                test_result = monitor._run_script("notification_service.py", ["test"])
                print(json.dumps(test_result, indent=2, ensure_ascii=False))
        
        else:
            print(json.dumps({"error": f"Unknown command: {command}"}))
            sys.exit(1)
    
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
