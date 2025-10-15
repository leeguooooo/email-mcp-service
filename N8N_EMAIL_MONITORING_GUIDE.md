# 🤖 n8n + AI 智能邮件监控与通知系统

这是一个完整的解决方案，让你可以使用 n8n 定时触发邮件监控，通过 AI 过滤重要邮件，并自动发送 webhook 通知到钉钉、飞书、企业微信等平台。

## 🌟 系统特性

- **🔄 自动化监控**: n8n 定时触发，无需人工干预
- **🧠 AI 智能过滤**: 使用 OpenAI/Claude 等 AI 判断邮件重要性
- **📱 多平台通知**: 支持钉钉、飞书、企业微信、Slack 等
- **🔒 去重保护**: 避免重复通知同一封邮件
- **⚡ 高性能**: 并行处理，支持多账户
- **🛡️ 错误处理**: 完善的错误处理和重试机制
- **📊 监控统计**: 运行状态和成功率统计

## 🏗️ 系统架构

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│   n8n 定时   │───▶│  邮件获取     │───▶│  AI 过滤     │───▶│  Webhook通知  │
│   触发器     │    │  (MCP工具)   │    │  (智能判断)  │    │  (多平台)     │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
                           │                    │                   │
                           ▼                    ▼                   ▼
                    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
                    │   邮件缓存    │    │  过滤规则    │    │   去重数据库  │
                    │   (SQLite)   │    │  (配置文件)  │    │   (SQLite)   │
                    └──────────────┘    └─────────────┘    └──────────────┘
```

## 🚀 快速开始

### 1. 一键设置

```bash
# 克隆项目（如果还没有）
git clone https://github.com/leeguooooo/email-mcp-service.git
cd mcp-email-service

# 运行自动设置脚本
python scripts/setup_n8n_monitoring.py
```

这个脚本会自动：
- ✅ 检查所有依赖项
- ✅ 安装缺失的 Python 包
- ✅ 创建配置文件模板
- ✅ 测试各个组件
- ✅ 生成 n8n 配置说明

### 2. 配置邮件账户

```bash
# 配置邮件账户（如果还没有）
python setup.py
```

### 3. 设置 API 密钥

```bash
# OpenAI (推荐)
export OPENAI_API_KEY="your_openai_api_key"

# 或者 Anthropic Claude
export ANTHROPIC_API_KEY="your_anthropic_api_key"

# 设置 Python 路径
export PYTHONPATH="/path/to/mcp-email-service:$PYTHONPATH"
```

### 4. 配置 Webhook

编辑 `notification_config.json`，设置你的 webhook URL：

```json
{
  "webhooks": [
    {
      "name": "dingtalk_main",
      "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
      "webhook_type": "dingtalk",
      "secret": "YOUR_SECRET",
      "enabled": true
    }
  ]
}
```

### 5. 导入 n8n 工作流

1. 打开 n8n 界面
2. 点击 "Import from file"
3. 选择 `n8n/email_monitoring_workflow.json`
4. 修改 "邮件监控" 节点中的脚本路径
5. 配置 webhook URL
6. 启动工作流

## 📁 项目结构

```
mcp-email-service/
├── scripts/                          # 核心脚本
│   ├── call_email_tool.py            # 邮件工具桥接
│   ├── ai_email_filter.py            # AI 过滤服务
│   ├── notification_service.py       # 通知服务
│   ├── email_monitor.py              # 主控制脚本
│   └── setup_n8n_monitoring.py       # 自动设置脚本
├── n8n/                              # n8n 工作流
│   ├── email_monitoring_workflow.json # 工作流配置
│   └── README.md                     # n8n 详细说明
├── config_templates/                 # 配置模板
│   ├── ai_filter_config.example.json
│   ├── notification_config.example.json
│   └── email_monitor_config.example.json
└── 配置文件 (自动生成)
    ├── ai_filter_config.json         # AI 过滤配置
    ├── notification_config.json      # 通知配置
    └── email_monitor_config.json     # 监控配置
```

## 🔧 详细配置

### AI 过滤配置 (`ai_filter_config.json`)

```json
{
  "ai_provider": "openai",              // AI 提供商: openai, anthropic
  "model": "gpt-3.5-turbo",            // 模型名称
  "priority_threshold": 0.7,           // 重要性阈值 (0-1)
  "filter_rules": {
    "high_priority_senders": [         // 高优先级发件人
      "boss@company.com",
      "important@client.com"
    ],
    "high_priority_keywords": [        // 重要关键词
      "urgent", "important", "紧急", "重要"
    ],
    "low_priority_keywords": [         // 低优先级关键词
      "newsletter", "promotion", "广告"
    ]
  }
}
```

### 通知配置 (`notification_config.json`)

```json
{
  "webhooks": [
    {
      "name": "dingtalk_main",
      "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN",
      "webhook_type": "dingtalk",      // 支持: dingtalk, feishu, wechat, slack, custom
      "secret": "YOUR_SECRET",         // 签名密钥（钉钉、飞书需要）
      "retry_times": 3,                // 重试次数
      "enabled": true,                 // 是否启用
      "template": "dingtalk"           // 消息模板
    }
  ],
  "deduplication": {
    "enabled": true,                   // 启用去重
    "window_hours": 24,               // 去重时间窗口（小时）
    "cleanup_days": 7                 // 清理历史记录（天）
  }
}
```

### 监控配置 (`email_monitor_config.json`)

```json
{
  "email": {
    "fetch_limit": 20,                // 每次获取邮件数量
    "unread_only": true,              // 只获取未读邮件
    "account_id": null,               // 指定账户ID（null=所有账户）
    "folder": "INBOX"                 // 邮件文件夹
  },
  "ai_filter": {
    "enabled": true,                  // 启用AI过滤
    "priority_threshold": 0.7         // 重要性阈值
  },
  "notification": {
    "enabled": true,                  // 启用通知
    "webhook_names": null             // 指定webhook（null=所有启用的）
  }
}
```

## 🧪 测试和调试

### 测试单个组件

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

### 查看运行状态

```bash
# 查看监控状态
python scripts/email_monitor.py status

