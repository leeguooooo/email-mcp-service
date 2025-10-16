# 邮件同步验证指南

**日期**: 2025-10-15  
**状态**: ✅ 已验证

---

## 🚀 快速验证

### 1. 运行测试脚本

```bash
# 完整测试（推荐）
python3 test_sync.py

# 查看测试日志
tail -f test_sync.log
```

### 2. 使用MCP工具验证

```bash
# 启动MCP服务器
./run.sh

# 在另一个终端或通过MCP客户端调用：

# 获取同步状态
mcp call sync_emails '{"action": "status"}'

# 强制同步
mcp call sync_emails '{"action": "force"}'

# 搜索缓存邮件
mcp call sync_emails '{"action": "search", "query": "关键词"}'

# 查看健康状态
mcp call get_sync_health

# 查看同步历史
mcp call get_sync_history '{"hours": 24}'

# 查看连接池统计
mcp call get_connection_pool_stats
```

---

## 📊 验证结果示例

### 测试输出
```
🚀 邮件同步测试开始 - 2025-10-15 17:09:43
📝 日志文件: test_sync.log

============================================================
测试 1: 检查同步状态
============================================================
✅ 同步管理器初始化成功
📊 同步状态: {...}

============================================================
测试 2: 强制同步
============================================================
📧 测试账户: example@163.com
🔄 开始同步...
✅ 同步完成!
📊 结果: {
    'success': True,
    'folders_synced': 23,
    'emails_added': 103,
    'emails_updated': 0
}

============================================================
测试 3: 搜索缓存邮件
============================================================
🔍 获取最近20封邮件...
✅ 找到 20 封缓存邮件
   1. 邮件主题1
      发件人: 发件人1
      时间: 2025-10-15 17:06:05
   ...

============================================================
测试 4: 健康监控
============================================================
✅ 整体健康状况: healthy
📊 统计:
   - 总账户数: 1
   - 健康账户: 1
   - 平均分数: 100.0/100
   - 成功率: 100.0%

============================================================
测试 5: 连接池统计
============================================================
✅ 连接池统计:
   - 总创建: 1
   - 复用次数: 0
   - 已关闭: 0
   - 活跃连接: 1

总计: 5/5 测试通过
🎉 所有测试通过!
```

---

## 📝 日志位置

### 1. 测试日志
```bash
# 查看测试日志
cat test_sync.log

# 实时监控
tail -f test_sync.log
```

### 2. 同步日志（如果配置了）
```bash
# 配置文件: sync_config.json
cat sync.log

# 实时监控
tail -f sync.log
```

### 3. 应用程序日志
```bash
# 如果通过MCP服务器运行
# 日志会输出到标准输出
./run.sh 2>&1 | tee mcp_server.log
```

### 4. 健康监控历史
```bash
# 查看健康监控历史（JSON格式）
cat sync_health_history.json | python3 -m json.tool
```

---

## 🔍 检查同步数据

### 查看数据库
```bash
# 使用SQLite查看同步的邮件
sqlite3 email_sync.db

# 查看账户
sqlite> SELECT * FROM accounts;

# 查看文件夹
sqlite> SELECT * FROM folders;

# 查看邮件数量
sqlite> SELECT COUNT(*) FROM emails;

# 查看最近邮件
sqlite> SELECT subject, sender, date_sent 
        FROM emails 
        ORDER BY date_sent DESC 
        LIMIT 10;

# 退出
sqlite> .quit
```

### 使用Python脚本
```python
import sqlite3

conn = sqlite3.connect('email_sync.db')
cursor = conn.cursor()

# 查看账户
cursor.execute("SELECT id, email, provider FROM accounts")
print("账户:", cursor.fetchall())

# 查看邮件数
cursor.execute("SELECT COUNT(*) FROM emails")
print("总邮件数:", cursor.fetchone()[0])

# 查看未读邮件数
cursor.execute("SELECT COUNT(*) FROM emails WHERE is_read = 0")
print("未读邮件:", cursor.fetchone()[0])

conn.close()
```

---

## 🐛 常见问题

### 问题1: 缺少schedule模块
```bash
# 错误: ModuleNotFoundError: No module named 'schedule'

# 解决:
pip3 install schedule
# 或
uv pip install schedule
```

