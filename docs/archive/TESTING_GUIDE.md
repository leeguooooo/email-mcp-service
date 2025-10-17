# 测试指南 - UID 和 Account ID 修复验证

## 测试目标

验证两个关键修复：
1. ✅ **Account ID 修复**：返回真实的账户 ID（如 `leeguoo_qq`）而不是邮箱地址
2. ✅ **UID 支持**：所有操作都支持 UID 和序列号，自动回退

## 测试环境准备

### 1. 检查账户配置

```bash
cat accounts.json
```

应该看到类似：
```json
{
  "accounts": {
    "env_163": {
      "email": "leeguoo@163.com",
      ...
    },
    "leeguoo_qq": {
      "email": "leeguoo@qq.com",
      ...
    }
  }
}
```

**关键点**：账户 ID 是 `env_163` 和 `leeguoo_qq`，不是邮箱地址。

### 2. 启动 MCP 服务

```bash
# 如果使用 npx
npx -y @modelcontextprotocol/inspector python -m src.main

# 或者直接运行
python -m src.main
```

## 测试场景

### 场景 1：验证 list_emails 返回正确的 account_id

**测试步骤**：

```javascript
// 1. 列出邮件（使用特定账户）
{
  "tool": "list_emails",
  "arguments": {
    "limit": 5,
    "account_id": "leeguoo_qq"  // 使用真实的账户 ID
  }
}
```

**预期结果**：
```json
{
  "emails": [
    {
      "id": "1",
      "subject": "测试邮件",
      "account": "leeguoo@qq.com",
      "account_id": "leeguoo_qq"  // ✅ 应该是账户 ID，不是邮箱
    }
  ],
  "account_id": "leeguoo_qq"  // ✅ 列表级别也应该有
}
```

**验证点**：
- ✅ `account_id` 字段存在
- ✅ `account_id` = `"leeguoo_qq"` （不是 `"leeguoo@qq.com"`）

---

### 场景 2：验证 search_emails 返回正确的 account_id

**测试步骤**：

```javascript
// 2. 搜索邮件
{
  "tool": "search_emails",
  "arguments": {
    "query": "招聘",
    "account_id": "env_163"
  }
}
```

**预期结果**：
```json
{
  "success": true,
  "emails": [
    {
      "id": "1186",  // 这是 UID
      "subject": "地上铁招聘",
      "account": "leeguoo@163.com",
      "account_id": "env_163"  // ✅ 真实账户 ID
    }
  ],
  "account_id": "env_163"
}
```

---

### 场景 3：验证 get_email_detail 使用 account_id 能正确路由

**测试步骤**：

```javascript
// 3. 从搜索结果获取详情（使用返回的 account_id）
// 假设搜索返回了 {"id": "1186", "account_id": "env_163"}

{
  "tool": "get_email_detail",
  "arguments": {
    "email_id": "1186",  // UID
    "account_id": "env_163"  // 使用返回的 account_id
  }
}
```

**预期结果**：
```json
{
  "id": "1186",
  "uid": "1186",  // ✅ 使用了 UID
  "subject": "地上铁招聘",
  "body": "...",
  "account": "leeguoo@163.com",
  "account_id": "env_163"  // ✅ 返回真实 ID
}
```

**关键验证**：
- ✅ 能成功获取邮件（不报错 "Email not found"）
- ✅ 返回的是正确的邮件内容
- ✅ `account_id` 是 `"env_163"`

---

### 场景 4：验证 UID 回退机制

**测试 4A：使用 UID（来自 search）**

```javascript
// 先搜索
{
  "tool": "search_emails",
  "arguments": {
    "query": "test",
    "limit": 1
  }
}
// 假设返回 {"id": "1186", "account_id": "env_163"}

// 然后标记为已读
{
  "tool": "mark_email_read",
  "arguments": {
    "email_id": "1186",  // UID
    "account_id": "env_163"
  }
}
```

**预期**：
- ✅ 成功标记
- ✅ 日志显示 "Successfully used UID"（如果开启 DEBUG）

**测试 4B：使用序列号（来自 list）**

```javascript
// 先列表
{
  "tool": "list_emails",
  "arguments": {
    "limit": 1,
    "account_id": "env_163"
  }
}
// 假设返回 {"id": "1", "account_id": "env_163"}

// 然后标记为已读
{
  "tool": "mark_email_read",
  "arguments": {
    "email_id": "1",  // 序列号
    "account_id": "env_163"
  }
}
```

