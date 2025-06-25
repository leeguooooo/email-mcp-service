# 邮件同步架构设计

## 一、架构概述

MCP Email Service 采用了**混合查询架构**，结合本地缓存和远程IMAP查询，解决了实时性和性能的平衡问题。

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  MCP Tools  │────▶│ Hybrid Mgr   │────▶│ Local DB    │
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │                      │
                           ▼                      │
                    ┌──────────────┐              │
                    │ IMAP Server  │◀─────────────┘
                    └──────────────┘     (Sync)
```

## 二、核心问题解决方案

### 1. 实时性问题

**问题**：本地数据库可能没有最新邮件

**解决方案**：
- **智能新鲜度判断**：根据数据年龄自动决定是否需要远程查询
- **快速同步机制**：只同步最新的10-20封邮件，快速更新
- **优先级策略**：未读邮件、最近日期的搜索优先获取最新数据

### 2. 一致性保证

**写操作流程**：
```
删除/标记请求 → 远程IMAP执行 → 成功 → 更新本地DB
                              ↓ 失败
                          返回错误，本地不变
```

### 3. 性能优化

- **并行同步**：多账户并行处理
- **增量同步**：只同步变化的部分
- **智能缓存**：元数据积极缓存，正文按需获取

## 三、同步策略

### 1. 后台同步（推荐）

```bash
# 启动守护进程
uv run python sync_manager.py start

# 自动执行：
- 每15分钟增量同步（最近7天）
- 每天凌晨2点完全同步
- 首次同步获取6个月历史
```

### 2. 手动同步

```bash
# MCP工具内
sync_emails with action="force"

# 命令行
uv run python sync_manager.py sync
```

### 3. 实时同步

使用混合模式时，会在需要时自动触发快速同步：
- 搜索操作
- 查看未读邮件
- 数据超过5分钟未更新

## 四、配置管理

### 1. 同步配置 (`sync_config.json`)

```json
{
  "sync": {
    "first_sync_days": 180,        // 首次同步180天
    "incremental_sync_days": 7,    // 增量同步7天
    "interval_minutes": 15         // 同步间隔15分钟
  }
}
```

### 2. 混合模式配置 (`hybrid_config.json`)

```json
{
  "hybrid_mode": {
    "enabled": true,
    "cache_settings": {
      "freshness_threshold_minutes": 5,  // 5分钟内的数据视为新鲜
      "auto_sync_on_search": true        // 搜索时自动同步
    }
  }
}
```

## 五、工具使用指南

### 1. 控制缓存行为

所有读取工具支持 `use_cache` 参数：

```bash
# 强制使用缓存（离线模式）
list_emails with use_cache=true

# 强制实时查询（在线模式）  
list_emails with use_cache=false

# 智能判断（默认）
list_emails
```

### 2. 监控同步状态

```bash
# 查看同步状态
sync_emails with action="status"

# 查看数据新鲜度
get_freshness_status
```

## 六、最佳实践

1. **保持后台同步运行**
   - 使用 `sync_manager.py start` 启动守护进程
   - 确保只有一个同步进程（自动检查）

2. **合理配置同步参数**
   - 网络好：降低同步间隔（5-10分钟）
   - 网络差：增加同步间隔（30-60分钟）

3. **监控数据库大小**
   - 定期清理90天前的邮件
   - 使用 `VACUUM` 优化数据库

4. **处理特殊场景**
   - 重要邮件：使用 `use_cache=false` 确保实时
   - 批量操作：使用缓存提高性能

## 七、故障处理

### 常见问题

1. **找不到新邮件**
   ```bash
   # 强制同步
   sync_emails with action="force"
   ```

2. **同步进程重复**
   ```bash
   # 检查进程
   uv run python check_sync_processes.py
   
   # 停止所有同步
   uv run python sync_manager.py stop
   ```

3. **数据不一致**
   ```bash
   # 重新初始化
   uv run python sync_manager.py init
   ```

## 八、性能指标

- **缓存命中率**：>80%（正常使用）
- **快速同步耗时**：<10秒
- **完整同步耗时**：<5分钟/账户
- **数据库大小**：~1MB/1000封邮件

## 九、未来优化方向

1. **IMAP IDLE支持**：实时推送新邮件
2. **智能预取**：基于使用习惯预取数据
3. **分布式缓存**：支持多客户端共享
4. **增量搜索**：只搜索变化部分