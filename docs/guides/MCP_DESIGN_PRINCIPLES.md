# MCP Email Service - 设计原则与能力定位

## 📐 核心设计原则

### 1. **原子级操作** (Atomic Operations)

MCP Email Service 专注于提供**细颗粒度的原子操作**，而非高层次的业务整合。

#### ✅ 我们提供什么
- **单一职责的操作**: 每个工具只做一件事
  - `list_emails` - 获取邮件列表
  - `mark_email_read` - 标记为已读
  - `get_email_headers` - 获取邮件头
  - `delete_email` - 删除邮件

- **数据级能力**: 返回结构化数据，不做解释或整合
  - 邮件元数据（发件人、主题、日期等）
  - 文件夹信息（名称、未读数等）
  - 同步状态（最后同步时间、错误信息等）

#### ❌ 我们不提供什么
- **业务逻辑整合**: 如 "整理收件箱"、"智能分类"
- **AI 能力**: 如翻译、摘要、情感分析
- **复杂工作流**: 如 "删除所有垃圾邮件并生成报告"

### 2. **上层 AI 负责整合** (AI Orchestration)

调用方（如 Claude、GPT、其他 AI Agent）负责：
- 串联多个原子操作完成复杂任务
- 决策和策略（哪些邮件需要删除、归档等）
- 生成摘要、翻译、分类等高级功能

#### 示例对比

**❌ 错误设计**（在 MCP 层做整合）：
```python
# 不应该在 MCP 工具中实现
@tool("organize_inbox")
def organize_inbox():
    """自动整理收件箱，分类垃圾邮件，生成摘要"""
    emails = list_emails()
    spam = ai_model.classify_spam(emails)  # ❌ AI 能力
    summary = translate(emails)  # ❌ 翻译能力
    return {"spam": spam, "summary": summary}
```

**✅ 正确设计**（AI 调用原子操作）：
```python
# AI Agent 的伪代码
emails = mcp_call("list_emails", {"limit": 20})
headers = [mcp_call("get_email_headers", {"email_id": e.id}) for e in emails]

# AI 自己决策
spam_ids = my_ai_model.classify_spam(headers)
important_ids = my_ai_model.find_important(headers)

# 调用原子操作执行
mcp_call("delete_emails", {"email_ids": spam_ids})
summary = my_ai_model.summarize(important_ids)
```

## 🛠️ 当前能力清单 (28 个工具)

### 📧 读取类 (Read Operations)
- `list_emails` - 列举邮件（支持分页、过滤）
- `get_email_detail` - 获取邮件详情
- `get_email_headers` - **[NEW]** 仅获取邮件头（高效分类）
- `search_emails` - 搜索邮件（支持分页）
- `get_email_attachments` - 提取附件信息

### ✏️ 状态类 (State Operations)
- `mark_emails` / `mark_email_read` / `mark_email_unread` - 标记已读/未读（支持 dry_run）
- `batch_mark_read` - 批量标记已读
- `delete_emails` / `delete_email` / `batch_delete_emails` - 删除邮件（支持 dry_run）
- `flag_email` - 标记星标/重要

### 📁 组织类 (Organization Operations)
- `list_folders` - 列举文件夹
- `list_unread_folders` - **[NEW]** 获取各文件夹未读数（原子数据）
- `move_emails_to_folder` - 移动邮件
- `analyze_contacts` - 分析联系人频率（基础统计）
- `get_contact_timeline` - 获取与某人的通信历史

### 💬 沟通类 (Communication Operations)
- `send_email` - 发送邮件
- `reply_email` - 回复邮件
- `forward_email` - 转发邮件

### 🔧 系统类 (System Operations)
- `check_connection` - 测试连接
- `list_accounts` - 列举账号
- `get_recent_activity` - **[NEW]** 获取同步活动统计
- `sync_emails` - 同步控制（start/stop/force/status/config）
- `get_sync_health` - 获取同步健康度
- `get_sync_history` - 获取同步历史
- `get_connection_pool_stats` - 获取连接池统计

## 📝 新增原子工具说明

### `list_unread_folders`
**用途**: 获取各文件夹的未读邮件数量  
**场景**: AI 可以根据这些数据决定优先处理哪个文件夹

```json
{
  "folders": [
    {"name": "INBOX", "unread_count": 15, "total_count": 150, "account": "user@example.com"},
    {"name": "Work", "unread_count": 3, "total_count": 50, "account": "user@example.com"}
  ]
}
```

