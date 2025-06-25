# 邮件去重修复说明

## 问题描述

在使用 `sync_emails` 的 `recent` action 获取最近邮件时，发现有重复邮件出现。例如：
- "上一周招聘的 1 个开发工程师职位" 出现了3次
- 其他邮件也有重复

## 问题原因

数据库中存在重复的邮件记录。同一个 `message_id` 在同一个账户下可能有多条记录，这是因为：
1. 邮件可能存在于多个文件夹（如 INBOX 和 All Mail）
2. 同步过程中可能重复插入了数据

## 解决方案

### 1. 更新查询逻辑（已完成）

在 `src/database/email_sync_db.py` 中更新了以下方法：

#### get_recent_emails 方法
```sql
WITH unique_emails AS (
    SELECT e.*, 
           f.name as folder_name, 
           a.email as account_email,
           ROW_NUMBER() OVER (PARTITION BY e.message_id, e.account_id ORDER BY e.date_sent DESC) as rn
    FROM emails e
    JOIN folders f ON e.folder_id = f.id
    JOIN accounts a ON e.account_id = a.id
    WHERE e.is_deleted = FALSE
)
SELECT * FROM unique_emails
WHERE rn = 1
```

#### search_emails 方法
同样使用了 ROW_NUMBER() 窗口函数来去重。

### 2. 最少显示50封邮件（已完成）

在 `src/core/sync_handlers.py` 的 `_handle_get_recent_cached_emails` 方法中：
```python
limit = args.get('limit', 50)
# 最少显示50封
if limit < 50:
    limit = 50
```

### 3. 清理重复数据（建议）

可以运行以下SQL来清理已有的重复数据：

```sql
-- 查看重复邮件
SELECT message_id, account_id, COUNT(*) as count
FROM emails
WHERE is_deleted = FALSE
GROUP BY message_id, account_id
HAVING COUNT(*) > 1;

-- 删除重复（保留最新的）
DELETE FROM emails
WHERE id NOT IN (
    SELECT MIN(id)
    FROM emails
    GROUP BY message_id, account_id
);
```

## 效果

修复后：
- 每个邮件只显示一次（基于 message_id 和 account_id 的组合）
- 保留最新的邮件记录（基于 date_sent）
- 最近邮件最少显示50封

## 使用示例

```json
{
  "action": "recent",
  "limit": 20
}
```

即使指定 limit 为 20，实际也会返回 50 封邮件。