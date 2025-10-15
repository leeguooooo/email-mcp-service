# n8n 智能邮件监控与通知系统

这是一个完整的 n8n 工作流，用于自动监控邮件、使用 AI 过滤重要邮件并发送通知。

## 🚀 功能特性

- **定时监控**: 每5分钟自动检查新邮件
- **AI 智能过滤**: 使用 AI 判断邮件重要性
- **多平台通知**: 支持钉钉、飞书、企业微信、Slack 等
- **去重机制**: 避免重复通知同一封邮件
- **错误处理**: 完善的错误处理和通知机制
- **健康监控**: 系统运行状态监控

## 📋 前置要求

### 1. 系统环境
- n8n 已安装并运行
- Python 3.11+ 
- MCP 邮件服务已配置

### 2. 依赖安装
```bash
# 安装 Python 依赖
pip install openai anthropic requests

# 或者使用项目的依赖管理
cd /path/to/mcp-email-service
uv sync
```

### 3. 配置文件准备
确保以下配置文件已创建：
- `accounts.json` - 邮件账户配置
- `ai_filter_config.json` - AI 过滤配置
- `notification_config.json` - 通知配置
- `email_monitor_config.json` - 监控配置

## 🛠️ 安装步骤

### 1. 导入工作流
1. 打开 n8n 界面
2. 点击 "Import from file" 或 "Import from URL"
3. 选择 `email_monitoring_workflow.json` 文件
4. 确认导入

### 2. 配置工作流

#### 修改脚本路径
在 "邮件监控" 节点中，更新脚本路径：
```bash
# 将路径改为你的实际路径
/your/path/to/mcp-email-service/scripts/email_monitor.py run
```

#### 配置 Webhook URL
在通知节点中配置你的 webhook URL：

**钉钉机器人**:
```
https://oapi.dingtalk.com/robot/send?access_token=YOUR_DINGTALK_TOKEN
```

**飞书机器人**:
```
https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_FEISHU_TOKEN
```

**企业微信机器人**:
```
https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_WECHAT_KEY
```

### 3. 配置定时器
默认每5分钟运行一次，可以根据需要调整：
- 每分钟: `* * * * *`
- 每10分钟: `*/10 * * * *`
- 每小时: `0 * * * *`

## ⚙️ 配置文件详解

### 1. AI 过滤配置 (`ai_filter_config.json`)
```json
{
  "ai_provider": "openai",
  "model": "gpt-3.5-turbo",
  "api_key_env": "OPENAI_API_KEY",
  "priority_threshold": 0.7,
  "max_body_length": 500,
  "filter_rules": {
    "high_priority_senders": [
      "boss@company.com",
      "important@client.com"
    ],
    "high_priority_keywords": [
      "urgent", "important", "asap", "紧急", "重要"
    ],
    "low_priority_keywords": [
      "newsletter", "promotion", "unsubscribe", "广告", "推广"
    ]
  }
}
```

### 2. 通知配置 (`notification_config.json`)
```json
{
  "webhooks": [
    {
      "name": "dingtalk",
      "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
      "webhook_type": "dingtalk",
      "secret": "YOUR_SECRET",
      "enabled": true,
      "template": "dingtalk"
    },
    {
      "name": "feishu", 
      "webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_TOKEN",
      "webhook_type": "feishu",
      "enabled": true,
      "template": "feishu"
    }
  ],
  "deduplication": {
    "enabled": true,
    "window_hours": 24,
    "cleanup_days": 7
  }
}
```

### 3. 监控配置 (`email_monitor_config.json`)
```json
{
  "email": {
    "fetch_limit": 20,
    "unread_only": true,
    "account_id": null,
    "folder": "INBOX"
  },
  "ai_filter": {
    "enabled": true,
    "config_path": "ai_filter_config.json",
    "priority_threshold": 0.7
  },
  "notification": {
    "enabled": true,
    "config_path": "notification_config.json",
    "webhook_names": null
  }
}
```

## 🔧 环境变量设置

在 n8n 或系统中设置以下环境变量：

