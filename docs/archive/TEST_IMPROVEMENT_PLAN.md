# 测试改进计划

## 🚨 当前问题分析

### 本次修复的关键 Bug（未被测试捕获）

| Bug | 严重性 | 影响 | 为什么测试没发现 |
|-----|--------|------|------------------|
| 1. UID vs 序列号混乱 | 🔴 Critical | 删除/标记错误的邮件 | 没有 mock IMAP 响应测试 |
| 2. `account_id` 路由错误 | 🔴 Critical | 跨账户数据泄漏 | 缺少集成测试 |
| 3. 连接泄漏 | 🔴 Critical | 资源耗尽 | 没有连接管理测试 |
| 4. FLAGS 解析错误 | 🟡 High | 功能失败 | 没有 IMAP 协议测试 |
| 5. 缓存空列表误判 | 🟡 High | 性能下降 100-200x | 没有缓存逻辑测试 |
| 6. 多账户缓存逻辑错误 | 🔴 Critical | 数据不完整 | 没有多账户场景测试 |
| 7. 文件夹名称未引用 | 🟡 High | IMAP BAD 请求 | 没有协议兼容性测试 |

### 现有测试覆盖情况

#### ✅ 已覆盖（约 30%）
- Schema 定义验证
- 参数类型检查
- AccountManager 基础功能
- 并行操作线程安全（部分）

#### ❌ 未覆盖（约 70%）
- **IMAP 操作逻辑**：UID 处理、FLAGS 解析、连接管理
- **缓存系统**：缓存命中/失效判断、数据一致性
- **多账户隔离**：跨账户场景、账户路由
- **协议兼容性**：文件夹名称编码、特殊字符处理
- **错误处理**：边界条件、None 值、空列表
- **性能优化**：header-only fetch、body truncation

---

## 📋 测试改进方案

### 阶段 1：核心 IMAP 操作测试（优先级：🔴 最高）

#### 1.1 创建 `test_imap_operations.py`

```python
"""
测试核心 IMAP 操作逻辑（使用 Mock）
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
from src.legacy_operations import (
    fetch_emails, get_email_detail, mark_email_read,
    delete_email, move_email_to_trash, batch_mark_read
)

class TestUIDHandling(unittest.TestCase):
    """测试 UID vs 序列号处理"""
    
    def test_fetch_emails_returns_uid(self):
        """测试 fetch_emails 返回稳定的 UID 而非序列号"""
        # Mock IMAP 响应
        # ... 实现
    
    def test_get_email_detail_uid_fallback(self):
        """测试 get_email_detail UID 失败时回退到序列号"""
        # ... 实现
    
    def test_mark_email_read_uses_uid_first(self):
        """测试 mark_email_read 优先使用 UID"""
        # ... 实现

class TestFLAGSParsing(unittest.TestCase):
    """测试 FLAGS 解析"""
    
    def test_parse_flags_from_tuple_response(self):
        """测试从 IMAP tuple 响应解析 FLAGS"""
        # Mock: (b'1 (UID 123 FLAGS (\\Seen))', b'')
        # ... 实现
    
    def test_parse_flags_with_multiple_flags(self):
        """测试解析多个 FLAGS"""
        # Mock: (b'1 (FLAGS (\\Seen \\Flagged \\Answered))', b'')
        # ... 实现

class TestConnectionManagement(unittest.TestCase):
    """测试连接管理（防止泄漏）"""
    
    def test_fetch_emails_always_closes_connection(self):
        """测试 fetch_emails 总是关闭连接（即使异常）"""
        # ... 实现
    
    def test_connection_closed_on_error(self):
        """测试出错时连接仍被关闭"""
        # ... 实现
```

#### 1.2 创建 `test_folder_normalization.py`

```python
"""
测试文件夹名称规范化
"""
import unittest
from src.legacy_operations import _normalize_folder_name

class TestFolderNormalization(unittest.TestCase):
    """测试文件夹名称规范化"""
    
    def test_inbox_unchanged(self):
        """测试 INBOX 不变"""
        self.assertEqual(_normalize_folder_name('INBOX'), 'INBOX')
    
    def test_spaces_quoted(self):
        """测试包含空格的文件夹名称被引用"""
        result = _normalize_folder_name('Deleted Messages')
        self.assertEqual(result, '"Deleted Messages"')
    
    def test_utf7_encoding(self):
        """测试非 ASCII 字符使用 UTF-7 编码"""
        result = _normalize_folder_name('草稿箱')
        # 验证结果是有效的 IMAP UTF-7
        self.assertIsInstance(result, (str, bytes))
    
    def test_empty_defaults_to_inbox(self):
        """测试空字符串默认为 INBOX"""
        self.assertEqual(_normalize_folder_name(''), 'INBOX')
        self.assertEqual(_normalize_folder_name(None), 'INBOX')
```

