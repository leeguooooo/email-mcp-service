#!/usr/bin/env python3
"""
邮件监控 HTTP API 服务
供 n8n 通过 HTTP Request 调用
"""
import sys
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用
app = FastAPI(
    title="Email Monitor API",
    description="MCP Email Service HTTP API for n8n",
    version="1.0.0"
)

# 添加 CORS 支持（允许 n8n 调用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CheckEmailsResponse(BaseModel):
    """检查邮件响应"""
    success: bool
    message: str
    stats: Dict[str, Any]
    important_emails: list = []
    notification: Dict[str, Any] = None


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Email Monitor API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "email-monitor-api"}


@app.post("/api/check-emails", response_model=CheckEmailsResponse)
async def check_emails():
    """
    检查邮件并返回重要邮件
    
    这个接口会：
    1. 获取未读邮件
    2. AI 过滤重要邮件
    3. 返回结果和通知内容
    
    n8n 收到后可以直接发送通知
    """
    try:
        logger.info("开始检查邮件...")
        
        # 导入邮件监控模块
        from scripts.email_monitor import EmailMonitor
        
        # 创建监控实例并运行
        monitor = EmailMonitor()
        result = await asyncio.to_thread(monitor.run_monitoring_cycle)
        
        logger.info(f"邮件检查完成: {result}")
        
        return JSONResponse(
            content=result,
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"检查邮件时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check emails: {str(e)}"
        )


@app.get("/api/stats")
async def get_stats():
    """获取统计信息"""
    try:
        # 这里可以添加统计逻辑
        return {
            "success": True,
            "stats": {
                "service": "running",
                "uptime": "available"
            }
        }
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@app.post("/api/test-notification")
async def test_notification():
    """测试通知（不检查邮件）"""
    return {
        "success": True,
        "message": "Test notification",
        "notification": {
            "msg_type": "text",
            "content": {
                "text": "📧 邮件监控 API 测试通知\n\n服务运行正常！"
            }
        }
    }


def main():
    """启动服务"""
    import uvicorn
    
    # 从环境变量获取配置
    import os
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "18888"))  # 使用不常见端口
    reload = os.getenv("API_RELOAD", "false").lower() == "true"
    
    logger.info(f"启动邮件监控 API 服务...")
    logger.info(f"监听地址: {host}:{port}")
    
    uvicorn.run(
        "scripts.email_monitor_api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()

