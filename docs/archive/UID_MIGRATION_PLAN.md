# UID 迁移和性能优化计划

## 当前问题

### 1. UID/序列号混淆（严重）
- `search_emails` 返回 UID 作为 `id`
- `list_emails` 返回序列号作为 `id`  
- 所有操作函数（`get_email_detail`, `mark_email_read`, `delete_email` 等）假设传入的是序列号
- **结果**：search 后的操作会作用于错误的邮件

### 2. 性能问题
- `fetch_emails` 使用 `(RFC822)` 下载**完整邮件**（包括附件）
- 50封邮件 = 重复下载50次完整内容
- 应该只获取头部：`(BODY.PEEK[HEADER.FIELDS (From Subject Date)] FLAGS)`

### 3. Sync DB 未使用
- 有完整的 `email_sync.db` 和后台同步
- 但所有 MCP 工具仍然实时查询 IMAP
- 浪费了缓存

## 修复方案

### 阶段 1：修复 UID 混淆（紧急）

#### 1.1 统一 ID 格式
所有函数返回：
```python
{
    "id": "seq_123",      # 向后兼容的序列号格式
    "uid": "1186",        # 真实的 UID（如果可用）
    ...
}
```

#### 1.2 修改 `get_email_detail` 
```python
def get_email_detail(email_id, folder="INBOX", account_id=None):
    # 尝试作为 UID
    if email_id and str(email_id).isdigit():
        try:
            result, data = mail.uid('fetch', email_id, '(RFC822)')
            if result == 'OK' and data and data[0]:
                # 成功，是 UID
                return process_email(data, is_uid=True)
        except:
            pass
    
    # 回退到序列号
    result, data = mail.fetch(email_id, '(RFC822)')
    return process_email(data, is_uid=False)
```

#### 1.3 修改所有写操作函数
同样的模式应用到：
- `mark_email_read`
- `delete_email`
- `move_email_to_trash`
- `batch_move_to_trash`
- `batch_delete_emails`
- `batch_mark_read`

### 阶段 2：性能优化

#### 2.1 优化 `fetch_emails`
```python
# 当前（慢）：
result, data = mail.fetch(email_id, '(RFC822)')  # 下载完整邮件

# 优化后（快）：
result, data = mail.fetch(email_id, 
    '(BODY.PEEK[HEADER.FIELDS (From Subject Date Message-ID)] FLAGS RFC822.SIZE)')
```

#### 2.2 使用 UID 而不是序列号
```python
# fetch_emails 应该使用 UID：
result, data = mail.uid('search', None, 'ALL')
email_uids = data[0].split()

for uid in email_uids:
    result, data = mail.uid('fetch', uid, '(HEADER ...)')
```

### 阶段 3：利用 Sync DB（可选）

修改 `EmailService` 首先查询本地 DB：
```python
def list_emails(self, limit=50, unread_only=False, folder="INBOX", account_id=None):
    # 1. 尝试从 sync DB 读取
    cached_emails = self.sync_db.get_emails(account_id, folder, limit)
    
    if cached_emails and self.is_cache_fresh():
        return cached_emails
    
    # 2. 回退到 IMAP
    return self.fetch_from_imap(...)
```

## 实施顺序

1. **立即修复**：阶段 1.1-1.3（修复 UID 混淆）
2. **短期优化**：阶段 2.1-2.2（性能提升）
3. **长期改进**：阶段 3（使用缓存）

## 测试场景

### UID 修复测试
1. 运行 `search_emails(query="test")`
2. 获取返回的第一封邮件的 `id`
3. 调用 `get_email_detail(email_id=id)`
4. ✅ 应该返回**同一封邮件**的详情

### 性能测试
```python
import time

# 前
start = time.time()
list_emails(limit=50)
print(f"Time: {time.time() - start}s")  # 应该 < 5秒

# 后  
start = time.time()
list_emails(limit=50)
print(f"Time: {time.time() - start}s")  # 应该 < 2秒
```

## 兼容性保证

- ✅ 旧代码传递序列号仍然工作（回退机制）
- ✅ 新代码传递 UID 也工作（优先尝试）
- ✅ 响应包含 `id` 和 `uid` 两个字段
- ✅ 逐步迁移，不需要一次性修改所有调用方


