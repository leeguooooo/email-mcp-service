# 快速测试指南

## 方法 1: 自动化测试脚本 (推荐)

```bash
python test_account_id_fix.py
```

**预期输出**：
```
🎉 所有测试通过！
```

---

## 方法 2: MCP Inspector 手动测试

### 启动服务

```bash
npx -y @modelcontextprotocol/inspector python -m src.main
```

### 测试场景 1: 列出邮件

在 Inspector 中调用：

```json
{
  "tool": "list_emails",
  "arguments": {
    "limit": 5,
    "account_id": "leeguoo_qq"
  }
}
```

**验证点**：
- ✅ 响应中有 `account_id: "leeguoo_qq"`
- ✅ 每封邮件都有 `account_id: "leeguoo_qq"`
- ❌ 不应该是 `"leeguoo@qq.com"`

### 测试场景 2: 获取邮件详情

从场景 1 复制一个邮件的 `id` 和 `account_id`：

```json
{
  "tool": "get_email_detail",
  "arguments": {
    "email_id": "1186",          // 从 list_emails 复制
    "account_id": "leeguoo_qq"   // 从 list_emails 复制
  }
}
```

**验证点**：
- ✅ 成功返回邮件内容（不报错 "Email not found"）
- ✅ 响应中 `account_id: "leeguoo_qq"`
- ✅ 主题和内容正确

### 测试场景 3: 搜索邮件

```json
{
  "tool": "search_emails",
  "arguments": {
    "query": "招聘",
    "account_id": "env_163"
  }
}
```

**验证点**：
- ✅ 每封邮件都有 `account_id: "env_163"`
- ✅ 可以用返回的 `account_id` 获取详情

---

## 方法 3: Python REPL 测试

```bash
python3
```

```python
import sys
sys.path.insert(0, 'src')
from src.legacy_operations import fetch_emails, get_email_detail

# 测试 1: 列出邮件
result = fetch_emails(limit=2, account_id="leeguoo_qq")
print("列表级 account_id:", result.get('account_id'))
print("邮件级 account_id:", result['emails'][0].get('account_id'))

# 测试 2: 获取详情
email_id = result['emails'][0]['id']
account_id = result['emails'][0]['account_id']
detail = get_email_detail(email_id, account_id=account_id)
print("详情 account_id:", detail.get('account_id'))
print("主题:", detail.get('subject'))
```

**预期输出**：
```
列表级 account_id: leeguoo_qq
邮件级 account_id: leeguoo_qq
详情 account_id: leeguoo_qq
主题: 【去哪儿网】2025-10-26 (大连)...
```

---

## 方法 4: 检查日志

开启 DEBUG 日志：

```bash
export LOG_LEVEL=DEBUG
python -m src.main
```

查找日志中的：
```
DEBUG - ConnectionManager initialized with account_id: leeguoo_qq
DEBUG - Returning account_id: leeguoo_qq
```

---

## 成功标准 ✅

- ✅ 所有 API 返回的 `account_id` 是账户键名（如 `"leeguoo_qq"`）
- ✅ 不是邮箱地址（不是 `"leeguoo@qq.com"`）
- ✅ 使用返回的 `account_id` 能成功获取邮件详情
- ✅ 没有 "Email not found" 错误

---

## 故障排查

### 问题: 仍然返回邮箱地址

```bash
# 1. 清除 Python 缓存
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} +

# 2. 重新运行测试
python test_account_id_fix.py
```

### 问题: account_id 为 None

检查 accounts.json 中是否有 `id` 字段：

```json
{
  "accounts": {
    "leeguoo_qq": {           // ← 这个键名会自动成为 id
      "email": "leeguoo@qq.com",
      ...
    }
  }
}
```

如果使用环境变量配置，可能需要修改代码添加自动生成 ID。

---

需要更详细的测试说明，请查看 `TESTING_GUIDE.md`。