### 问题2: 循环导入错误
```bash
# 错误: ImportError: circular import

# 解决: 已在代码中使用延迟导入修复
# 确保使用最新版本的代码
```

### 问题3: 没有看到日志
```bash
# 原因: 日志级别太高或未配置

# 解决1: 检查配置
cat sync_config.json | grep -A 5 '"logging"'

# 解决2: 运行测试脚本（自动配置日志）
python3 test_sync.py

# 解决3: 启用文件日志
# 编辑 sync_config.json:
{
  "logging": {
    "level": "INFO",
    "file_enabled": true,
    "file_path": "sync.log"
  }
}
```

### 问题4: 账户健康状态显示 "no_accounts"
```bash
# 原因: 没有配置邮箱账户或账户未同步

# 解决: 
# 1. 检查accounts.json
cat accounts.json

# 2. 运行一次同步
python3 test_sync.py

# 或通过MCP
mcp call sync_emails '{"action": "force"}'
```

---

## 📈 性能监控

### 查看同步性能
```bash
# 使用MCP工具
mcp call get_sync_history '{"hours": 24}'

# 输出示例:
📜 同步历史 (最近 24 小时, 所有账户)

✅ 10-15 17:10 - 增量同步: 103 封邮件 (8.2秒)
✅ 10-15 14:55 - 增量同步: 45 封邮件 (5.1秒)
✅ 10-15 14:40 - 增量同步: 23 封邮件 (3.5秒)
```

### 查看连接池效率
```bash
mcp call get_connection_pool_stats

# 输出示例:
🔌 IMAP 连接池统计

• 总创建连接数: 15
• 复用次数: 145
• 已关闭连接数: 3
• 等待次数: 2
• 等待超时次数: 0

• 活跃账户数: 5
• 总活跃连接数: 12

📈 连接复用率: 90.6%
```

---

## ⚙️ 配置说明

### 同步配置 (sync_config.json)
```json
{
  "sync": {
    "enabled": true,              // 启用同步
    "auto_start": true,           // 自动启动
    "interval_minutes": 15,       // 同步间隔（分钟）
    "full_sync_hours": 24,        // 完全同步间隔（小时）
    "first_sync_days": 180,       // 首次同步天数
    "incremental_sync_days": 7    // 增量同步天数
  },
  "logging": {
    "level": "INFO",              // 日志级别
    "file_enabled": true,         // 启用文件日志
    "file_path": "sync.log"       // 日志文件路径
  }
}
```

### 日志级别
- `DEBUG`: 详细调试信息（最详细）
- `INFO`: 一般信息（推荐）
- `WARNING`: 警告信息
- `ERROR`: 错误信息（最简洁）

---

## 🎯 推荐验证流程

### 首次验证
```bash
# 1. 安装依赖
pip3 install schedule

# 2. 运行完整测试
python3 test_sync.py

# 3. 检查测试结果
# 应该看到: "🎉 所有测试通过!"

# 4. 查看同步的邮件
sqlite3 email_sync.db "SELECT COUNT(*) FROM emails;"

# 5. 查看健康状态
python3 -c "
from src.background.sync_health_monitor import get_health_monitor
monitor = get_health_monitor()
import json
print(json.dumps(monitor.get_overall_health(), indent=2))
"
```

### 日常监控
```bash
# 通过MCP工具
mcp call get_sync_health
mcp call get_connection_pool_stats

# 或查看日志
tail -f sync.log
tail -f test_sync.log
```

---

## 📚 相关文档

- [同步改进文档](./docs/SYNC_IMPROVEMENTS.md)
- [连接池修复](./docs/CONNECTION_POOL_FIX.md)
- [死锁修复](./docs/DEADLOCK_FIX.md)
- [架构文档](./docs/ARCHITECTURE.md)

---

## ✅ 验证清单

- [x] 安装schedule模块
- [x] 修复循环导入
- [x] 运行测试脚本
- [x] 所有测试通过 (5/5)
- [x] 同步成功 (103封邮件)
- [x] 缓存可搜索 (20封邮件)
- [x] 健康监控正常 (100/100)
- [x] 连接池正常 (1个连接)

**验证状态**: ✅ **完全通过!**


