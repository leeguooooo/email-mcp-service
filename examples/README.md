# 📋 配置示例

本目录包含所有配置文件的示例模板。

## 📁 文件说明

### 核心配置
- **accounts.example.json** - 邮箱账号配置示例
- **sync_config.json.example** - 邮件同步配置示例
- **.env.example** - 环境变量配置示例

## 🚀 快速开始

### 1. 复制示例配置

```bash
# 邮箱账号配置
cp examples/accounts.example.json data/accounts.json

# 同步配置（可选）
cp examples/sync_config.json.example data/sync_config.json

# 环境变量（本地脚本）
cp examples/.env.example .env
```

### 2. 编辑配置文件

#### data/accounts.json

```json
{
  "accounts": [
    {
      "email": "your@email.com",
      "password": "your-password-or-app-code",
      "imap_server": "imap.example.com",
      "imap_port": 993,
      "smtp_server": "smtp.example.com",
      "smtp_port": 465
    }
  ]
}
```

**重要提示**：
- 163/QQ 邮箱使用授权码，不是登录密码
- Gmail 使用应用专用密码
- 配置后记得将 `data/accounts.json` 添加到 `.gitignore`（已自动忽略）

#### .env

```bash
# 邮件 API 配置（可选）
API_SECRET_KEY=your-secret-key

# Webhook 配置
FEISHU_WEBHOOK=https://open.larksuite.com/...

# Telegram 配置（可选）
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=123456789

# AI 配置
OPENAI_API_KEY=sk-...
```

## 📚 配置指南

### 邮箱配置指南

| 邮箱提供商 | 配置说明 |
|----------|---------|
| **163 邮箱** | 登录 mail.163.com → 设置 → 开启 IMAP → 获取授权码 |
| **QQ 邮箱** | 设置 → 账户 → 开启 IMAP → 生成授权码 |
| **Gmail** | 开启两步验证 → [生成应用专用密码](https://myaccount.google.com/apppasswords) |
| **Outlook** | 直接使用邮箱密码 |

### 更多示例

其他配置模板在 `../config_templates/` 目录：
- `config_templates/notification_config.example.json` - 通知配置
- `config_templates/daily_digest_config.example.json` - 每日汇总配置
- `config_templates/env.example` - 环境变量

## ⚠️ 安全提示

1. **永远不要提交敏感配置文件**
   - `data/accounts.json`
   - `.env`
   - `data/sync_config.json`

2. **使用强密码/密钥**
   ```bash
   # 生成随机密钥
   openssl rand -hex 32
   ```

3. **定期轮换密钥**
   - API Key 每 90 天轮换一次
   - 邮箱授权码每 180 天更新

## 📚 相关文档

- [主文档](../README.md)
- [快速开始指南](../docs/guides/HTTP_API_QUICK_START.md)
- [安全配置指南](../docs/guides/SECURITY_SETUP_GUIDE.md)
- [部署清单](../docs/guides/FINAL_DEPLOYMENT_CHECKLIST.md)