**预期**：
- ✅ 成功标记（回退到序列号）
- ✅ 日志可能显示 "UID store failed, trying sequence number"

---

### 场景 5：验证批量操作

```javascript
// 5. 批量标记为已读
{
  "tool": "batch_mark_read",
  "arguments": {
    "email_ids": ["1186", "1187", "1188"],  // UIDs from search
    "account_id": "env_163"
  }
}
```

**预期结果**：
```json
{
  "success": true,
  "message": "Marked 3/3 emails as read",
  "account": "leeguoo@163.com",
  "account_id": "env_163",  // ✅ 返回真实 ID
  "failed_ids": []  // ✅ 应该为空（全部成功）
}
```

---

## 错误场景测试

### 测试错误的 account_id

```javascript
{
  "tool": "get_email_detail",
  "arguments": {
    "email_id": "123",
    "account_id": "nonexistent_account"
  }
}
```

**预期**：
- ❌ 返回错误："No email account configured"

### 测试错误的邮箱地址作为 account_id（验证修复前的问题）

```javascript
{
  "tool": "get_email_detail",
  "arguments": {
    "email_id": "123",
    "account_id": "leeguoo@qq.com"  // ❌ 应该用 "leeguoo_qq"
  }
}
```

**修复前**：会回退到默认账户，取到错误的邮件
**修复后**：应该返回错误或回退到默认账户（取决于实现）

---

## 使用 Python 脚本测试

创建测试脚本 `test_account_id_fix.py`：

```python
#!/usr/bin/env python3
"""测试 account_id 修复"""
import sys
sys.path.insert(0, 'src')

from legacy_operations import (
    fetch_emails, 
    get_email_detail, 
    mark_email_read
)
from operations.search_operations import EmailSearchOperations
from account_manager import AccountManager
import json

def test_list_emails():
    """测试 list_emails 返回正确的 account_id"""
    print("=" * 60)
    print("测试 1: list_emails 返回 account_id")
    print("=" * 60)
    
    result = fetch_emails(limit=2, account_id="leeguoo_qq")
    
    if 'error' in result:
        print(f"❌ 错误: {result['error']}")
        return False
    
    print(f"✅ 列表级 account_id: {result.get('account_id')}")
    
    if result.get('emails'):
        first_email = result['emails'][0]
        print(f"✅ 邮件级 account_id: {first_email.get('account_id')}")
        print(f"   邮件 ID: {first_email.get('id')}")
        print(f"   账户邮箱: {first_email.get('account')}")
        
        # 验证
        if first_email.get('account_id') == 'leeguoo_qq':
            print("✅ PASS: account_id 正确")
            return True, first_email.get('id')
        else:
            print(f"❌ FAIL: account_id 应该是 'leeguoo_qq'，实际是 '{first_email.get('account_id')}'")
            return False, None
    
    return False, None

def test_get_email_detail(email_id, account_id):
    """测试 get_email_detail 能正确路由"""
    print("\n" + "=" * 60)
    print(f"测试 2: get_email_detail 路由到正确账户")
    print(f"  email_id: {email_id}")
    print(f"  account_id: {account_id}")
    print("=" * 60)
    
    result = get_email_detail(email_id, account_id=account_id)
    
    if 'error' in result:
        print(f"❌ 错误: {result['error']}")
        return False
    
    print(f"✅ 成功获取邮件")
    print(f"   主题: {result.get('subject', 'N/A')[:50]}")
    print(f"   account_id: {result.get('account_id')}")
    print(f"   uid: {result.get('uid')}")
    
    if result.get('account_id') == account_id:
        print("✅ PASS: account_id 正确")
        return True
    else:
        print(f"❌ FAIL: account_id 不匹配")
        return False

def test_search_emails():
    """测试搜索返回正确的 account_id"""
    print("\n" + "=" * 60)
    print("测试 3: search_emails 返回 account_id")
    print("=" * 60)
    
    account_mgr = AccountManager()
    account = account_mgr.get_account("env_163")
    
    if not account:
        print("❌ 找不到账户 env_163")
        return False, None
    
    from connection_manager import ConnectionManager
    conn_mgr = ConnectionManager(account)
    
    searcher = EmailSearchOperations(conn_mgr)
    result = searcher.search_emails(
        query="",  # 搜索所有
        limit=2,
        account_id="env_163"
    )
    
    if not result.get('success'):
        print(f"❌ 搜索失败: {result}")
        return False, None
    
    print(f"✅ 搜索到 {len(result.get('emails', []))} 封邮件")
    
    if result.get('emails'):
        first = result['emails'][0]
        print(f"   第一封邮件:")
        print(f"   - ID: {first.get('id')}")
        print(f"   - account_id: {first.get('account_id')}")
        
        if first.get('account_id') == 'env_163':
            print("✅ PASS: account_id 正确")
            return True, first.get('id')
        else:
            print(f"❌ FAIL: account_id 应该是 'env_163'")
            return False, None
    
    return False, None

if __name__ == '__main__':
    print("\n" + "🧪 " * 20)
    print("Account ID 修复测试")
    print("🧪 " * 20 + "\n")
    
    # 测试 1: list_emails
    success1, email_id = test_list_emails()
    
    # 测试 2: get_email_detail（如果测试1成功）
    success2 = False
    if success1 and email_id:
        success2 = test_email_detail(email_id, "leeguoo_qq")
    
    # 测试 3: search_emails
    success3, search_id = test_search_emails()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"list_emails:        {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"get_email_detail:   {'✅ PASS' if success2 else '❌ FAIL'}")
    print(f"search_emails:      {'✅ PASS' if success3 else '❌ FAIL'}")
    
    if success1 and success2 and success3:
        print("\n🎉 所有测试通过！")
        sys.exit(0)
    else:
        print("\n❌ 部分测试失败")
        sys.exit(1)
```