### `get_email_headers`
**用途**: 只获取邮件头，不拉取邮件正文（高效）  
**场景**: AI 进行快速分类、过滤时无需完整邮件内容

```json
{
  "headers": {
    "From": "sender@example.com",
    "Subject": "Meeting Tomorrow",
    "Date": "Mon, 22 Oct 2025 10:00:00 +0000",
    "Message-ID": "<abc123@example.com>"
  },
  "source": "imap_headers"
}
```

### `get_recent_activity`
**用途**: 获取最近的同步活动和统计  
**场景**: AI 可以根据活动情况决定是否需要触发同步或告警

```json
{
  "accounts": [
    {
      "account": "user@example.com",
      "last_sync": "2025-10-22T10:30:00Z",
      "success_rate": 98.5,
      "last_error": null
    }
  ]
}
```

## 🎯 优化参数说明

### 分页支持
- `list_emails` 新增 `offset` 参数
- `search_emails` 新增 `offset` 参数
- 上层 AI 可以实现分批处理大量邮件

### 元数据支持
- `list_emails` 新增 `include_metadata` 参数
- 返回数据来源（`source: "cache"` 或 `source: "imap"`）
- 帮助 AI 做缓存策略判断

### Dry Run 支持
- `mark_emails` 新增 `dry_run` 参数
- `delete_emails` 新增 `dry_run` 参数
- AI 可以先验证操作，再实际执行

## 📦 示例脚本定位

以下脚本位于 `scripts/` 目录，定位为**参考实现和集成示例**，而非核心能力：

### 示例脚本
- `scripts/email_translator.py` - 翻译示例（调用 OpenAI API）
- `scripts/inbox_organizer.py` - 整理示例（组合多个 MCP 工具）
- `scripts/email_monitor_api.py` - HTTP API 包装（可选部署）

这些脚本展示了**如何使用 MCP 原子操作组合成高级功能**，但不是 MCP 核心的一部分。

## 🔄 迁移建议

如果你正在使用示例脚本，建议：

1. **理解底层调用**: 查看示例脚本，了解它们如何组合原子操作
2. **自定义逻辑**: 根据自己的需求修改脚本逻辑
3. **可选部署**: 如需 HTTP 访问，可部署 `email_monitor_api.py`
4. **本地扩展**: 在 `examples/` 目录创建自己的整合脚本

## 🚀 最佳实践

### 为 AI Agent 设计调用

```python
# ✅ 推荐：组合原子操作
def ai_organize_inbox():
    # 1. 获取文件夹未读数
    folders = mcp.call("list_unread_folders")
    
    # 2. 优先处理未读最多的文件夹
    top_folder = max(folders, key=lambda f: f['unread_count'])
    
    # 3. 获取邮件头（高效）
    emails = mcp.call("list_emails", {"folder": top_folder['name'], "limit": 50})
    headers = [mcp.call("get_email_headers", {"email_id": e['id']}) 
               for e in emails[:10]]  # 只获取前10封的头部
    
    # 4. AI 决策
    spam = my_model.classify(headers)
    
    # 5. 执行原子操作（带 dry_run）
    result = mcp.call("delete_emails", {"email_ids": spam, "dry_run": True})
    if result['success']:
        mcp.call("delete_emails", {"email_ids": spam, "dry_run": False})
```

### 保持工具的单一职责

```python
# ❌ 避免：混合职责
@tool("smart_reply")
def smart_reply(email_id):
    """获取邮件，生成回复，发送"""  # 太复杂
    
# ✅ 推荐：拆分成原子操作
# 1. get_email_detail
# 2. [AI 生成回复内容]
# 3. reply_email
```

## 📖 参考文档

- [HTTP API 快速开始](./HTTP_API_QUICK_START.md) - 如何部署 HTTP 包装
- [生产部署指南](./PRODUCTION_DEPLOYMENT_GUIDE.md) - 生产环境配置
- [项目架构](../ARCHITECTURE.md) - 技术架构说明

## 💡 总结

| 层级 | 职责 | 实现方 |
|------|------|--------|
| **AI 层** | 决策、整合、高级功能（翻译、摘要） | 调用方 AI |
| **MCP 层** | 原子操作、数据访问 | 本项目 |
| **基础设施层** | IMAP/SMTP、缓存、同步 | 本项目 |

**核心理念**: MCP = "乐高积木"，AI = "搭建者"
