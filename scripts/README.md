# Scripts - 集成示例与参考实现

> **⚠️ 重要说明**: 这些脚本是**示例实现**，展示如何组合 MCP 原子操作来实现高级功能。它们**不是 MCP 核心能力**，而是可选的参考代码和集成工具。

## 📋 目录

- [设计定位](#设计定位)
- [示例脚本](#示例脚本)
- [使用方式](#使用方式)
- [自定义扩展](#自定义扩展)

## 🎯 设计定位

### MCP 核心 vs 示例脚本

| 类型 | 职责 | 位置 |
|------|------|------|
| **MCP 核心** | 提供原子级邮件操作（28个工具） | `src/` |
| **示例脚本** | 展示如何组合操作实现业务逻辑 | `scripts/` (本目录) |

### 为什么要分离？

1. **保持 MCP 的纯粹性**: MCP 只做数据访问，不做业务决策
2. **灵活性**: 不同的 AI 可能有不同的整合需求
3. **可定制**: 用户可以根据自己的需求修改示例脚本
4. **职责清晰**: 翻译、分类、摘要等能力属于上层 AI

## 📁 示例脚本

### 1. `inbox_organizer.py` - 收件箱整理示例

**功能**: 组合多个 MCP 工具，分析邮件并给出整理建议

**使用的 MCP 工具**:
- `list_emails` - 获取邮件列表
- `get_email_detail` - 获取邮件详情
- 规则分类邮件

**运行方式**:
```bash
# CLI 使用
uv run python scripts/inbox_organizer.py --limit 15 --text

# 返回 JSON
uv run python scripts/inbox_organizer.py --limit 20

# 指定账号
uv run python scripts/inbox_organizer.py --account-id user@example.com
```

**返回数据结构**:
```json
{
  "success": true,
  "actions": {
    "delete_spam": [...],
    "delete_marketing": [...],
    "mark_as_read": [...],
    "needs_attention": [...]
  },
  "important_summaries": [...],
  "stats": {...}
}
```

**定位**: 这是一个**工作流示例**，展示如何：
- 批量获取邮件
- 使用 AI 进行分类
- 生成结构化建议
- 提供中文摘要（可选）

### 2. `email_translator.py` - 翻译示例

**功能**: 调用 OpenAI API 翻译邮件内容并生成摘要

**特性**:
- 自动检测语言
- 翻译成中文
- 生成简短摘要

**运行方式**:
```bash
# 从标准输入读取邮件列表
echo '[{"id":"123","subject":"Hello","body":"..."}]' | python scripts/email_translator.py

# 或作为 Python 模块调用
from scripts.email_translator import EmailTranslator
translator = EmailTranslator()
result = translator.translate_and_summarize(emails)
```

**定位**: 这是**第三方 API 集成示例**，展示如何：
- 调用 OpenAI Translation API
- 批量处理邮件
- 返回多语言支持

### 3. `email_monitor_api.py` - HTTP API 包装

**功能**: 将 MCP 工具和示例脚本暴露为 HTTP API

**端点**:
- `POST /api/check-emails` - 检查并返回重要邮件
- `POST /api/organize-inbox` - 调用 inbox_organizer
- `POST /api/translate-unread` - 翻译未读邮件
- `POST /api/mark-read` - 批量标记已读

**运行方式**:
```bash
# 设置 API Key
export API_SECRET_KEY="your-secret-key"

# 启动服务
python scripts/email_monitor_api.py
# 或
uvicorn scripts.email_monitor_api:app --host 0.0.0.0 --port 18888
```

**调用示例**:
```bash
curl -X POST "http://localhost:18888/api/organize-inbox?limit=15" \
  -H "X-API-Key: your-secret-key"
```

**定位**: 这是**可选部署组件**，用于：
- 外部自动化平台集成
- 不支持 MCP 协议的系统
- HTTP-based AI agents

### 4. `email_monitor.py` - 监控示例

**功能**: 定期检查邮件并发送通知

**运行方式**:
```bash
python scripts/email_monitor.py
```

**配置**: `data/email_monitor_config.json`

**定位**: 这是**自动化示例**，展示如何：
- 定期轮询邮件
- 发送飞书/Lark 通知

### 5. `daily_email_digest.py` - 每日汇总调度

**功能**: 获取昨天邮件并生成摘要，支持 Lark/Telegram 通知

**运行方式**:
```bash
# 单次运行
python scripts/daily_email_digest.py run

# 常驻调度
python scripts/daily_email_digest.py daemon
```

**配置**: `data/daily_digest_config.json`

**定位**: 这是**本地定时示例**，展示如何：
- 每日汇总邮件
- 使用 AI 分类与摘要

## 🚀 使用方式

### 直接使用（快速体验）

```bash
# 1. 整理收件箱
uv run python scripts/inbox_organizer.py --text

# 2. 启动 HTTP API（可选）
export API_SECRET_KEY="your-key"
python scripts/email_monitor_api.py
```

### 作为参考实现（推荐）

1. **阅读源码**: 了解脚本如何组合 MCP 工具
2. **复制修改**: 复制到 `examples/` 并根据需求定制
3. **集成到 AI**: 在你的 AI Agent 中实现类似逻辑

### 在 AI Agent 中复现

```python
# 不是直接调用 inbox_organizer.py
# 而是在 AI 中复现其逻辑

# 1. 获取邮件
emails = mcp_client.call("list_emails", {"limit": 20})

# 2. 获取邮件头（高效）
headers = [
    mcp_client.call("get_email_headers", {"email_id": e["id"]})
    for e in emails[:10]
]

# 3. AI 自己分类（使用自己的模型）
spam_ids = my_ai_model.classify_spam(headers)
important_ids = my_ai_model.find_important(headers)

# 4. 执行操作
mcp_client.call("delete_emails", {"email_ids": spam_ids})

# 5. 生成摘要（使用自己的摘要模型）
summary = my_ai_model.summarize(important_ids)
```

## 🔧 自定义扩展

### 创建自己的整合脚本

```bash
# 1. 复制示例到 examples/
cp scripts/inbox_organizer.py examples/my_organizer.py

# 2. 修改逻辑
# - 调整分类规则
# - 使用不同的 AI 模型
# - 添加自定义输出格式

# 3. 运行
python examples/my_organizer.py
```

### 常见定制场景

#### 场景 1: 集成其他通知服务

修改 `email_monitor.py`:
```python
# 原：飞书通知
from notification_service import send_lark_notification

# 改：Slack 通知
import requests
def send_slack(message):
    requests.post(SLACK_WEBHOOK_URL, json={"text": message})
```

## 📊 性能考虑

### 批量操作优化

示例脚本默认使用串行操作。如需并行处理：

```python
# inbox_organizer.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def fetch_headers_parallel(email_ids):
    with ThreadPoolExecutor(max_workers=5) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                executor,
                lambda id: mcp.call("get_email_headers", {"email_id": id}),
                email_id
            )
            for email_id in email_ids
        ]
        return await asyncio.gather(*tasks)
```

### 缓存策略

```python
# 缓存分类结果
import json
from pathlib import Path

cache_file = Path("data/classification_cache.json")

def classify_with_cache(email_id, content):
    cache = json.load(open(cache_file)) if cache_file.exists() else {}
    
    if email_id in cache:
        return cache[email_id]
    
    result = classify(content)
    cache[email_id] = result
    json.dump(cache, open(cache_file, 'w'))
    
    return result
```

## 🧪 测试

### 单元测试

```bash
# 测试整理器
pytest tests/test_inbox_organizer.py
```

### 集成测试

```bash
# 完整工作流测试
python scripts/test_workflow.py
```

## 📚 相关文档

- [MCP 设计原则](../docs/guides/MCP_DESIGN_PRINCIPLES.md) - 理解 MCP 定位
- [HTTP API 快速开始](../docs/guides/HTTP_API_QUICK_START.md) - 部署 HTTP API
- [翻译工作流总结](../docs/guides/TRANSLATION_WORKFLOW_SUMMARY.md) - 翻译示例说明

## 💡 最佳实践

### ✅ 推荐

1. **理解再使用**: 先理解示例逻辑，再根据需求定制
2. **保持简单**: 每个脚本只做一件事
3. **可配置**: 通过配置文件控制行为，而非硬编码
4. **错误处理**: 示例脚本包含完善的错误处理，可直接参考

### ❌ 避免

1. **直接修改**: 不要直接修改 scripts/ 下的文件（会影响升级）
2. **过度耦合**: 不要在示例脚本中混入过多业务逻辑
3. **忽略文档**: 示例代码包含详细注释，阅读注释了解设计意图

## 🔄 升级注意

当升级 MCP Email Service 时：

1. **scripts/ 可能更新**: 示例脚本会随 MCP 工具改进
2. **检查 CHANGELOG**: 查看示例脚本的变更
3. **重新评估定制**: 如果你有自定义版本，评估是否需要合并新特性

## 🤝 贡献

如果你有好的整合示例，欢迎贡献：

1. 在 `examples/` 创建你的实现
2. 添加完整的文档和注释
3. 提交 PR

---

**记住**: 这些脚本是**教学工具**和**集成参考**，真正的强大之处在于你的 AI 如何组合使用底层的 MCP 原子操作！ 🚀
