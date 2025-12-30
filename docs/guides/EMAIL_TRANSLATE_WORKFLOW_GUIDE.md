# 📧 邮件翻译总结工作流指南

## 🎯 功能说明

这个工作流实现了你的需求：

1. **定时获取未读邮件** - 每 10 分钟执行一次
2. **智能翻译** - 非中文邮件自动翻译成中文
3. **生成摘要** - 使用 OpenAI 生成中文摘要
4. **发送飞书通知** - 调用方根据返回内容推送
5. **标记已读** - 自动标记为已读

## 🔄 工作流程

```
定时触发 (每10分钟)
   ↓
调用 /api/translate-unread
   ├─ 获取未读邮件
   ├─ 检测语言
   ├─ 非中文 → OpenAI 翻译
   └─ 生成中文摘要
   ↓
检查是否有邮件？
   ├─ 有 → 发送飞书通知
   │       ↓
   │     标记已读
   │       ↓
   │     完成
   └─ 无 → 跳过
```

## 📝 API 端点

### 1. `/api/translate-unread` - 翻译未读邮件

**请求**:
```bash
POST /api/translate-unread
Headers:
  X-API-Key: your-api-key
```

**响应**:
```json
{
  "success": true,
  "message": "翻译总结完成",
  "count": 3,
  "summary": "📧 共 3 封未读邮件\n\n1. 欢迎使用...",
  "emails": [
    {
      "id": "123",
      "from": "test@example.com",
      "subject": "Welcome",
      "subject_zh": "欢迎",
      "summary_zh": "这是一封欢迎邮件...",
      "is_chinese": false
    }
  ],
  "email_ids": ["123", "456", "789"],
  "lark_message": {
    "msg_type": "text",
    "content": {
      "text": "📬 未读邮件摘要\n\n..."
    }
  }
}
```

### 2. `/api/mark-read` - 标记已读

**请求**:
```bash
POST /api/mark-read
Headers:
  X-API-Key: your-api-key
Content-Type: application/json

["email-id-1", "email-id-2", "email-id-3"]
```

**响应**:
```json
{
  "success": true,
  "message": "成功标记 3 封邮件为已读",
  "marked_count": 3,
  "email_ids": ["email-id-1", "email-id-2", "email-id-3"]
}
```

## 🚀 部署步骤

### 1. 设置环境变量

在 `.env` 文件中添加：

```bash
# OpenAI API Key (必需 - 用于翻译)
OPENAI_API_KEY=sk-your-openai-key

# API 安全
API_SECRET_KEY=$(openssl rand -hex 32)

# 飞书 Webhook（可选）
FEISHU_WEBHOOK=https://open.larksuite.com/open-apis/bot/v2/hook/xxx
```

### 2. 启动 API 服务

```bash
# 确保设置了环境变量
export OPENAI_API_KEY="sk-your-key"
export API_SECRET_KEY="your-secret"

# 启动服务
uv run uvicorn scripts.email_monitor_api:app --port 18888
```

### 3. 设置本地定时任务

```bash
# 每 10 分钟触发翻译（按需处理返回的 email_ids）
*/10 * * * * curl -X POST http://localhost:18888/api/translate-unread -H "X-API-Key: your-secret-key"
```

### 4. 测试

```bash
# 测试翻译 API
curl -X POST http://localhost:18888/api/translate-unread \
  -H "X-API-Key: your-secret-key"
```

## 📊 本地调度配置

### 定时频率

默认每 10 分钟运行一次，可修改 cron 表达式：

- `*/5 * * * *` - 每 5 分钟
- `*/15 * * * *` - 每 15 分钟
- `0 * * * *` - 每小时
- `0 9-18 * * *` - 工作时间（9-18点）每小时

### 邮件数量限制

在 API 中默认获取最多 20 封未读邮件。

如需修改，编辑 `scripts/email_monitor_api.py`:

```python
fetch_result = await asyncio.to_thread(
    svc.list_emails,
    limit=50,
    unread_only=True,
    folder="INBOX",
    account_id=None,
    use_cache=False
)
```

## 🎨 飞书消息格式

生成的飞书消息格式：

```
📬 未读邮件摘要

📧 共 3 封未读邮件

1. 欢迎使用我们的服务
   发件人: service@example.com
   摘要: 这是一封欢迎邮件，介绍了服务的主要功能...

2. 会议提醒
   发件人: calendar@company.com
   摘要: 明天下午2点有重要会议...

3. 账单通知
   发件人: billing@provider.com
   摘要: 您的本月账单已生成，金额为...
```

## 💰 成本估算

### OpenAI API 使用量

| 邮件数/次 | Tokens/次 | 成本/次 | 运行频率 | 月成本 |
|-----------|----------|---------|----------|--------|
| 5 封 | 1K-2K | $0.002-0.004 | 每10分钟 | $8-17 |
| 10 封 | 2K-4K | $0.004-0.008 | 每10分钟 | $17-34 |
| 20 封 | 4K-8K | $0.008-0.016 | 每10分钟 | $34-69 |

**优化建议**:
1. 调整运行频率为每 15-30 分钟
2. 限制邮件数量为 10 封
3. 只在工作时间运行

### 优化后成本（推荐）

- 每 15 分钟 + 10 封邮件 + 工作时间 = **约 $10-15/月**

## 🔧 自定义配置

### 1. 修改翻译提示词

编辑 `scripts/email_translator.py`:

```python
prompt = f"""请将以下邮件翻译成中文，并提供简短摘要（不超过100字）：

发件人: {from_addr}
主题: {subject}
内容: {body}

要求：
- 翻译要准确、自然
- 摘要要抓住重点
- 突出重要信息（会议时间、截止日期等）

请以 JSON 格式返回：
{{
  "subject_zh": "中文主题",
  "summary_zh": "中文摘要"
}}"""
```

### 2. 添加智能分类

可以让 OpenAI 同时进行分类：

```python
{{
  "subject_zh": "中文主题",
  "summary_zh": "中文摘要",
  "category": "work/personal/urgent/spam",  # 添加分类
  "priority": 1-5  # 添加优先级
}}
```

### 3. 富文本通知

修改为飞书 Card 格式：

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": {
        "content": "📬 未读邮件摘要",
        "tag": "plain_text"
      }
    },
    "elements": [
      {
        "tag": "div",
        "text": {
          "content": "summary content",
          "tag": "lark_md"
        }
      }
    ]
  }
}
```

## 🐛 故障排除

### 翻译失败

**问题**: `OPENAI_API_KEY 未设置`

**解决**:
```bash
export OPENAI_API_KEY="sk-your-key"
# 重启 API 服务
```

### 标记已读失败

**问题**: `email_ids` 格式错误

**解决**: 确保请求体是数组格式：
```json
["email-id-1", "email-id-2"]
```

### 飞书通知未收到

**问题**: Webhook URL 错误

**解决**: 
1. 检查环境变量 `FEISHU_WEBHOOK`
2. 测试 Webhook: `curl -X POST $FEISHU_WEBHOOK -d '{"msg_type":"text","content":{"text":"test"}}'`

## 📚 相关文档

- [SECURITY_SETUP_GUIDE.md](SECURITY_SETUP_GUIDE.md) - 安全配置
- [HTTP_API_QUICK_START.md](HTTP_API_QUICK_START.md) - API 快速开始
- [COST_OPTIMIZATION_GUIDE.md](COST_OPTIMIZATION_GUIDE.md) - 成本优化

---

**现在你有一个完整的邮件翻译和总结系统了！** 🎉
