# ✅ 正确的 n8n + Python MCP 架构方案

根据 Leo 和 leeguoo 的讨论，我们需要调整架构。

## ❌ 错误方案（当前）

```
n8n → Execute Command → python script (本地)
```

**问题**:
- n8n 是 Node.js 应用，Function 节点只能跑 JS
- 官方托管版不给 shell 访问
- 自建版虽然可以用 Execute Command，但要确保容器内有 Python

## ✅ 正确方案

### 方案 A: Python 服务 + HTTP Request (推荐)

```
n8n (定时触发) → HTTP Request → Python MCP Service → 返回结果 → n8n 处理通知
```

**架构**:
1. Python MCP 服务作为独立 HTTP 服务运行
2. n8n 通过 HTTP Request 节点调用
3. Python 返回 JSON 结果
4. n8n 根据结果发送飞书通知

### 方案 B: n8n Webhook 触发 Python (备选)

```
Python 脚本 (cron) → 处理邮件 → HTTP POST → n8n Webhook → 发送通知
```

**架构**:
1. Python 脚本独立运行（cron/systemd）
2. 发现重要邮件后 POST 到 n8n webhook
3. n8n 收到后发送飞书通知

## 🎯 推荐实现：方案 A

### 1. 创建 Python HTTP 服务

```python
# scripts/email_monitor_api.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI()

@app.post("/api/check-emails")
async def check_emails():
    """检查邮件并返回重要邮件"""
    try:
        from scripts.email_monitor import EmailMonitor
        monitor = EmailMonitor()
        result = monitor.run()
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 2. n8n 工作流配置

```json
{
  "nodes": [
    {
      "name": "定时触发",
      "type": "n8n-nodes-base.cron",
      "parameters": {
        "cronExpression": "*/5 * * * *"
      }
    },
    {
      "name": "调用邮件检查API",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://localhost:8000/api/check-emails",
        "method": "POST",
        "responseFormat": "json"
      }
    },
    {
      "name": "判断是否有重要邮件",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{$json.success}}",
              "value2": true
            }
          ]
        }
      }
    },
    {
      "name": "发送飞书通知",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "={{$env.FEISHU_WEBHOOK}}",
        "method": "POST",
        "bodyParameters": {
          "msg_type": "interactive",
          "card": "={{$json.notification}}"
        }
      }
    }
  ]
}
```

### 3. 部署方式

#### 开发环境
```bash
# 启动 Python API 服务
uv run python scripts/email_monitor_api.py

# 或使用 uvicorn
uv run uvicorn scripts.email_monitor_api:app --reload
```

#### 生产环境
```bash
# 使用 systemd
sudo systemctl enable email-monitor-api
sudo systemctl start email-monitor-api

# 或使用 Docker
docker run -d -p 8000:8000 email-monitor-api
```

## 📊 架构对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| Execute Command | 简单直接 | 需要自建 n8n + 容器配置 | ⭐⭐ |
| HTTP Service | 解耦、可扩展 | 需要额外服务 | ⭐⭐⭐⭐⭐ |
| Webhook 触发 | Python 独立 | n8n 只做通知 | ⭐⭐⭐⭐ |
| 全迁移 JS | n8n 原生 | 重写所有代码 | ⭐ |

## 🚀 立即行动

### 选择 1: 快速实现 HTTP Service

```bash
# 1. 安装 FastAPI
uv add fastapi uvicorn

# 2. 创建 API 服务
# (参考上面的 email_monitor_api.py)

# 3. 启动服务
uv run uvicorn scripts.email_monitor_api:app --reload

# 4. 在 n8n 中配置 HTTP Request 节点
```

### 选择 2: 简单的 Webhook 方案

```bash
# Python 脚本定时运行
# 发现重要邮件 → POST 到 n8n webhook
# n8n 负责发送通知
```

## 💡 我的建议

**立即实现方案 A (HTTP Service)**:
- ✅ 最灵活、可扩展
- ✅ Python 代码不需要大改
- ✅ n8n 只负责调度和通知
- ✅ 可以独立部署和监控
- ✅ 支持任何 n8n (托管/自建)

现在我可以帮你：
1. 创建 FastAPI 服务
2. 修改 n8n 工作流使用 HTTP Request
3. 更新部署文档

你想要哪种方案？
