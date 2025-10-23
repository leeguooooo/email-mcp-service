"""
同步配置管理模块
"""
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class SyncConfigManager:
    """同步配置管理器"""
    
    DEFAULT_CONFIG = {
        "sync": {
            "enabled": True,
            "auto_start": True,  # 服务启动时自动开始同步
            "interval_minutes": 15,  # 增量同步间隔（分钟）
            "full_sync_hours": 24,   # 完全同步间隔（小时）
            "startup_delay_seconds": 30,  # 启动延迟，避免启动时资源冲突
        },
        "quiet_hours": {
            "enabled": False,
            "start": "23:00",  # 静默开始时间
            "end": "06:00",    # 静默结束时间
            "timezone": "local"  # 时区设置
        },
        "performance": {
            "max_concurrent_accounts": 2,  # 最大并发账户数
            "batch_size": 50,              # 邮件批处理大小
            "request_delay_ms": 100,       # 请求间隔（毫秒）
            "timeout_seconds": 30,         # 单个操作超时时间
            "max_memory_mb": 512,          # 最大内存使用（MB）
        },
        "retry": {
            "max_attempts": 3,         # 最大重试次数
            "delay_minutes": 5,        # 重试延迟（分钟）
            "exponential_backoff": True,  # 指数退避
            "max_delay_minutes": 60,   # 最大延迟时间
        },
        "storage": {
            "db_path": "data/email_sync.db",
            "compress_content": True,      # 压缩邮件内容
            "vacuum_interval_days": 7,     # 数据库清理间隔
            "backup_enabled": True,        # 自动备份
            "backup_keep_days": 30,        # 备份保留天数
        },
        "cleanup": {
            "enabled": True,
            "days_to_keep": 90,           # 邮件保留天数
            "cleanup_interval_hours": 24, # 清理间隔
            "soft_delete": True,          # 软删除（标记删除而不是物理删除）
            "compress_old_emails": True,  # 压缩旧邮件
        },
        "folders": {
            "sync_all": True,           # 同步所有文件夹
            "exclude_folders": [        # 排除的文件夹
                "[Gmail]/All Mail",
                "[Gmail]/Important", 
                "[Gmail]/Chats",
                "Junk",
                "Spam"
            ],
            "priority_folders": [       # 优先同步的文件夹
                "INBOX",
                "Sent",
                "Drafts"
            ]
        },
        "notifications": {
            "enabled": False,
            "new_emails": False,        # 新邮件通知
            "sync_completion": False,   # 同步完成通知
            "errors": True,             # 错误通知
            "webhook_url": None,        # Webhook通知URL
        },
        "logging": {
            "level": "INFO",
            "file_enabled": True,
            "file_path": "sync.log",
            "max_file_size_mb": 10,
            "backup_count": 5,
        }
    }
    
    def __init__(self, config_file: str = "data/sync_config.json"):
        """初始化配置管理器"""
        self.config_file = Path(config_file)
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                
                # 深度合并配置
                config = self._deep_merge(self.DEFAULT_CONFIG.copy(), user_config)
                logger.info(f"Loaded config from {self.config_file}")
                return config
                
            except Exception as e:
                logger.error(f"Failed to load config from {self.config_file}: {e}")
                logger.info("Using default configuration")
        
        # 创建默认配置文件
        self.save_config(self.DEFAULT_CONFIG)
        return self.DEFAULT_CONFIG.copy()
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """深度合并字典"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base
    
    def _validate_config(self):
        """验证配置"""
        errors = []
        
        # 验证同步间隔
        sync_interval = self.config.get('sync', {}).get('interval_minutes', 15)
        if not isinstance(sync_interval, int) or sync_interval < 1 or sync_interval > 1440:
            errors.append("sync.interval_minutes must be between 1 and 1440")
        
        # 验证完全同步间隔
        full_sync_hours = self.config.get('sync', {}).get('full_sync_hours', 24)
        if not isinstance(full_sync_hours, int) or full_sync_hours < 1 or full_sync_hours > 168:
            errors.append("sync.full_sync_hours must be between 1 and 168")
        
        # 验证静默时间
        quiet_hours = self.config.get('quiet_hours', {})
        if quiet_hours.get('enabled'):
            for time_key in ['start', 'end']:
                time_str = quiet_hours.get(time_key)
                if time_str:
                    try:
                        datetime.strptime(time_str, '%H:%M')
                    except ValueError:
                        errors.append(f"quiet_hours.{time_key} must be in HH:MM format")
        
        # 验证性能设置
        perf = self.config.get('performance', {})
        max_accounts = perf.get('max_concurrent_accounts', 2)
        if not isinstance(max_accounts, int) or max_accounts < 1 or max_accounts > 10:
            errors.append("performance.max_concurrent_accounts must be between 1 and 10")
        
        batch_size = perf.get('batch_size', 50)
        if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 1000:
            errors.append("performance.batch_size must be between 1 and 1000")
        
        # 验证重试设置
        retry = self.config.get('retry', {})
        max_attempts = retry.get('max_attempts', 3)
        if not isinstance(max_attempts, int) or max_attempts < 1 or max_attempts > 10:
            errors.append("retry.max_attempts must be between 1 and 10")
        
        # 验证清理设置
        cleanup = self.config.get('cleanup', {})
        if cleanup.get('enabled'):
            days_to_keep = cleanup.get('days_to_keep', 90)
            if not isinstance(days_to_keep, int) or days_to_keep < 1 or days_to_keep > 3650:
                errors.append("cleanup.days_to_keep must be between 1 and 3650")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
        
        logger.info("Configuration validation passed")
    
    def save_config(self, config: Dict[str, Any] = None):
        """保存配置到文件"""
        if config is None:
            config = self.config
        
        try:
            # 添加元数据
            config_with_meta = {
                "_metadata": {
                    "version": "1.0",
                    "updated_at": datetime.now().isoformat(),
                    "description": "MCP Email Service Sync Configuration"
                },
                **config
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_with_meta, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            raise
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """更新配置"""
        try:
            # 备份当前配置
            backup_config = self.config.copy()
            
            # 深度合并更新
            self.config = self._deep_merge(self.config, updates)
            
            # 验证新配置
            self._validate_config()
            
            # 保存配置
            self.save_config()
            
            logger.info("Configuration updated successfully")
            return True
            
        except Exception as e:
            # 恢复备份配置
            self.config = backup_config
            logger.error(f"Failed to update config: {e}")
            return False
    
    def get_config(self, path: str = None) -> Any:
        """获取配置值"""
        if path is None:
            return self.config
        
        keys = path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def set_config(self, path: str, value: Any) -> bool:
        """设置配置值"""
        keys = path.split('.')
        config = self.config
        
        # 导航到父级
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 设置值
        config[keys[-1]] = value
        
        try:
            self._validate_config()
            self.save_config()
            return True
        except Exception as e:
            logger.error(f"Failed to set config {path}: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """重置为默认配置"""
        try:
            self.config = self.DEFAULT_CONFIG.copy()
            self.save_config()
            logger.info("Configuration reset to defaults")
            return True
        except Exception as e:
            logger.error(f"Failed to reset config: {e}")
            return False
    
    def export_config(self, file_path: str) -> bool:
        """导出配置到指定文件"""
        try:
            export_path = Path(file_path)
            
            export_data = {
                "exported_at": datetime.now().isoformat(),
                "version": "1.0",
                "config": self.config
            }
            
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration exported to {export_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export config: {e}")
            return False
    
    def import_config(self, file_path: str) -> bool:
        """从文件导入配置"""
        try:
            import_path = Path(file_path)
            if not import_path.exists():
                raise FileNotFoundError(f"Config file not found: {import_path}")
            
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # 提取配置部分
            if 'config' in import_data:
                imported_config = import_data['config']
            else:
                imported_config = import_data
            
            # 更新配置
            return self.update_config(imported_config)
            
        except Exception as e:
            logger.error(f"Failed to import config: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "sync_enabled": self.config.get('sync', {}).get('enabled', False),
            "sync_interval_minutes": self.config.get('sync', {}).get('interval_minutes', 15),
            "full_sync_hours": self.config.get('sync', {}).get('full_sync_hours', 24),
            "quiet_hours_enabled": self.config.get('quiet_hours', {}).get('enabled', False),
            "max_concurrent_accounts": self.config.get('performance', {}).get('max_concurrent_accounts', 2),
            "cleanup_enabled": self.config.get('cleanup', {}).get('enabled', False),
            "days_to_keep": self.config.get('cleanup', {}).get('days_to_keep', 90),
            "db_path": self.config.get('storage', {}).get('db_path', 'data/email_sync.db'),
            "log_level": self.config.get('logging', {}).get('level', 'INFO'),
            "config_file": str(self.config_file)
        }


# 全局配置管理器实例
_config_manager_instance = None

def get_config_manager() -> SyncConfigManager:
    """获取全局配置管理器实例"""
    global _config_manager_instance
    if _config_manager_instance is None:
        _config_manager_instance = SyncConfigManager()
    return _config_manager_instance