---

### 阶段 2：缓存系统测试（优先级：🟡 高）

#### 2.1 创建 `test_cache_logic.py`

```python
"""
测试缓存逻辑
"""
import unittest
from unittest.mock import Mock, patch
from src.legacy_operations import fetch_emails
from src.operations.cached_operations import CachedEmailOperations

class TestCacheHitLogic(unittest.TestCase):
    """测试缓存命中逻辑"""
    
    def test_cache_returns_empty_list_still_valid(self):
        """关键测试：缓存返回空列表时仍被视为有效"""
        # Mock: cache.list_emails_cached 返回 {"emails": [], "from_cache": True}
        # 验证：不应回退到 IMAP
        # ... 实现
    
    def test_cache_returns_none_triggers_imap(self):
        """测试缓存返回 None 时触发 IMAP"""
        # ... 实现
    
    def test_cache_age_validation(self):
        """测试缓存年龄验证（< 15 分钟）"""
        # ... 实现

class TestMultiAccountCacheLogic(unittest.TestCase):
    """测试多账户缓存逻辑"""
    
    def test_cache_skipped_for_multi_account(self):
        """关键测试：多账户请求跳过缓存"""
        # Mock: account_id=None, use_cache=True
        # 验证：不调用 cache.list_emails_cached
        # ... 实现
    
    def test_cache_used_for_single_account(self):
        """测试单账户请求使用缓存"""
        # Mock: account_id='env_163', use_cache=True
        # 验证：调用 cache.list_emails_cached
        # ... 实现
```

---

### 阶段 3：多账户隔离测试（优先级：🔴 最高）

#### 3.1 扩展 `test_account_manager.py`

```python
class TestAccountIDRouting(unittest.TestCase):
    """测试 account_id 路由"""
    
    def test_fetch_emails_returns_canonical_account_id(self):
        """测试 fetch_emails 返回规范的 account_id（非 email）"""
        # 验证：返回 'env_163' 而非 'leeguoo@163.com'
        # ... 实现
    
    def test_search_emails_preserves_account_id(self):
        """测试 search_emails 保留正确的 account_id"""
        # ... 实现
    
    def test_get_email_detail_uses_canonical_account_id(self):
        """测试 get_email_detail 使用规范的 account_id"""
        # ... 实现
    
    def test_account_lookup_by_email_fallback(self):
        """测试通过 email 查找账户的回退逻辑"""
        # ... 实现
```

---

### 阶段 4：性能优化测试（优先级：🟢 中）

#### 4.1 创建 `test_performance_optimizations.py`

```python
"""
测试性能优化
"""
import unittest
from unittest.mock import Mock, patch

class TestHeaderOnlyFetch(unittest.TestCase):
    """测试仅获取头部"""
    
    def test_fetch_emails_uses_header_only(self):
        """测试 fetch_emails 仅获取头部（不获取 body）"""
        # Mock IMAP fetch
        # 验证：使用 BODY.PEEK[HEADER.FIELDS (...)]
        # ... 实现

class TestBodyTruncation(unittest.TestCase):
    """测试 body 截断"""
    
    def test_get_email_detail_truncates_large_body(self):
        """测试 get_email_detail 截断大 body（> 100KB）"""
        # ... 实现
    
    def test_html_to_text_conversion(self):
        """测试 HTML 转纯文本"""
        # ... 实现
```

---

## 🔧 实施步骤

### 第 1 步：修复当前测试环境
```bash
# 安装测试依赖
uv pip install pytest pytest-cov pytest-mock

# 验证现有测试可运行
uv run pytest tests/ -v
```