运行测试：

```bash
python test_account_id_fix.py
```

---

## 快速验证命令

### 方法 1：使用 MCP Inspector

```bash
# 启动 inspector
npx -y @modelcontextprotocol/inspector python -m src.main

# 在 inspector 中调用工具，观察返回的 account_id
```

### 方法 2：使用 Python REPL

```python
python3
>>> import sys
>>> sys.path.insert(0, 'src')
>>> from legacy_operations import fetch_emails
>>> 
>>> # 测试
>>> result = fetch_emails(limit=1, account_id="leeguoo_qq")
>>> print(result.get('account_id'))  # 应该输出 "leeguoo_qq"
>>> 
>>> # 测试邮件级别
>>> if result.get('emails'):
...     print(result['emails'][0].get('account_id'))  # 也应该是 "leeguoo_qq"
```

### 方法 3：检查日志

开启 DEBUG 日志：

```bash
# 设置环境变量
export LOG_LEVEL=DEBUG

# 运行服务
python -m src.main
```

查找日志中的关键信息：
```
DEBUG - Successfully fetched email using UID 1186
DEBUG - UID store failed for 999, trying sequence number
```

---

## 预期的修复效果

### 修复前 ❌
```json
{
  "id": "1186",
  "account_id": "leeguoo@qq.com"  // ❌ 邮箱地址
}

// 再次调用时
get_email_detail("1186", account_id="leeguoo@qq.com")
// → AccountManager.get_account("leeguoo@qq.com") → None
// → 回退到默认账户 → 错误的邮件或找不到
```

### 修复后 ✅
```json
{
  "id": "1186",
  "account_id": "leeguoo_qq"  // ✅ 真实账户 ID
}

// 再次调用时
get_email_detail("1186", account_id="leeguoo_qq")
// → AccountManager.get_account("leeguoo_qq") → Success!
// → 正确的账户 → 正确的邮件
```

---

## 故障排查

### 问题：仍然返回邮箱地址

**检查**：
```bash
# 1. 确认代码已更新
grep "self.account_id" src/connection_manager.py

# 2. 确认没有缓存的 .pyc 文件
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -delete

# 3. 重启服务
```

### 问题：account_id 为 None

**原因**：环境变量账户没有 ID

**解决**：为环境变量账户添加到 accounts.json，或者修改回退逻辑：

```python
# 在 ConnectionManager.__init__ 中
self.account_id = account_config.get('id') or f"env_{self.email.split('@')[0]}"
```

---

## 成功标准

✅ 所有测试场景通过
✅ `account_id` 返回的是账户键名（如 `"leeguoo_qq"`）
✅ 使用返回的 `account_id` 能正确路由到对应账户
✅ UID 和序列号都能工作
✅ 没有 "Email not found" 错误（在正确使用时）

---

需要帮助创建测试脚本或运行特定测试吗？