# 查看通知统计
python scripts/notification_service.py stats 7

# 查看配置
python scripts/email_monitor.py config
```

### 调试技巧

1. **查看日志**:
   ```bash
   tail -f email_monitor.log
   ```

2. **n8n 调试**:
   - 使用 n8n 的执行历史查看详细日志
   - 在代码节点中添加 `console.log()` 输出调试信息

3. **手动测试**:
   ```bash
   # 测试特定组件
   python scripts/setup_n8n_monitoring.py --test-only
   ```

## 📊 监控和维护

### 运行统计

系统会自动记录以下统计信息：
- 📥 获取邮件数量
- ⚠️ 重要邮件数量  
- 📤 发送通知数量
- ✅ 成功率统计
- ⏱️ 运行时间

### 性能优化

1. **调整监控频率**: 根据邮件量调整 n8n 定时器
2. **优化 AI 过滤**: 使用更快的模型或本地模型
3. **批量处理**: 增加 `fetch_limit` 减少调用频率
4. **缓存优化**: 使用邮件缓存减少重复获取

### 故障处理

常见问题和解决方案：

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 脚本执行失败 | 路径或依赖问题 | 检查 Python 路径和依赖安装 |
| AI 过滤失败 | API 密钥或网络问题 | 验证 API 密钥，检查网络连接 |
| 通知发送失败 | Webhook URL 或签名问题 | 验证 URL 和签名配置 |
| 重复通知 | 去重配置问题 | 检查去重设置，清理历史记录 |

## 🔒 安全注意事项

1. **API 密钥安全**:
   - 使用环境变量存储密钥
   - 定期轮换密钥
   - 限制 API 密钥权限

2. **Webhook 安全**:
   - 使用 HTTPS URL
   - 配置签名验证
   - 限制访问权限

3. **邮件内容隐私**:
   - 注意发送给 AI 的内容
   - 考虑使用本地 AI 模型
   - 配置内容过滤规则

## 🚀 高级功能

### 1. 多账户支持

```json
{
  "email": {
    "account_id": "account1",  // 指定特定账户
    "folder": "INBOX"
  }
}
```

### 2. 自定义过滤规则

```json
{
  "filter_rules": {
    "high_priority_senders": ["vip@company.com"],
    "category_keywords": {
      "urgent": ["urgent", "asap", "紧急"],
      "meeting": ["meeting", "会议", "conference"],
      "finance": ["invoice", "payment", "发票", "付款"]
    }
  }
}
```

### 3. 多 Webhook 支持

```json
{
  "webhooks": [
    {
      "name": "urgent_channel",
      "webhook_url": "...",
      "enabled": true
    },
    {
      "name": "general_channel", 
      "webhook_url": "...",
      "enabled": true
    }
  ]
}
```

### 4. 条件通知

在 n8n 中可以添加条件节点，根据不同条件发送到不同的 webhook：

```javascript
// n8n 条件节点示例
if ($json.category === 'urgent') {
  return [{ json: { webhook: 'urgent_channel' } }];
} else {
  return [{ json: { webhook: 'general_channel' } }];
}
```

## 📞 支持和贡献

### 获取帮助

1. 查看 [n8n/README.md](n8n/README.md) 获取详细的 n8n 配置说明
2. 运行 `python scripts/setup_n8n_monitoring.py --help` 查看设置选项
3. 查看项目 Issues 或提交新的问题

### 贡献代码

欢迎提交 Pull Request 来改进这个系统：
- 🐛 修复 Bug
- ✨ 添加新功能
- 📚 改进文档
- 🧪 添加测试

## 📄 许可证

本项目遵循 MIT 许可证。

---

**🎉 现在你就有了一个完全自动化的智能邮件监控系统！**

系统会自动：
1. ⏰ 每 5 分钟检查新邮件
2. 🤖 使用 AI 判断邮件重要性
3. 📱 发送重要邮件通知到你的工作群
4. 🔄 避免重复通知
5. 📊 记录运行统计

享受智能邮件管理带来的便利吧！ 🚀
