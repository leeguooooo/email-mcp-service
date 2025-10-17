# 性能优化计划

## 当前性能瓶颈分析

### 🐌 问题 1: 下载完整邮件（最严重）

**现状**：
```python
# src/legacy_operations.py:159
mail.fetch(email_id, '(RFC822)')  # 下载完整邮件（正文+附件）
```

**影响**：
- 列出 50 封邮件 = 下载 50 封完整邮件
- 每封 1-5MB（带附件）→ 总共 50-250MB
- 网络传输时间：数十秒甚至分钟

**解决方案**：
```python
# 只下载头部信息
fetch_parts = '(BODY.PEEK[HEADER.FIELDS (From To Subject Date Message-ID)] FLAGS RFC822.SIZE)'
mail.fetch(email_id, fetch_parts)
```

**效果**：
- 每封只下载 < 1KB（头部）
- 50 封 = 50KB（vs 250MB）
- **速度提升 5000x** 🚀

---

### 🐌 问题 2: 每次重新建立连接

**现状**：
```python
# 每次调用
mail = conn_mgr.connect_imap()  # 新建 TCP + TLS 连接
mail.login(...)
mail.select(folder)
# ... 操作
mail.logout()  # 关闭连接
```

**影响**：
- 每次 list_emails 都要：TCP 握手 + TLS 握手 + IMAP 登录
- 延迟：~500ms-2s（取决于网络和服务器）

**解决方案**：
```python
# 使用连接池
from connection_pool import ConnectionPool

pool = ConnectionPool()
with pool.get_connection(account_id) as mail:
    # 复用已有连接
    mail.select(folder)
    # ... 操作
# 连接返回池中，不关闭
```

**效果**：
- 首次：~1s（建立连接）
- 后续：~50ms（复用连接）
- **速度提升 20x** 🚀

---

### 🐌 问题 3: 未使用同步数据库

**现状**：
- `email_sync.db` 有完整的邮件缓存
- 但 `list_emails`/`search_emails` 仍然实时查询 IMAP
- 同步数据库只有 n8n 在用

**解决方案**：
```python
def list_emails(limit=50, use_cache=True, ...):
    if use_cache and sync_enabled():
        # 从 SQLite 读取（毫秒级）
        return read_from_sync_db(limit, ...)
    else:
        # 实时 IMAP（秒级）
        return fetch_from_imap(limit, ...)
```

**效果**：
- 缓存命中：~10ms
- IMAP 查询：~5s
- **速度提升 500x** 🚀

---

## 优化实施计划

### Phase 1: 快速优化（轻量级，1-2小时）

#### 1.1 修改 `fetch_emails` - 只下载头部

**文件**: `src/legacy_operations.py`

**修改前**：
```python
mail.fetch(email_id, '(RFC822)')  # 完整邮件
```

**修改后**：
```python
# 只下载头部信息 + FLAGS + 大小
fetch_cmd = '(BODY.PEEK[HEADER.FIELDS (From To Subject Date Message-ID)] FLAGS RFC822.SIZE)'
result, data = mail.fetch(email_id, fetch_cmd)
```

**处理逻辑**：
```python
# data 格式: [(b'1 (FLAGS (...) BODY[...] {123}', b'header bytes'), ...]
header_bytes = data[0][1] if len(data[0]) >= 2 else data[1][1]
msg = email.message_from_bytes(header_bytes)

# 提取 FLAGS
flags_str = str(data[0][0])
is_unread = '\\Seen' not in flags_str

# 提取大小
size_match = re.search(r'RFC822\.SIZE (\d+)', flags_str)
size = int(size_match.group(1)) if size_match else 0
```

**影响范围**：
- ✅ `fetch_emails()` - 列表显示
- ❌ `get_email_detail()` - 仍下载完整邮件（正确行为）

---

#### 1.2 批量 UID FETCH

**当前**：
```python
for email_id in email_ids:
    mail.fetch(email_id, ...)  # 50 次网络往返
```

**优化后**：
```python
# 一次性获取多个
uid_range = f"{email_ids[0]}:{email_ids[-1]}"
result, data = mail.uid('FETCH', uid_range, fetch_cmd)
# 解析批量响应
```

**效果**：
- 网络往返：50 → 1
- **速度再提升 5-10x**

---

### Phase 2: 连接池集成（中等，2-3小时）

#### 2.1 修改 `get_connection_manager()`

**文件**: `src/legacy_operations.py`

