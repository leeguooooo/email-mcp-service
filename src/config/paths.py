"""
路径配置 - 定义项目中使用的所有路径
"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 数据目录（存放运行时生成的文件）
DATA_DIR = PROJECT_ROOT / "data"

# 确保数据目录存在
DATA_DIR.mkdir(exist_ok=True)

# 数据库文件路径
EMAIL_SYNC_DB = str(DATA_DIR / "email_sync.db")
NOTIFICATION_HISTORY_DB = str(DATA_DIR / "notification_history.db")

# 配置文件路径
SYNC_CONFIG_JSON = str(DATA_DIR / "sync_config.json")
SYNC_HEALTH_HISTORY_JSON = str(DATA_DIR / "sync_health_history.json")
DIGEST_CONFIG_JSON = str(DATA_DIR / "daily_digest_config.json")
NOTIFICATION_CONFIG_JSON = str(DATA_DIR / "notification_config.json")
EMAIL_MONITOR_CONFIG_JSON = str(DATA_DIR / "email_monitor_config.json")

# 账户配置文件（数据目录）
ACCOUNTS_JSON = str(DATA_DIR / "accounts.json")

# 日志目录
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 临时文件目录
TEMP_DIR = DATA_DIR / "tmp"
TEMP_DIR.mkdir(exist_ok=True)

# 附件下载目录
ATTACHMENTS_DIR = DATA_DIR / "attachments"
ATTACHMENTS_DIR.mkdir(exist_ok=True)
