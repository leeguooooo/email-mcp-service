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
```json
{
  "url": "={{ $env.EMAIL_API_URL }}"
}
```

### 2. 使用环境变量

所有敏感信息都应该通过环境变量配置：
- API 地址
- API 密钥
- Webhook URL
- 数据库连接字符串

## 📝 n8n 环境变量设置

### 步骤 1: 访问 n8n 设置

1. 登录 n8n: https://n8n.ifoodme.com/
2. 进入 **Settings** → **Environments**

### 步骤 2: 添加环境变量

添加以下环境变量：

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `EMAIL_API_URL` | 邮件 API 地址 | `https://your-domain.com/api/check-emails` |
| `FEISHU_WEBHOOK` | 飞书 Webhook | `https://open.larksuite.com/open-apis/bot/v2/hook/xxx` |

**注意**: 
- 不要在截图中暴露完整的 URL
- 不要在公开文档中写入真实值
- 定期轮换敏感信息

### 步骤 3: 在工作流中使用

```json
{
  "parameters": {
    "url": "={{ $env.EMAIL_API_URL }}",
    "method": "POST"
  }
}
```

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
    # 只允许 n8n 服务器访问
    allow 1.2.3.4;  # n8n 服务器 IP
    deny all;
    
    proxy_pass http://localhost:18888;
}
```

## 🗂️ .env 文件管理

### 本地开发 `.env` 文件

```bash
# 邮件 API 配置
EMAIL_API_URL=https://your-domain.com/api/check-emails
API_SECRET_KEY=your-random-secret-key-here

# n8n 配置
N8N_URL=https://n8n.ifoodme.com
N8N_API_KEY=your-n8n-api-key

# 通知配置
FEISHU_WEBHOOK=https://open.larksuite.com/open-apis/bot/v2/hook/xxx

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
- [n8n Security Documentation](https://docs.n8n.io/hosting/security/)

## ⚡ 快速安全部署

```bash
# 1. 生成安全的 API Key
openssl rand -hex 32

# 2. 设置环境变量
export API_SECRET_KEY="生成的密钥"
export EMAIL_API_URL="https://your-domain.com/api/check-emails"

# 3. 在 n8n 中设置环境变量
# (通过 Web 界面)

# 4. 部署工作流
uv run python scripts/deploy_http_workflow.py

# 5. 测试（带认证）
curl -X POST https://your-domain.com/api/check-emails \
  -H "X-Api-Key: 你的密钥"
```

---

**记住**: 安全性是持续的过程，不是一次性的任务！定期审查和更新安全配置。