**添加连接池**：
```python
from connection_pool import ConnectionPool

# 模块级别
_connection_pool = None

def get_connection_pool():
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool(
            max_connections_per_account=3,
            connection_timeout=60,
            idle_timeout=300
        )
    return _connection_pool

def fetch_emails(limit=50, ...):
    pool = get_connection_pool()
    
    with pool.get_connection(account_id) as mail:
        # 使用连接池管理的连接
        mail.select(folder)
        # ... 操作
    # 连接自动返回池中
```

**修改范围**：
- `fetch_emails`
- `get_email_detail`
- `mark_email_read`
- `delete_email`
- 所有 IMAP 操作

---

### Phase 3: 同步数据库集成（重量级，4-6小时）

#### 3.1 添加缓存读取路径

**新文件**: `src/operations/cached_operations.py`

```python
import sqlite3
from datetime import datetime, timedelta

class CachedEmailOperations:
    def __init__(self, db_path='email_sync.db'):
        self.db_path = db_path
    
    def list_emails_cached(self, limit=50, unread_only=False, 
                          folder='INBOX', account_id=None,
                          max_age_minutes=5):
        """从缓存读取邮件列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查缓存新鲜度
        cursor.execute("""
            SELECT MAX(last_synced) 
            FROM emails 
            WHERE account_id = ? AND folder = ?
        """, (account_id, folder))
        
        last_sync = cursor.fetchone()[0]
        if not last_sync or \
           datetime.now() - datetime.fromisoformat(last_sync) > timedelta(minutes=max_age_minutes):
            # 缓存过期，返回 None 触发实时查询
            conn.close()
            return None
        
        # 从缓存读取
        query = """
            SELECT uid, from_addr, subject, date, flags, message_id
            FROM emails
            WHERE account_id = ? AND folder = ?
        """
        if unread_only:
            query += " AND flags NOT LIKE '%\\Seen%'"
        
        query += " ORDER BY date DESC LIMIT ?"
        
        cursor.execute(query, (account_id, folder, limit))
        rows = cursor.fetchall()
        
        emails = []
        for row in rows:
            emails.append({
                'id': row[0],  # UID
                'from': row[1],
                'subject': row[2],
                'date': row[3],
                'unread': '\\Seen' not in row[4],
                'message_id': row[5],
                'account_id': account_id
            })
        
        conn.close()
        return emails
```

#### 3.2 修改 `fetch_emails` 支持缓存

```python
def fetch_emails(limit=50, unread_only=False, folder="INBOX", 
                 account_id=None, use_cache=True):
    """
    Fetch emails (with optional caching)
    
    Args:
        use_cache: If True, try to read from sync database first
    """
    # 尝试从缓存读取
    if use_cache:
        cached_ops = CachedEmailOperations()
        cached_result = cached_ops.list_emails_cached(
            limit, unread_only, folder, account_id,
            max_age_minutes=5  # 5分钟缓存
        )
        
        if cached_result is not None:
            logger.debug(f"Returning cached emails for {account_id}")
            return {
                "emails": cached_result,
                "from_cache": True,
                "account_id": account_id
            }
    
    # 缓存未命中或禁用，走实时 IMAP
    logger.debug(f"Fetching live emails for {account_id}")
    # ... 原有 IMAP 逻辑
```

---

#### 3.3 初始化同步服务

**确保后台同步运行**：

```bash
# 初始化同步
python scripts/init_sync.py

# 启动调度器（常驻）
python -m src.operations.sync_scheduler &

# 或使用 systemd (推荐)
sudo systemctl enable mcp-email-sync
sudo systemctl start mcp-email-sync
```

**验证同步数据**：
```bash
# 检查数据库
sqlite3 email_sync.db "SELECT COUNT(*) FROM emails;"

# 检查最近同步时间
sqlite3 email_sync.db "SELECT account_id, MAX(last_synced) FROM emails GROUP BY account_id;"
```

---

### Phase 4: 超大邮件优化（可选，1-2小时）

#### 4.1 正文截断

```python
MAX_BODY_PREVIEW = 50 * 1024  # 50KB

def get_email_detail(email_id, ...):
    # ... 获取邮件
    
    body = extract_body(msg)
    
    # 截断过长正文
    if len(body) > MAX_BODY_PREVIEW:
        body = body[:MAX_BODY_PREVIEW]
        body_truncated = True
    else:
        body_truncated = False
    
    return {
        "body": body,
        "body_truncated": body_truncated,
        "body_size": len(body),
        ...
    }
```

#### 4.2 附件懒加载

```python
# 列表只返回附件元数据
attachments = [{
    "filename": part.get_filename(),
    "size": len(part.get_payload(decode=False)),
    "content_type": part.get_content_type(),
    "download_url": f"/api/attachment/{email_id}/{idx}"  # 按需下载
} for idx, part in enumerate(msg.walk()) if part.get_filename()]
```

