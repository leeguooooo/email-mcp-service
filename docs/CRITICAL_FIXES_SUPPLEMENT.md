# 关键修复补充 - UID vs 序号问题

## 🐛 额外发现的问题

### 1. get_email_headers 使用序号而非 UID ✅

**问题**: 使用 `mail.fetch(email_id, ...)` 但 `email_id` 实际是 UID

**位置**: `src/services/email_service.py:482`

**影响**: 
- 外层所有工具都按 UID 传递 `email_id`
- `mail.fetch()` 只接受序号（sequence number），不是 UID
- 会把 UID 当成序号，导致获取错误的邮件或失败
- **严重性**: HIGH - 工具在大多数场景下都会失败

**原因**: 
IMAP 有两种标识邮件的方式：
- **Sequence Number**: 1, 2, 3... (会变化，删除邮件后重新编号)
- **UID**: 唯一且不变的标识符

项目中统一使用 UID，但 `fetch()` 命令默认使用 sequence number。

**修复**:

```python
# ❌ 错误：使用 fetch() + UID
_, msg_data = mail.fetch(email_id, '(BODY.PEEK[HEADER.FIELDS (...)])')

# ✅ 正确：使用 uid() + fetch
_, msg_data = mail.uid('fetch', email_id, '(BODY.PEEK[HEADER.FIELDS (...)])')
```

**完整修复代码**:

```python
def get_email_headers(self, email_id: str, ...) -> Dict[str, Any]:
    mail = conn_mgr.connect_imap()
    
    try:
        mail.select(folder, readonly=True)
        
        # ✅ 使用 UID fetch
        fetch_command = '(BODY.PEEK[HEADER.FIELDS ({})])'.format(' '.join(headers))
        _, msg_data = mail.uid('fetch', email_id, fetch_command)
        
        # ✅ 正确解析 UID fetch 返回值
        # UID fetch 返回格式: 
        # [(b'123 (UID 123 BODY[HEADER.FIELDS (...)] {size})', b'header_data'), ...]
        header_data = None
        if isinstance(msg_data[0], tuple) and len(msg_data[0]) >= 2:
            header_data = msg_data[0][1]
        elif isinstance(msg_data[0], bytes):
            header_data = msg_data[0]
        
        if not header_data:
            return {'error': 'Failed to parse email headers', 'success': False}
        
        # 继续处理...
        
    finally:
        conn_mgr.close_imap(mail)
```

**为什么要用 UID**:

| 场景 | Sequence Number | UID |
|------|----------------|-----|
| 删除邮件后 | 编号会改变 | 保持不变 |
| 多客户端 | 不可靠 | 可靠 |
| 跨会话 | 不可靠 | 可靠 |
| 性能 | 略快 | 略慢但安全 |

**项目约定**: 所有 `email_id` 都是 UID，所有 IMAP 操作都应使用 `mail.uid()` 命令。

### 2. search_emails fallback 分支未处理 offset ✅

**问题**: Schema 定义了 `offset` 参数，但 fallback 分支未处理

**位置**: `src/services/email_service.py:429`

**影响**:
- 在没有 `optimized_search` 模块的环境（大多数部署）
- 使用 offset 分页时会得到重复的结果
- 调用方以为分页生效了，实际上每次都返回前 N 条

**示例**:

```python
# ❌ 修复前的行为
page1 = mcp.call("search_emails", {"query": "test", "limit": 10, "offset": 0})
# 返回: emails 1-10

page2 = mcp.call("search_emails", {"query": "test", "limit": 10, "offset": 10})
# 期望: emails 11-20
# 实际: emails 1-10 (重复！)
```

**修复**:

```python
# ❌ 错误：忽略 offset
result = search_ops.search_emails(
    query=query,
    limit=limit  # 只取 limit 条
)

# ✅ 正确：fetch more and slice
fetch_limit = limit + offset if offset > 0 else limit
result = search_ops.search_emails(
    query=query,
    limit=fetch_limit  # 取 limit + offset 条
)
result = self._ensure_success_field(result)

# 应用分页
if offset > 0 and 'emails' in result:
    result['emails'] = result['emails'][offset:offset + limit]
    result['offset'] = offset
    result['limit'] = limit
```

**为什么这样做**:

SearchOperations 不支持 offset 参数（底层限制），所以我们：
1. 获取更多邮件 (limit + offset)
2. 在内存中切片返回正确的页

**性能考虑**:

| Offset | Fetch | Performance |
|--------|-------|-------------|
| 0 | 10 | ✅ 快 |
| 10 | 20 | ⚠️ 略慢 |
| 100 | 110 | ❌ 慢（获取100条浪费） |

**建议**: 对于大 offset，应该提示用户使用 optimized_search 或限制最大 offset。

## 🔍 其他需要检查的地方

### 相关操作也应该用 UID

检查项目中其他使用 `mail.fetch()` 的地方，确保都改为 `mail.uid('fetch', ...)`：

```bash
# 搜索可能有问题的代码
grep -r "mail.fetch(" src/
```

**常见操作对照表**:

| 操作 | 错误 | 正确 |
|------|------|------|
| 获取邮件 | `mail.fetch(id, ...)` | `mail.uid('fetch', id, ...)` |
| 搜索 | `mail.search(...)` | `mail.uid('search', ...)` |
| 标记 | `mail.store(id, ...)` | `mail.uid('store', id, ...)` |
| 复制 | `mail.copy(id, ...)` | `mail.uid('copy', id, ...)` |

### UID 返回值解析

UID 命令的返回值格式与普通命令不同：

```python
# 普通 fetch 返回
# [(b'1 (FLAGS (...) BODY[...] {...})', b'data'), ...]

# UID fetch 返回（注意多了 UID 字段）
# [(b'1 (UID 123 FLAGS (...) BODY[...] {...})', b'data'), ...]
```

解析时需要注意提取正确的部分。

## 📊 测试验证

### 测试 get_email_headers

```python
import imaplib

# 创建测试环境
mail = imaplib.IMAP4_SSL('imap.example.com')
mail.login('user', 'pass')
mail.select('INBOX')

# 获取一个真实 UID
_, uids = mail.uid('search', None, 'ALL')
test_uid = uids[0].split()[0].decode()

# ❌ 错误方式（会失败或获取错误邮件）
status, data = mail.fetch(test_uid, '(BODY.PEEK[HEADER.FIELDS (From Subject)])')
print("Fetch:", status, data)  # 可能失败

# ✅ 正确方式
status, data = mail.uid('fetch', test_uid, '(BODY.PEEK[HEADER.FIELDS (From Subject)])')
print("UID Fetch:", status, data)  # 成功

mail.logout()
```

### 测试 search_emails offset

```python
# 测试分页一致性
def test_pagination():
    # 获取前20条
    all_20 = mcp.call("search_emails", {"query": "test", "limit": 20, "offset": 0})
    
    # 分两页获取
    page1 = mcp.call("search_emails", {"query": "test", "limit": 10, "offset": 0})
    page2 = mcp.call("search_emails", {"query": "test", "limit": 10, "offset": 10})
    
    # 验证
    assert page1['emails'] == all_20['emails'][:10]
    assert page2['emails'] == all_20['emails'][10:20]
    assert page1['emails'][0]['id'] != page2['emails'][0]['id']  # 不重复
    
    print("✅ Pagination test passed")
```

## 📝 代码审查清单

在处理 IMAP 操作时，检查以下几点：

- [ ] **使用 UID**: 所有 `email_id` 操作都使用 `mail.uid()` 命令
- [ ] **解析返回值**: UID 命令返回格式与普通命令不同
- [ ] **分页处理**: 所有支持 offset 的地方都正确实现
- [ ] **错误处理**: UID 不存在时返回明确错误
- [ ] **文档说明**: 参数文档中明确说明是 UID 而非序号

## 🎓 经验教训

### 1. **理解 IMAP 协议**
- 不要假设所有标识符都一样
- UID 和 sequence number 是不同的概念
- 默认命令使用 sequence number

### 2. **完整实现新功能**
- Schema 定义参数 → Handler 传递 → Service 实现
- 不要只实现一个分支，要覆盖所有 fallback

### 3. **测试所有路径**
- 测试有优化模块和没有优化模块的情况
- 测试边界条件（offset=0, offset>total）
- 测试实际的 UID 操作，不要只测试模拟数据

## 🔗 相关文档

- [IMAP UID Commands](https://www.rfc-editor.org/rfc/rfc3501#section-6.4.8)
- [Python imaplib Documentation](https://docs.python.org/3/library/imaplib.html)
- [关键修复总结](./CRITICAL_FIXES_20251022.md)

---

**修复日期**: 2025-10-22 (第二轮)  
**修复内容**: UID vs Sequence Number + Offset Fallback  
**严重性**: HIGH  
**测试状态**: ✅ Linting 通过，建议加集成测试


