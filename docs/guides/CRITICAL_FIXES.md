# 🔧 关键修复清单（本地定时）

这份清单保留了最关键的修复要点，适用于当前的本地定时方案。

## 1) HTTP API 路径拼接错误

**问题**: 基础 URL 写成了完整端点，导致重复拼接。

**正确示例**:
```
✅ 正确: http://localhost:18888
❌ 错误: http://localhost:18888/api/check-emails
```

**调用方式**:
- `http://localhost:18888/api/check-emails`
- `http://localhost:18888/api/translate-unread`

## 2) 环境变量模板统一

- 使用 `config_templates/env.example`
- 避免硬编码 Webhook 与 API Key

## 3) API 认证校验

- 设置 `API_SECRET_KEY`
- 调用时携带 `X-API-Key`

## 4) 脚本运行路径

- 使用绝对路径或先 `cd` 到项目根目录
- cron/systemd 中显式指定工作目录

---

**说明**: 旧的自动化平台配置细节已弃用，以本地定时任务为准。
