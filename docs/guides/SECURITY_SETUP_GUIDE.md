# 🔒 安全配置指南

## ⚠️ 重要警告

邮件信息**非常敏感**，必须采取严格的安全措施！

## 🛡️ 安全原则

### 1. 不要在代码中暴露敏感信息

❌ **禁止**:
```json
{
  "url": "https://e.httpmisonote.com/api/check-emails"
}
```

✅ **推荐**:
```python
api_base_url = os.getenv("API_BASE_URL", "http://localhost:18888")
url = f"{api_base_url}/api/check-emails"
```

### 2. 使用环境变量

所有敏感信息都应该通过环境变量配置：
- API 地址
- API 密钥
- Webhook URL
- 数据库连接字符串

## 📝 本地环境变量设置

在服务器或本地 `.env` 中设置环境变量：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `API_BASE_URL` | HTTP API 基础地址 | `http://localhost:18888` |
| `API_SECRET_KEY` | HTTP API 认证密钥 | `openssl rand -hex 32` |
| `FEISHU_WEBHOOK` | 飞书 Webhook | `https://open.larksuite.com/open-apis/bot/v2/hook/xxx` |
| `OPENAI_API_KEY` | AI 能力密钥 | `sk-xxx` |

**注意**:
- 不要在截图或公开文档中暴露完整的 URL/密钥
- 生产环境建议用系统环境变量或 secret manager
- 定期轮换敏感信息

## 🔐 API 服务安全

### 1. 添加 API 认证

在 `scripts/email_monitor_api.py` 中添加认证：

```python
from fastapi import Header, HTTPException

API_KEY = os.getenv("API_SECRET_KEY")

async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_api_key

@app.post("/api/check-emails", dependencies=[Depends(verify_api_key)])
async def check_emails():
    # ... 你的代码
```

### 2. 使用 HTTPS

确保 API 服务只通过 HTTPS 访问：
- ✅ `https://your-domain.com`
- ❌ `http://your-domain.com`

### 3. 限流保护

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/check-emails")
@limiter.limit("10/minute")  # 每分钟最多 10 次
async def check_emails(request: Request):
    # ... 你的代码
```

### 4. IP 白名单

在 Nginx 或防火墙层面限制访问：

```nginx
location /api/ {
    # 只允许调度服务器访问
    allow 1.2.3.4;  # 调度服务器 IP
    deny all;
    
    proxy_pass http://localhost:18888;
}
```

## 🗂️ .env 文件管理

### 本地开发 `.env` 文件

```bash
# API 配置
API_BASE_URL=http://localhost:18888
API_SECRET_KEY=your-random-secret-key-here

# 通知配置
FEISHU_WEBHOOK=https://open.larksuite.com/open-apis/bot/v2/hook/xxx

# Telegram（可选）
TELEGRAM_BOT_TOKEN=123456:ABC-DEF
TELEGRAM_CHAT_ID=123456789

# AI 配置 (可选)
OPENAI_API_KEY=sk-xxx
```

### 确保 .env 在 .gitignore 中

```bash
# 检查
cat .gitignore | grep .env

# 应该看到:
# .env
# .env.local
# .env.*.local
```

## 🚨 安全检查清单

部署前请确认：

- [ ] ✅ 所有敏感信息都使用环境变量
- [ ] ✅ `.env` 文件在 `.gitignore` 中
- [ ] ✅ API 服务启用了认证
- [ ] ✅ 使用 HTTPS 而非 HTTP
- [ ] ✅ 配置了限流保护
- [ ] ✅ 设置了 IP 白名单（可选）
- [ ] ✅ 定期审查访问日志
- [ ] ✅ API Key 定期轮换

## 🔍 审计日志

在 API 中添加访问日志：

```python
import logging

logger = logging.getLogger(__name__)

@app.post("/api/check-emails")
async def check_emails(request: Request):
    client_ip = request.client.host
    logger.info(f"API 调用 from {client_ip}")
    
    # ... 你的代码
```

## 🆘 安全事件响应

如果发现安全问题：

1. **立即**撤销暴露的 API Key
2. **立即**更改所有密码和密钥
3. **检查**访问日志，确认是否有未授权访问
4. **更新**所有依赖到最新安全版本
5. **通知**相关人员

## 📚 参考资源

- [OWASP API Security Top 10](https://owasp.org/www-project-api-security/)
- [FastAPI Security Best Practices](https://fastapi.tiangolo.com/tutorial/security/)

## ⚡ 快速安全部署

```bash
# 1. 生成安全的 API Key
openssl rand -hex 32

# 2. 设置环境变量
export API_SECRET_KEY="生成的密钥"
export FEISHU_WEBHOOK="https://open.larksuite.com/open-apis/bot/v2/hook/xxx"

# 3. 测试（带认证）
curl -X POST https://your-domain.com/api/check-emails \
  -H "X-Api-Key: 你的密钥"
```

---

**记住**: 安全性是持续的过程，不是一次性的任务！定期审查和更新安全配置。
