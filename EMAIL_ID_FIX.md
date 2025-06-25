# 邮件ID修复说明

## 问题描述

之前的邮件系统存在ID不匹配的问题：
- 邮件列表显示的ID (如1880) 是数据库中的UID
- 但IMAP服务器的实际序列号范围更小 (如Gmail只有1-299)
- 导致 `get_email_detail` 和 `delete_emails` 功能无法正常工作

## 解决方案

### 1. 使用数据库ID作为统一标识

现在邮件列表显示的是数据库自增ID，而不是UID：
```python
'id': str(row.get('id', ''))  # 使用数据库ID
```

### 2. 创建改进的操作函数

**文件：** `src/operations/improved_email_ops.py`

#### get_email_detail_by_db_id()
- 输入：数据库ID
- 过程：
  1. 在数据库中查找邮件信息（UID、folder、account等）
  2. 连接对应的IMAP服务器
  3. 通过UID查找IMAP中的邮件
  4. 获取完整的邮件内容
- 输出：完整的邮件详情

#### delete_emails_by_db_ids()
- 输入：数据库ID列表
- 过程：
  1. 查找所有邮件的IMAP信息
  2. 按账户和文件夹分组
  3. 连接各个IMAP服务器执行删除
  4. 更新数据库标记为已删除
- 输出：删除结果统计

### 3. 更新工具处理器

**文件：** `src/core/tool_handlers.py`

- `handle_get_email_detail()`: 优先使用新的 `get_email_detail_by_db_id()`
- `handle_delete_emails()`: 优先使用新的 `delete_emails_by_db_ids()`
- 保留向后兼容的fallback机制

### 4. 移除sync_emails的查询功能

- 移除了 `action: "search"` 和 `action: "recent"`
- 查询邮件应使用专门的工具：`list_emails` 和 `search_emails`
- 简化了sync_emails工具，只保留核心同步功能

## 使用示例

### 获取邮件列表
```json
{
  "limit": 50,
  "unread_only": false
}
```

返回格式：
```
📧 50 封邮件 (23 未读)
💡 使用 get_email_detail 工具和 [ID] 查看详情
🗑️ 使用 delete_emails 工具和 [ID] 删除邮件

📮 leeguoo@163.com (30封，10未读)

🔴[784] 重要会议提醒 | 张三 | 06-20 14:30
  [785] 周报已提交 | 李四 | 06-20 12:15
```

### 查看邮件详情
```json
{
  "email_id": "784",
  "account_id": "leeguooooo_gmail"
}
```

### 删除邮件
```json
{
  "email_ids": ["784", "785", "786"],
  "account_id": "leeguooooo_gmail"
}
```

## 技术优势

1. **统一的ID系统**：数据库ID在整个系统中保持一致
2. **自动映射**：系统自动处理数据库ID到IMAP序列号的映射
3. **错误恢复**：当IMAP中找不到邮件时，降级使用数据库数据
4. **批量操作**：支持高效的批量删除，按账户分组处理
5. **向后兼容**：保留了旧功能的fallback机制

## 注意事项

- 数据库ID是永久的，即使邮件在IMAP中被删除，ID也不会重复使用
- 如果邮件在IMAP中找不到，系统会尝试使用数据库中的现有信息
- 删除操作会同时更新IMAP服务器和本地数据库状态