### 第 2 步：创建 Mock IMAP 响应库
创建 `tests/fixtures/imap_responses.py`：
```python
"""
常见 IMAP 响应的 Mock 数据
"""

# UID FETCH 响应
UID_FETCH_RESPONSE = (
    b'1 (UID 12345 FLAGS (\\Seen) RFC822.SIZE 2048)',
    b''
)

# FLAGS 解析测试数据
FLAGS_RESPONSES = {
    'single_flag': (b'1 (FLAGS (\\Seen))', b''),
    'multiple_flags': (b'1 (FLAGS (\\Seen \\Flagged))', b''),
    'with_uid': (b'1 (UID 123 FLAGS (\\Seen))', b''),
}

# 文件夹列表响应
FOLDER_LIST_RESPONSE = [
    b'(\\HasNoChildren) "/" "INBOX"',
    b'(\\HasNoChildren) "/" "Sent Items"',
    b'(\\HasNoChildren) "/" "Deleted Messages"',
]
```

### 第 3 步：逐步实现测试
按优先级顺序：
1. **Week 1**: 核心 IMAP 操作测试（阶段 1）
2. **Week 2**: 缓存系统测试（阶段 2）
3. **Week 3**: 多账户隔离测试（阶段 3）
4. **Week 4**: 性能优化测试（阶段 4）

### 第 4 步：集成到 CI/CD
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          uv run pytest tests/ --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## 📊 测试覆盖率目标

| 模块 | 当前覆盖率 | 目标覆盖率 |
|------|-----------|-----------|
| `legacy_operations.py` | ~10% | **80%** |
| `cached_operations.py` | 0% | **70%** |
| `account_manager.py` | ~60% | **90%** |
| `connection_manager.py` | 0% | **70%** |
| **整体** | **~30%** | **75%** |

---

## 🎯 成功标准

### 短期目标（1 个月内）
- ✅ 所有已修复的 Bug 都有对应的回归测试
- ✅ 核心 IMAP 操作测试覆盖率达到 70%
- ✅ CI/CD 集成完成

### 中期目标（3 个月内）
- ✅ 测试覆盖率达到 75%
- ✅ 每次 PR 必须包含测试
- ✅ 测试运行时间 < 30 秒

### 长期目标（6 个月内）
- ✅ 集成测试（真实 IMAP 服务器）
- ✅ 性能基准测试
- ✅ 模糊测试（fuzzing）

---

## 💡 测试最佳实践

### 1. 使用 AAA 模式
```python
def test_example(self):
    # Arrange（准备）
    mock_imap = Mock()
    mock_imap.fetch.return_value = ('OK', [MOCK_DATA])
    
    # Act（执行）
    result = fetch_emails(limit=10)
    
    # Assert（断言）
    self.assertEqual(len(result['emails']), 10)
    mock_imap.fetch.assert_called_once()
```

### 2. 使用有意义的测试名称
```python
# ❌ Bad
def test_fetch(self):
    ...

# ✅ Good
def test_fetch_emails_returns_uid_not_sequence_number(self):
    ...
```

### 3. 每个测试只测一件事
```python
# ❌ Bad: 测试多个场景
def test_everything(self):
    test_normal_case()
    test_error_case()
    test_edge_case()

# ✅ Good: 分开测试
def test_normal_case(self):
    ...

def test_error_case(self):
    ...

def test_edge_case(self):
    ...
```

### 4. 使用 pytest fixtures
```python
@pytest.fixture
def mock_imap_connection():
    """提供一个 mock IMAP 连接"""
    mock = Mock()
    mock.select.return_value = ('OK', [b'10'])
    return mock

def test_with_fixture(mock_imap_connection):
    # 使用 fixture
    result = fetch_emails(connection=mock_imap_connection)
    ...
```

---

## 🔍 建议的下一步

1. **立即行动**（本周）：
   - ✅ 修复现有测试的语法错误
   - ✅ 为本次修复的 7 个 Bug 编写回归测试
   - ✅ 设置测试覆盖率报告

2. **短期行动**（本月）：
   - 实现阶段 1 和阶段 3 的测试
   - 达到 50% 测试覆盖率
   - 集成 CI/CD

3. **中期行动**（3 个月内）：
   - 完成所有 4 个阶段的测试
   - 达到 75% 测试覆盖率
   - 建立测试文化（PR 必须包含测试）

---

**结论**：当前测试主要关注"定义正确性"而非"行为正确性"。需要大幅扩展测试覆盖，特别是核心 IMAP 操作、缓存逻辑、多账户隔离这三个关键领域。

