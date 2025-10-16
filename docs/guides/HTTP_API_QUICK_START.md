# 🚀 HTTP API 方案快速开始

**正确的架构**: Python HTTP 服务 + n8n HTTP Request

## ⚡ 3 步部署

### 1. 启动 Python API 服务

```bash
# 开发环境 - 自动重载
uv run python scripts/email_monitor_api.py

# 或使用 uvicorn (推荐)
uv run uvicorn scripts.email_monitor_api:app --reload --host 0.0.0.0 --port 18888
```

**服务启动后**:
- API 地址: `http://localhost:18888`
- 健康检查: `http://localhost:18888/health`
- API 文档: `http://localhost:18888/docs`

### 2. 测试 API

```bash
# 健康检查
curl http://localhost:18888/health

# 测试邮件检查
curl -X POST http://localhost:18888/api/check-emails

# 测试通知
curl -X POST http://localhost:18888/api/test-notification
```

### 3. 部署 n8n 工作流

```bash
# 使用新的 HTTP 工作流
export N8N_API_KEY="your_key"
uv run python -c "
import json, sys
sys.path.insert(0, '.')
from scripts.setup_n8n_workflow import N8NWorkflowManager
import os

manager = N8NWorkflowManager(
    os.getenv('N8N_URL', 'https://n8n.ifoodme.com'),
    os.getenv('N8N_API_KEY')
)

# 导入新的 HTTP 工作流
with open('n8n/email_monitoring_http_workflow.json') as f:
    workflow = json.load(f)
    
result = manager.create_workflow(workflow)
print(f'✅ 工作流已创建: {result[\"id\"]}')
print(f'URL: https://n8n.ifoodme.com/workflow/{result[\"id\"]}')
"
```

## 📊 架构图

```
┌─────────────────┐
│   n8n 云服务     │
│  (定时触发)      │
└────────┬────────┘
         │ HTTP Request
         ↓
┌─────────────────┐
│  FastAPI Service│ ← 你的服务器
│  (Port 8000)    │
└────────┬────────┘
         │ 调用
         ↓
┌─────────────────┐
│  Python MCP     │
│  (邮件处理)     │
└─────────────────┘
         │ 返回结果
         ↓
┌─────────────────┐
│   n8n 接收      │
│  (发送飞书通知) │
└─────────────────┘
```

## 🔧 配置 n8n 工作流

在 n8n 中你会看到：

1. **定时触发** - 每5分钟运行
2. **调用邮件检查API** - HTTP Request 到 `http://localhost:8000/api/check-emails`
3. **检查结果** - 判断是否有重要邮件
4. **发送飞书通知** - 如果有重要邮件

### 修改 API 地址

在 n8n 工作流的"调用邮件检查API"节点中，将 URL 改为：

- **本地测试**: `http://localhost:18888/api/check-emails`
- **服务器部署**: `http://your-server-ip:18888/api/check-emails`
- **域名部署**: `https://api.yourdomain.com/api/check-emails`

## 🏭 生产部署

### 选项 1: systemd 服务

```bash
# 创建服务文件
sudo tee /etc/systemd/system/email-monitor-api.service <<EOF
[Unit]
Description=Email Monitor API Service
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/mcp-email-service
Environment="PATH=/path/to/.venv/bin"
ExecStart=/path/to/.venv/bin/uvicorn scripts.email_monitor_api:app --host 0.0.0.0 --port 18888
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl enable email-monitor-api
sudo systemctl start email-monitor-api
sudo systemctl status email-monitor-api
```

### 选项 2: Docker 部署

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install uv && \\
    uv sync

EXPOSE 18888

CMD ["uv", "run", "uvicorn", "scripts.email_monitor_api:app", "--host", "0.0.0.0", "--port", "18888"]
```

```bash
# 构建和运行
docker build -t email-monitor-api .
docker run -d -p 18888:18888 --name email-api email-monitor-api
```

### 选项 3: Nginx 反向代理

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:18888;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📝 API 接口文档

### POST /api/check-emails

检查邮件并返回重要邮件

**响应示例**:
```json
{
  "success": true,
  "message": "Monitoring cycle completed successfully",
  "stats": {
    "fetched_emails": 20,
    "important_emails": 3,
    "notifications_sent": 1
  },
  "important_emails": [
    {
      "from": "boss@company.com",
      "subject": "Urgent: Project Deadline",
      "priority_score": 0.9
    }
  ],
  "notification": {
    "msg_type": "interactive",
    "card": { ... }
  }
}
```

### GET /health

健康检查

**响应**:
```json
{
  "status": "healthy",
  "service": "email-monitor-api"
}
```

### POST /api/test-notification

测试通知（不实际检查邮件）

## 🔒 安全建议

### 1. 添加 API 认证

```python
from fastapi import Header, HTTPException

API_KEY = os.getenv("API_KEY", "your-secret-key")

async def verify_api_key(x_api_key: str = Header()):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_api_key

# 在路由中使用
@app.post("/api/check-emails", dependencies=[Depends(verify_api_key)])
async def check_emails():
    ...
```

### 2. 使用 HTTPS

```bash
# 使用 Let's Encrypt
sudo certbot --nginx -d api.yourdomain.com
```

### 3. 限流

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.post("/api/check-emails")
@limiter.limit("10/minute")
async def check_emails(request: Request):
    ...
```

## 🎯 优势对比

| 特性 | Execute Command | HTTP API |
|------|-----------------|----------|
| n8n 兼容性 | 仅自建版 | ✅ 所有版本 |
| 部署复杂度 | 高（容器配置） | ✅ 低（独立服务） |
| 可扩展性 | 低 | ✅ 高 |
| 监控调试 | 困难 | ✅ 简单 |
| Python 依赖 | 需要容器内安装 | ✅ 独立管理 |
| 代码修改 | 无需 | ✅ 无需 |

## ✅ 现在可以

1. **本地测试**: 启动 API + 在 n8n 中测试
2. **生产部署**: systemd/Docker + 配置域名
3. **开始使用**: 激活 n8n 工作流

**Python 代码完全不用改，只是加了个 HTTP 接口！** 🎉
