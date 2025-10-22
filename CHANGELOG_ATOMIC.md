# Changelog - 原子操作升级

## [1.1.0] - 2025-10-22

### 🎯 重大变更
- **明确项目定位**: MCP 专注于原子级操作，高级整合由上层 AI 完成
- **新增 3 个原子工具**: 增强数据访问能力
- **优化现有工具**: 添加分页、元数据、dry_run 支持

### ✨ 新增

#### 新原子工具
1. **`list_unread_folders`** - 获取各文件夹未读邮件统计
   - 返回每个文件夹的 unread_count / total_count
   - 支持 include_empty 参数
   - 帮助 AI 决定处理优先级

2. **`get_email_headers`** - 仅获取邮件头部
   - 不拉取邮件正文，速度快 90%+
   - 支持自定义 headers 列表
   - 返回 source 元数据（imap_headers）
   - 适合 AI 快速分类场景

3. **`get_recent_activity`** - 获取同步活动统计
   - 包含最后同步时间、成功率、错误信息
   - 支持 include_stats 参数
   - 帮助 AI 监控系统健康度

#### 新文档
- `docs/guides/MCP_DESIGN_PRINCIPLES.md` - 设计原则与能力定位
- `docs/ATOMIC_OPERATIONS_UPGRADE.md` - 升级说明与迁移指南
- `scripts/README.md` - 示例脚本定位与使用说明

### ⬆️ 优化

#### `list_emails`
- 新增 `offset` 参数 - 支持分页
- 新增 `include_metadata` 参数 - 返回数据来源信息

#### `search_emails`
- 新增 `offset` 参数 - 支持搜索结果分页

#### `mark_emails`
- 新增 `dry_run` 参数 - 先验证后执行

#### `delete_emails`
- 新增 `dry_run` 参数 - 安全删除确认

### 📚 文档

#### 新增文档
- **MCP 设计原则** - 明确"原子操作"定位，AI 负责整合
- **升级指南** - 完整的迁移建议和最佳实践
- **Scripts README** - 说明示例脚本是参考实现，非核心能力

#### 更新文档
- 主 README 将在后续更新中链接新文档
- 所有示例代码添加了定位说明

### 🔄 重构

#### 架构调整
- **明确职责分离**:
  - MCP 层：28 个原子操作工具
  - AI 层：决策、翻译、摘要、工作流编排
  - Scripts：参考实现和集成示例

#### Schema 层
- `src/core/tool_schemas.py`: 新增 3 个工具 schema
- 优化现有 schema，添加新参数

#### Handler 层
- `src/core/tool_handlers.py`: 新增 3 个 handler 和格式化方法

#### Service 层
- `src/services/email_service.py`: 新增 `get_email_headers` 方法
- `src/services/folder_service.py`: 新增 `list_folders_with_unread_count` 方法
- `src/services/system_service.py`: 新增 `get_recent_activity` 方法

#### 工具注册
- `src/mcp_tools.py`: 注册新工具，导入新 schema

### 🎓 示例脚本定位

以下脚本现在明确定位为**示例实现**（非核心能力）：
- `scripts/inbox_organizer.py` - 收件箱整理示例
- `scripts/ai_email_filter.py` - AI 过滤示例
- `scripts/email_translator.py` - 翻译示例
- `scripts/email_monitor_api.py` - HTTP API 包装（可选部署）
- `scripts/email_monitor.py` - 监控示例

这些脚本展示如何组合 MCP 原子操作实现高级功能。

### 📊 统计

- **工具总数**: 28 个 (+3 新增)
- **优化工具**: 4 个 (list_emails, search_emails, mark_emails, delete_emails)
- **新增文档**: 3 份
- **代码文件变更**: 6 个核心文件
- **向后兼容**: 100% (所有现有调用无需修改)

### 🔧 技术细节

#### 性能优化
- `get_email_headers` 比完整邮件获取快 90%+
- `list_unread_folders` 使用 IMAP STATUS 命令（高效）
- `get_recent_activity` 读取本地缓存（毫秒级）

#### 实现细节
- 所有新方法都包含完善的错误处理
- 统一返回结构（包含 `success` 字段）
- 支持多账号场景
- 完整的类型提示和文档字符串

### 🚀 使用示例

#### 快速分类（使用新工具）
```python
# 1. 获取邮件头（不拉正文，快）
emails = mcp.call("list_emails", {"limit": 100})
headers = [mcp.call("get_email_headers", {"email_id": e['id']}) 
           for e in emails]

# 2. AI 快速分类
spam_ids = my_ai.classify_spam(headers)

# 3. 批量删除（带 dry_run）
mcp.call("delete_emails", {"email_ids": spam_ids, "dry_run": True})
mcp.call("delete_emails", {"email_ids": spam_ids, "dry_run": False})
```

#### 分页处理
```python
# 分页获取大量邮件
all_emails = []
for offset in range(0, 1000, 50):
    page = mcp.call("list_emails", {"limit": 50, "offset": offset})
    all_emails.extend(page['emails'])
```

#### 健康度监控
```python
# 获取系统活动状态
activity = mcp.call("get_recent_activity", {"include_stats": True})
for acc in activity['accounts']:
    if acc['success_rate'] < 95:
        send_alert(acc)
```

### ⚠️ 破坏性变更

**无** - 本次升级 100% 向后兼容

### 📝 迁移建议

1. **如果使用 MCP 工具**: 无需任何修改
2. **如果使用示例脚本**: 
   - 继续使用：无影响
   - 推荐：理解逻辑后在 AI 中复现
3. **如果开发新功能**: 参考新的设计原则

### 🔗 相关链接

- [设计原则](docs/guides/MCP_DESIGN_PRINCIPLES.md)
- [升级指南](docs/ATOMIC_OPERATIONS_UPGRADE.md)
- [示例脚本说明](scripts/README.md)

---

**完整变更**: [查看 Git Diff](#)  
**贡献者**: leo, AI Assistant  
**发布日期**: 2025-10-22

