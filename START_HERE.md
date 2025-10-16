# 🎯 从这里开始！

欢迎使用 MCP 邮件服务 + n8n AI 智能监控系统！

## ⚡ 超快速开始 (3 分钟)

### 步骤 1: 设置 API Key

```bash
export N8N_API_KEY="your_n8n_api_key"
```

> 💡 从 https://n8n.ifoodme.com/ 的 Settings → API 获取

### 步骤 2: 测试连接

```bash
uv run python scripts/test_n8n_api.py
```

### 步骤 3: 自动导入

```bash
./setup_n8n.sh
```

**就这么简单！** ✨

## 📖 详细文档

根据你的需求选择：

### 🚀 我想快速开始
→ [QUICK_N8N_SETUP.md](QUICK_N8N_SETUP.md) - 3 步完成设置

### 🔧 我想了解 API 设置
→ [N8N_API_SETUP_GUIDE.md](N8N_API_SETUP_GUIDE.md) - API 详细说明

### 📚 我想完整了解系统
→ [N8N_EMAIL_MONITORING_GUIDE.md](N8N_EMAIL_MONITORING_GUIDE.md) - 完整功能文档

### 🏢 我要部署到生产环境
→ [PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md) - 生产最佳实践

### 🎯 我想看总结
→ [FINAL_SETUP_SUMMARY.md](FINAL_SETUP_SUMMARY.md) - 完整总结

## 🎁 你会得到什么

✅ **自动化邮件监控** - 每 5 分钟自动检查  
✅ **AI 智能过滤** - 自动识别重要邮件  
✅ **实时通知** - 飞书群组即时提醒  
✅ **去重保护** - 避免重复打扰  
✅ **生产级稳定** - 完善的错误处理  

## 🎮 可用命令速查

### 测试和诊断
```bash
# 测试 n8n API
uv run python scripts/test_n8n_api.py

# 测试飞书 webhook
uv run python scripts/test_lark_webhook.py

# 完整系统测试
uv run python scripts/setup_n8n_monitoring.py --test-only

# 查看系统状态
uv run python scripts/email_monitor.py status
```

### 手动运行
```bash
# 运行一次监控循环
uv run python scripts/email_monitor.py run

# 获取未读邮件
uv run python scripts/call_email_tool.py list_unread_emails '{"limit":5}'

# 测试通知
uv run python scripts/notification_service.py test
```

## 🔑 环境变量

### 必需
```bash
export N8N_API_KEY="your_api_key"  # n8n API 密钥
```

### 可选 (有默认值)
```bash
export N8N_URL="https://n8n.ifoodme.com"
export FEISHU_WEBHOOK="your_webhook_url"
export OPENAI_API_KEY="your_openai_key"  # AI 过滤
```

## 💡 小提示

- 🤖 没有 OpenAI API Key？没关系！系统会自动回退到关键词过滤
- 📱 想换通知平台？编辑 `notification_config.json` 支持钉钉/企微/Slack
- ⏰ 想改频率？在 n8n 工作流中修改 cron 表达式
- 🔍 遇到问题？查看 `email_monitor.log` 日志文件

## 🆘 需要帮助？

### 快速诊断
```bash
# 检查环境变量
env | grep -E "(N8N|FEISHU|OPENAI)"

# 查看日志
tail -f email_monitor.log

# 完整健康检查
uv run python scripts/setup_n8n_monitoring.py --check-only
```

### 常见问题
1. **API 连接失败** → 检查 N8N_API_KEY 和网络
2. **工作流导入失败** → 确认 API Key 权限
3. **通知不工作** → 测试 webhook URL
4. **AI 过滤失败** → 系统会自动回退，不影响运行

## 📊 系统架构

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│   n8n 定时   │───▶│  邮件获取     │───▶│  AI 过滤     │───▶│  飞书通知     │
│   (5分钟)    │    │  (MCP工具)   │    │  (智能判断)  │    │  (实时推送)   │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
```

## 🎉 开始你的智能邮件管理之旅！

现在就运行：
```bash
export N8N_API_KEY="your_key"
./setup_n8n.sh
```

**3 分钟后，你将拥有一个完全自动化的智能邮件监控系统！** 🚀
