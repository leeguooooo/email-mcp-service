# 故障排除指南

## 常见错误及解决方案

### 1. 连接检查错误

**错误信息**: `string indices must be integers, not 'str'`

**原因**: 系统期望字典但收到了字符串

**解决方案**:
```bash
# 运行快速修复
uv run python quick_fix.py
```

### 2. 数据库锁定错误

**错误信息**: `database is locked`

**原因**: 
- 多个进程同时访问数据库
- WAL文件未清理
- 同步进程异常退出

**解决方案**:
```bash
# 1. 停止所有同步进程
pkill -f "sync_manager|email_sync"

# 2. 清理数据库锁
uv run python optimize_db.py unlock

# 3. 优化数据库
uv run python optimize_db.py
```

### 3. NoneType 错误

**错误信息**: `'NoneType' object has no attribute 'execute'`

**原因**: 使用连接池时直接访问 conn 属性

**解决方案**: 已在最新版本修复，使用 `execute()` 方法替代直接访问

### 4. NOT NULL 约束失败

**错误信息**: `NOT NULL constraint failed: folders.account_id`

**原因**: 同步时未指定账户ID

**解决方案**: 已在最新版本修复，自动选择默认账户

## 快速诊断命令

### 检查系统状态
```bash
# 1. 检查连接
uv run python -c "
import sys
sys.path.insert(0, 'src')
from legacy_operations import check_connection
print(check_connection())
"

# 2. 检查数据库
uv run python optimize_db.py

# 3. 检查同步进程
uv run python check_sync_processes.py
```

### 一键修复
```bash
# 运行快速修复工具（推荐）
uv run python quick_fix.py
```

## 性能优化建议

### 1. 数据库优化
```bash
# 定期运行（建议每周一次）
uv run python optimize_db.py
```

### 2. 调整同步频率
编辑 `sync_config.json`:
```json
{
  "sync": {
    "interval_minutes": 30,  // 增加间隔减少负载
    "first_sync_days": 90    // 减少首次同步范围
  }
}
```

### 3. 使用混合模式
编辑 `hybrid_config.json`:
```json
{
  "hybrid_mode": {
    "enabled": true,
    "cache_settings": {
      "freshness_threshold_minutes": 10  // 增加阈值减少远程查询
    }
  }
}
```

## 日志分析

### 查看日志
```bash
# 实时查看日志
tail -f sync.log

# 搜索错误
grep ERROR sync.log

# 查看特定账户日志
grep "leeguoo@163.com" sync.log
```

### 常见日志模式

1. **正常同步**:
   ```
   INFO - Starting sync for 3 accounts
   INFO - Sync completed: 10 added, 5 updated
   ```

2. **连接问题**:
   ```
   ERROR - IMAP connection error: [Errno 60] Operation timed out
   ```

3. **认证问题**:
   ```
   ERROR - IMAP authentication error: [AUTHENTICATIONFAILED]
   ```

## 预防措施

1. **定期备份**:
   ```bash
   cp email_sync.db email_sync.db.backup
   ```

2. **监控数据库大小**:
   ```bash
   ls -lh email_sync.db
   ```

3. **清理旧数据**:
   ```bash
   # 清理90天前的邮件
   uv run python -c "
   from src.database.email_sync_db import EmailSyncDatabase
   db = EmailSyncDatabase()
   db.execute('DELETE FROM emails WHERE date_sent < date(\"now\", \"-90 days\")')
   "
   ```

## 获取帮助

如果问题持续存在：

1. 收集诊断信息：
   ```bash
   uv run python quick_fix.py > diagnostic.log 2>&1
   ```

2. 检查版本：
   ```bash
   git log --oneline -5
   ```

3. 提交问题：
   - 包含错误信息
   - 包含 diagnostic.log
   - 描述重现步骤