"""
混合模式配置管理
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class HybridConfig:
    """混合模式配置管理器"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.config_file = Path("hybrid_config.json")
        self._config = self._load_config()
        self._initialized = True
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "hybrid_mode": {
                "enabled": True,
                "cache_settings": {
                    "freshness_threshold_minutes": 5,
                    "auto_sync_on_search": True,
                    "priority_folders": ["INBOX", "Sent", "Drafts"]
                },
                "query_strategy": {
                    "unread_always_fresh": True,
                    "search_recent_days": 7,
                    "min_search_results": 5
                },
                "performance": {
                    "quick_sync_timeout_seconds": 10,
                    "max_quick_sync_emails": 20,
                    "parallel_account_sync": True
                },
                "fallback": {
                    "use_cache_on_error": True,
                    "add_warning_on_stale": True
                }
            },
            "tool_settings": {
                "default_use_cache": None,
                "tool_overrides": {}
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 深度合并配置
                    return self._deep_merge(default_config, loaded_config)
            except Exception as e:
                logger.warning(f"Failed to load hybrid config: {e}, using defaults")
        else:
            # 如果示例文件存在，复制它
            example_file = Path("hybrid_config.json.example")
            if example_file.exists():
                try:
                    import shutil
                    shutil.copy(example_file, self.config_file)
                    logger.info("Created hybrid_config.json from example")
                except:
                    pass
        
        return default_config
    
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """深度合并两个字典"""
        result = base.copy()
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    @property
    def is_enabled(self) -> bool:
        """检查混合模式是否启用"""
        return self._config.get("hybrid_mode", {}).get("enabled", True)
    
    def get_freshness_threshold(self, tool_name: str = None) -> int:
        """获取新鲜度阈值（分钟）"""
        # 先检查工具特定配置
        if tool_name:
            tool_config = self._config.get("tool_settings", {}).get("tool_overrides", {}).get(tool_name, {})
            if "freshness_threshold_minutes" in tool_config:
                return tool_config["freshness_threshold_minutes"]
        
        # 返回默认值
        return self._config.get("hybrid_mode", {}).get("cache_settings", {}).get("freshness_threshold_minutes", 5)
    
    def get_tool_cache_setting(self, tool_name: str) -> Optional[bool]:
        """获取工具的缓存使用设置"""
        # 先检查工具特定配置
        tool_config = self._config.get("tool_settings", {}).get("tool_overrides", {}).get(tool_name, {})
        if "use_cache" in tool_config:
            return tool_config["use_cache"]
        
        # 返回默认设置
        return self._config.get("tool_settings", {}).get("default_use_cache")
    
    def should_auto_sync_on_search(self) -> bool:
        """是否在搜索时自动同步"""
        return self._config.get("hybrid_mode", {}).get("cache_settings", {}).get("auto_sync_on_search", True)
    
    def get_priority_folders(self) -> List[str]:
        """获取优先同步的文件夹"""
        return self._config.get("hybrid_mode", {}).get("cache_settings", {}).get("priority_folders", ["INBOX"])
    
    def get_query_strategy(self) -> Dict[str, Any]:
        """获取查询策略配置"""
        return self._config.get("hybrid_mode", {}).get("query_strategy", {})
    
    def get_performance_settings(self) -> Dict[str, Any]:
        """获取性能配置"""
        return self._config.get("hybrid_mode", {}).get("performance", {})
    
    def get_fallback_settings(self) -> Dict[str, Any]:
        """获取降级策略配置"""
        return self._config.get("hybrid_mode", {}).get("fallback", {})
    
    def reload(self):
        """重新加载配置"""
        self._config = self._load_config()
        logger.info("Hybrid config reloaded")
    
    def get_all_config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config.copy()

# 全局配置实例
def get_hybrid_config() -> HybridConfig:
    """获取混合配置单例"""
    return HybridConfig()