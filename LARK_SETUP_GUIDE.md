# 🚀 飞书 Webhook 邮件监控快速设置指南

你的飞书 webhook 已经测试成功！现在可以快速设置完整的邮件监控系统。

## ✅ 已完成的配置

- **飞书 Webhook**: `https://open.larksuite.com/open-apis/bot/v2/hook/a56c9638-cb65-4f95-bb11-9eb19e09692a`
- **测试状态**: ✅ 通过（文本和卡片消息都正常）
- **配置文件**: 已创建 `notification_config.json`
- **n8n 工作流**: 已更新为使用你的 webhook

## 🎯 下一步操作

### 1. 设置 AI API 密钥

选择一个 AI 提供商并设置 API 密钥：

```bash
# 选项 1: OpenAI (推荐，便宜且快速)
export OPENAI_API_KEY="your_openai_api_key"

# 选项 2: Anthropic Claude (更智能但较贵)
export ANTHROPIC_API_KEY="your_anthropic_api_key"
```

### 2. 配置邮件账户

如果还没有配置邮件账户：

```bash
python setup.py
```

### 3. 测试完整流程

```bash
# 测试邮件获取
python scripts/call_email_tool.py list_unread_emails '{"limit":3}'

# 测试完整监控流程
python scripts/email_monitor.py run
```

### 4. 导入 n8n 工作流

1. 打开 n8n 界面
2. 点击 "Import from file"
3. 选择 `n8n/email_monitoring_workflow.json`
4. 修改 "邮件监控" 节点中的脚本路径为你的实际路径：
   ```
   python /Users/leo/github.com/mcp-email-service/scripts/email_monitor.py run
   ```
5. 启动工作流

## 📱 飞书通知效果

你将收到两种类型的通知：

### 📧 重要邮件通知
当 AI 识别到重要邮件时，会发送卡片消息：
- 📧 **主题**: 邮件标题
- 👤 **发件人**: 发件人信息  
- ⏰ **时间**: 接收时间
- 🎯 **重要性**: AI 评分 (0-100%)
- 🏷️ **分类**: work/urgent/personal 等
- 🤖 **分析原因**: AI 判断理由
- 👀 **预览**: 邮件内容预览
- 💡 **建议操作**: reply/forward/archive 等

### 📊 系统监控报告
每次运行会发送系统状态：
- 📥 获取邮件数量
- ⚠️ 重要邮件数量
- 📤 发送通知数量
- 🟢/🔴 运行状态

## ⚙️ 自定义配置

### 调整 AI 过滤规则

编辑 `ai_filter_config.json`：

```json
{
  "priority_threshold": 0.7,
  "filter_rules": {
    "high_priority_senders": [
      "boss@company.com",
      "important@client.com"
    ],
    "high_priority_keywords": [
      "urgent", "important", "meeting", 
      "紧急", "重要", "会议"
    ]
  }
}
```

### 调整监控频率

在 n8n 工作流的定时器节点中修改：
- 每 5 分钟: `*/5 * * * *` (默认)
- 每 10 分钟: `*/10 * * * *`
- 每小时: `0 * * * *`

### 调整通知模板

编辑 `notification_config.json` 中的 `templates` 部分，可以自定义消息格式。

## 🧪 测试命令

```bash
# 测试飞书 webhook
python scripts/test_lark_webhook.py

# 测试 AI 过滤
python scripts/ai_email_filter.py '[{"id":"test","subject":"紧急会议","from":"boss@company.com","date":"2024-01-15","body_preview":"明天有重要会议"}]'

# 测试完整监控
python scripts/email_monitor.py test

# 查看系统状态
python scripts/email_monitor.py status
```

## 🚨 故障排除

### 常见问题

1. **AI 过滤失败**
   ```bash
   # 检查 API 密钥
   echo $OPENAI_API_KEY
   
   # 测试 API 连接
   python -c "import openai; print('OpenAI 可用')"
   ```

2. **邮件获取失败**
   ```bash
   # 检查邮件配置
   python scripts/call_email_tool.py list_accounts
   ```

3. **通知发送失败**
   ```bash
   # 测试 webhook
   python scripts/test_lark_webhook.py
   ```

### 查看日志

```bash
# 查看监控日志
tail -f email_monitor.log

# 查看通知统计
python scripts/notification_service.py stats 7
```

## 🎉 完成！

一旦设置完成，你的系统将：

1. ⏰ **每 5 分钟自动检查**新邮件
2. 🤖 **AI 智能分析**邮件重要性
3. 📱 **飞书实时通知**重要邮件
4. 🔄 **自动去重**避免重复通知
5. 📊 **运行统计**监控系统健康

享受智能邮件管理的便利吧！🚀

---

## 📞 需要帮助？

- 查看详细文档: `N8N_EMAIL_MONITORING_GUIDE.md`
- 运行设置脚本: `python scripts/setup_n8n_monitoring.py`
- 查看 n8n 配置: `n8n/README.md`