---

## 性能对比

### 优化前

| 操作 | 耗时 | 网络流量 | 瓶颈 |
|------|------|----------|------|
| list_emails (50封) | 30-60s | 50-250MB | 下载完整邮件 |
| 每次操作 | +1-2s | - | 重新建连接 |
| search_emails | 20-40s | 30-150MB | 同上 |

**总体体验**：😫 很慢

---

### Phase 1 优化后（只下载头部）

| 操作 | 耗时 | 网络流量 | 改善 |
|------|------|----------|------|
| list_emails (50封) | 3-5s | < 50KB | ✅ 10x faster |
| 每次操作 | +1-2s | - | 仍需连接 |
| search_emails | 2-4s | < 30KB | ✅ 10x faster |

**总体体验**：🙂 可用

---

### Phase 2 优化后（+ 连接池）

| 操作 | 耗时 | 网络流量 | 改善 |
|------|------|----------|------|
| list_emails (首次) | 3-5s | < 50KB | 同上 |
| list_emails (后续) | 0.5-1s | < 50KB | ✅ 50x faster |
| search_emails | 0.5-1s | < 30KB | ✅ 50x faster |

**总体体验**：😊 快速

---

### Phase 3 优化后（+ 同步缓存）

| 操作 | 耗时 | 网络流量 | 改善 |
|------|------|----------|------|
| list_emails (缓存命中) | 10-50ms | 0 | ✅ 500x faster |
| list_emails (缓存未命中) | 0.5-1s | < 50KB | 回退到 Phase 2 |
| search_emails (缓存) | 5-20ms | 0 | ✅ 1000x faster |

**总体体验**：🤩 极快

---

## 实施建议

### 推荐顺序

1. **立即实施**：Phase 1（只下载头部）
   - 影响最大
   - 风险最小
   - 工作量最小

2. **短期实施**：Phase 2（连接池）
   - 需要测试连接稳定性
   - 改动范围中等

3. **长期实施**：Phase 3（同步缓存）
   - 需要保证同步服务稳定运行
   - 需要处理缓存一致性
   - 最大性能提升

4. **按需实施**：Phase 4（超大邮件）
   - 针对特定场景
   - 可选优化

---

## 风险评估

### Phase 1 风险：低 ✅

- **兼容性**：IMAP 标准支持
- **测试范围**：list_emails
- **回滚**：简单（恢复 RFC822）

### Phase 2 风险：中 ⚠️

- **连接泄漏**：需要严格测试 cleanup
- **并发问题**：多个请求共用连接池
- **服务器限制**：某些 IMAP 服务器限制并发连接数

**缓解措施**：
- 限制连接池大小（每账户 2-3 个）
- 实现连接健康检查
- 添加连接超时和重试

### Phase 3 风险：高 ⚠️⚠️

- **缓存过期**：用户看到旧数据
- **同步失败**：数据库未更新
- **一致性**：IMAP 和缓存不一致

**缓解措施**：
- 短缓存TTL（5分钟）
- 提供"刷新"按钮强制实时查询
- 监控同步健康状态
- 缓存未命中时回退到实时查询

---

## 监控指标

### 添加性能日志

```python
import time

def fetch_emails(...):
    start_time = time.time()
    cache_hit = False
    
    # ... 操作
    
    elapsed = time.time() - start_time
    logger.info(f"fetch_emails: {elapsed:.2f}s, cache_hit={cache_hit}, count={len(emails)}")
```

### 监控面板

建议跟踪：
- 平均响应时间
- 缓存命中率
- IMAP 连接数
- 网络流量
- 同步延迟

---

## 下一步行动

### 立即开始（Phase 1）

```bash
# 1. 备份当前代码
git checkout -b feature/performance-optimization

# 2. 修改 fetch_emails
# 编辑 src/legacy_operations.py

# 3. 测试
python test_account_id_fix.py

# 4. 性能测试
time python -c "from src.legacy_operations import fetch_emails; fetch_emails(50)"

# 5. 提交
git add src/legacy_operations.py
git commit -m "perf: optimize list_emails to fetch headers only (Phase 1)"
```

### 准备 Phase 2

```bash
# 检查连接池实现
ls src/connection_pool.py

# 测试连接池
python -c "from src.connection_pool import ConnectionPool; pool = ConnectionPool(); print('OK')"
```

### 准备 Phase 3

```bash
# 检查同步数据库
sqlite3 email_sync.db "SELECT COUNT(*) FROM emails;"

# 如果为空，初始化同步
python scripts/init_sync.py

# 启动后台同步
python -m src.operations.sync_scheduler &
```

---

准备好开始了吗？我可以帮你实施 Phase 1！