```bash
# OpenAI API Key (如果使用 OpenAI)
export OPENAI_API_KEY="your_openai_api_key"

# Anthropic API Key (如果使用 Claude)
export ANTHROPIC_API_KEY="your_anthropic_api_key"

# Python 路径 (确保能找到项目依赖)
export PYTHONPATH="/path/to/mcp-email-service:$PYTHONPATH"
```

## 🚦 工作流说明

### 节点功能

1. **定时触发器**: 每5分钟触发一次监控
2. **邮件监控**: 执行主监控脚本
3. **解析结果**: 解析监控结果并提取统计信息
4. **检查重要邮件**: 判断是否有重要邮件需要通知
5. **准备管理员通知**: 格式化通知消息
6. **发送管理员通知**: 发送到配置的 webhook
7. **记录日志**: 记录运行日志
8. **错误处理**: 处理运行错误并发送错误通知
9. **健康检查**: 监控系统健康状态

### 数据流

```
定时触发 → 邮件监控 → 解析结果 → 检查重要邮件
                ↓              ↓
            错误处理 ←→ 发送通知 + 记录日志 → 健康检查
```

## 🧪 测试和调试

### 1. 测试单个组件
```bash
# 测试邮件获取
python scripts/call_email_tool.py list_unread_emails '{"limit":5}'

# 测试 AI 过滤
python scripts/ai_email_filter.py '[{"id":"test","subject":"Urgent meeting","from":"boss@company.com","date":"2024-01-15","body_preview":"We need to discuss..."}]'

# 测试通知发送
python scripts/notification_service.py test

# 测试完整流程
python scripts/email_monitor.py run
```

### 2. 在 n8n 中测试
1. 点击工作流中的 "Test workflow" 按钮
2. 手动触发 "定时触发器" 节点
3. 查看每个节点的执行结果
4. 检查日志输出

### 3. 调试技巧
- 在 "解析结果" 节点中添加 `console.log()` 输出调试信息
- 使用 n8n 的执行历史查看详细运行日志
- 检查 Python 脚本的返回码和错误信息

## 📊 监控和维护

### 1. 运行状态监控
- 查看 n8n 执行历史
- 检查通知发送成功率
- 监控系统资源使用

### 2. 日志管理
```bash
# 查看监控日志
tail -f email_monitor.log

# 查看通知历史
python scripts/notification_service.py stats 7
```

### 3. 性能优化
- 调整监控频率
- 优化 AI 过滤规则
- 配置合适的邮件获取数量

## 🔒 安全注意事项

1. **API 密钥安全**
   - 使用环境变量存储 API 密钥
   - 定期轮换密钥
   - 限制 API 密钥权限

2. **Webhook 安全**
   - 使用 HTTPS URL
   - 配置 webhook 签名验证
   - 限制 webhook 访问权限

3. **邮件内容隐私**
   - 注意发送给 AI 的邮件内容
   - 考虑使用本地 AI 模型
   - 配置内容过滤规则

## 🆘 故障排除

### 常见问题

1. **脚本执行失败**
   - 检查 Python 路径和依赖
   - 验证配置文件格式
   - 查看详细错误信息

2. **AI 过滤失败**
   - 检查 API 密钥配置
   - 验证网络连接
   - 查看 API 调用限制

3. **通知发送失败**
   - 验证 webhook URL
   - 检查签名配置
   - 测试网络连接

4. **重复通知**
   - 检查去重配置
   - 清理历史记录
   - 验证邮件 ID 唯一性

### 日志分析
```bash
# 查看最近的错误
grep "ERROR" email_monitor.log | tail -10

# 统计成功率
grep -c "SUCCESS" email_monitor.log
grep -c "ERROR" email_monitor.log
```

## 📈 扩展功能

### 1. 添加更多通知渠道
- Slack
- Microsoft Teams  
- 自定义 webhook

### 2. 增强 AI 过滤
- 多模型投票
- 自定义训练数据
- 上下文学习

### 3. 高级功能
- 邮件自动回复
- 智能分类归档
- 优先级队列处理

## 📞 支持

如有问题，请：
1. 查看日志文件
2. 检查配置文件
3. 运行测试命令
4. 提交 Issue 或联系技术支持

---

**注意**: 请根据实际环境调整配置参数，确保系统安全和稳定运行。
