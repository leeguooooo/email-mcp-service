#!/usr/bin/env python3
"""
邮件监控 HTTP API 服务
供 n8n 通过 HTTP Request 调用
"""
import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from fastapi import FastAPI, HTTPException, Header, Depends
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

# API Key 配置
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
if not API_SECRET_KEY:
    logger.warning("⚠️  API_SECRET_KEY 未设置，API 将不受保护！")
    logger.warning("   请设置: export API_SECRET_KEY='your-secret-key'")


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")):
    """验证 API Key"""
    # 如果未配置 API_SECRET_KEY，跳过验证（开发模式）
    if not API_SECRET_KEY:
        logger.warning("🔓 API Key 验证已禁用（未设置 API_SECRET_KEY）")
        return None
    
    if not x_api_key:
        logger.warning("❌ 请求缺少 X-API-Key header")
        raise HTTPException(
            status_code=401,
            detail="Missing API Key. Please provide X-API-Key header."
        )
    
    if x_api_key != API_SECRET_KEY:
        logger.warning(f"❌ 无效的 API Key: {x_api_key[:8]}...")
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )
    
    logger.info("✅ API Key 验证成功")
    return x_api_key

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
    message: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
    important_emails: list = []
    notification: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class EmailDetailRequest(BaseModel):
    """请求单封邮件详情"""
    email_id: str
    message_id: Optional[str] = None
    account_id: Optional[str] = None
    folder: str = "INBOX"


class ListEmailsRequest(BaseModel):
    """请求邮件列表"""
    limit: int = 100
    offset: int = 0
    unread_only: bool = False
    folder: str = "all"
    account_id: Optional[str] = None
    include_metadata: bool = True
    use_cache: bool = True


class MarkEmailsRequest(BaseModel):
    """标记邮件已读/未读"""
    email_ids: List[str]
    mark_as: str  # read|unread
    folder: str = "INBOX"
    account_id: Optional[str] = None


class DeleteEmailsRequest(BaseModel):
    """删除/移入垃圾箱"""
    email_ids: List[str]
    folder: str = "INBOX"
    permanent: bool = False
    trash_folder: str = "Trash"
    account_id: Optional[str] = None


class MoveEmailsRequest(BaseModel):
    """移动邮件到指定文件夹"""
    email_ids: List[str]
    target_folder: str
    source_folder: str = "INBOX"
    account_id: Optional[str] = None


class SendEmailRequest(BaseModel):
    """发送新邮件"""
    to: List[str]
    subject: str
    body: str
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None
    attachments: Optional[List[Dict[str, str]]] = None
    is_html: bool = False
    account_id: Optional[str] = None


class ReplyEmailRequest(BaseModel):
    """回复邮件"""
    email_id: str
    body: str
    folder: str = "INBOX"
    reply_all: bool = False
    attachments: Optional[List[Dict[str, str]]] = None
    is_html: bool = False
    account_id: Optional[str] = None


class ForwardEmailRequest(BaseModel):
    """转发邮件"""
    email_id: str
    to: List[str]
    body: Optional[str] = None
    folder: str = "INBOX"
    include_attachments: bool = True
    account_id: Optional[str] = None


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


@app.post("/api/check-emails", response_model=CheckEmailsResponse, dependencies=[Depends(verify_api_key)])
async def check_emails():
    """
    检查邮件并返回重要邮件 (需要 API Key)
    
    这个接口会：
    1. 获取未读邮件
    2. AI 过滤重要邮件
    3. 返回结果和通知内容
    
    认证: 需要在 Header 中提供 X-API-Key
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


@app.post("/api/get-email-detail", dependencies=[Depends(verify_api_key)])
async def get_email_detail(req: EmailDetailRequest):
    """
    获取单封邮件的完整内容 (需要 API Key)

    Body:
        email_id: 邮件 UID
        account_id: 可选，指定账户 ID/邮箱
        folder: 可选，默认 INBOX
    """
    try:
        from src.account_manager import AccountManager
        from src.services.email_service import EmailService

        svc = EmailService(AccountManager())
        result = await asyncio.to_thread(
            svc.get_email_detail,
            email_id=req.email_id,
            folder=req.folder,
            account_id=req.account_id,
            message_id=req.message_id,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("获取邮件详情时发生错误: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get email detail: {str(e)}")


@app.get("/api/list-accounts", dependencies=[Depends(verify_api_key)])
async def list_accounts():
    """列出所有已配置账户"""
    try:
        from src.account_manager import AccountManager

        mgr = AccountManager()
        accounts = mgr.list_accounts()
        return JSONResponse(
            content={"success": True, "accounts": accounts, "count": len(accounts)},
            status_code=200,
        )
    except Exception as e:
        logger.error("列出账户失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/list-unread-folders", dependencies=[Depends(verify_api_key)])
async def list_unread_folders(
    account_id: Optional[str] = None,
    include_empty: bool = True,
):
    """列出文件夹及未读数"""
    try:
        from src.account_manager import AccountManager
        from src.services.folder_service import FolderService

        svc = FolderService(AccountManager())
        result = await asyncio.to_thread(
            svc.list_folders_with_unread_count,
            account_id=account_id,
            include_empty=include_empty,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("列出文件夹失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/list-emails", dependencies=[Depends(verify_api_key)])
async def list_emails(req: ListEmailsRequest):
    """获取邮件列表"""
    try:
        from src.account_manager import AccountManager
        from src.services.email_service import EmailService

        svc = EmailService(AccountManager())
        result = await asyncio.to_thread(
            svc.list_emails,
            limit=req.limit,
            unread_only=req.unread_only,
            folder=req.folder,
            account_id=req.account_id,
            offset=req.offset,
            include_metadata=req.include_metadata,
            use_cache=req.use_cache,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("获取邮件列表失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/mark-emails", dependencies=[Depends(verify_api_key)])
async def mark_emails(req: MarkEmailsRequest):
    """标记邮件已读/未读"""
    try:
        from src.account_manager import AccountManager
        from src.services.email_service import EmailService

        svc = EmailService(AccountManager())
        result = await asyncio.to_thread(
            svc.mark_emails,
            email_ids=req.email_ids,
            mark_as=req.mark_as,
            folder=req.folder,
            account_id=req.account_id,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("标记邮件失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/delete-emails", dependencies=[Depends(verify_api_key)])
async def delete_emails(req: DeleteEmailsRequest):
    """删除邮件或移入垃圾箱"""
    try:
        from src.account_manager import AccountManager
        from src.services.email_service import EmailService

        svc = EmailService(AccountManager())
        result = await asyncio.to_thread(
            svc.delete_emails,
            email_ids=req.email_ids,
            folder=req.folder,
            permanent=req.permanent,
            trash_folder=req.trash_folder,
            account_id=req.account_id,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("删除邮件失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/move-emails", dependencies=[Depends(verify_api_key)])
async def move_emails(req: MoveEmailsRequest):
    """移动邮件到指定文件夹"""
    try:
        from src.account_manager import AccountManager
        from src.services.folder_service import FolderService

        svc = FolderService(AccountManager())
        result = await asyncio.to_thread(
            svc.move_emails_to_folder,
            email_ids=req.email_ids,
            target_folder=req.target_folder,
            source_folder=req.source_folder,
            account_id=req.account_id,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("移动邮件失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/send-email", dependencies=[Depends(verify_api_key)])
async def send_email(req: SendEmailRequest):
    """发送新邮件"""
    try:
        from src.account_manager import AccountManager
        from src.services.communication_service import CommunicationService

        svc = CommunicationService(AccountManager())
        result = await asyncio.to_thread(
            svc.send_email,
            to=req.to,
            subject=req.subject,
            body=req.body,
            cc=req.cc,
            bcc=req.bcc,
            attachments=req.attachments,
            is_html=req.is_html,
            account_id=req.account_id,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("发送邮件失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reply-email", dependencies=[Depends(verify_api_key)])
async def reply_email(req: ReplyEmailRequest):
    """回复邮件"""
    try:
        from src.account_manager import AccountManager
        from src.services.communication_service import CommunicationService

        svc = CommunicationService(AccountManager())
        result = await asyncio.to_thread(
            svc.reply_email,
            email_id=req.email_id,
            body=req.body,
            reply_all=req.reply_all,
            folder=req.folder,
            attachments=req.attachments,
            is_html=req.is_html,
            account_id=req.account_id,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("回复邮件失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forward-email", dependencies=[Depends(verify_api_key)])
async def forward_email(req: ForwardEmailRequest):
    """转发邮件"""
    try:
        from src.account_manager import AccountManager
        from src.services.communication_service import CommunicationService

        svc = CommunicationService(AccountManager())
        result = await asyncio.to_thread(
            svc.forward_email,
            email_id=req.email_id,
            to=req.to,
            body=req.body,
            folder=req.folder,
            include_attachments=req.include_attachments,
            account_id=req.account_id,
        )
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        logger.error("转发邮件失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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


@app.post("/api/organize-inbox", dependencies=[Depends(verify_api_key)])
async def organize_inbox(
    limit: int = 15,
    unread_only: bool = False,
    folder: str = "INBOX",
    account_id: Optional[str] = None,
):
    """
    对最近的邮件进行整理分析，返回分类与摘要建议。

    Query 参数:
        limit: 分析的邮件数量
        unread_only: 是否仅分析未读邮件
        folder: 邮件文件夹（默认 INBOX）
        account_id: 指定账号 ID 或邮箱地址
    """
    try:
        logger.info(
            "开始整理邮件: limit=%s unread_only=%s folder=%s account_id=%s",
            limit,
            unread_only,
            folder,
            account_id,
        )

        from scripts.inbox_organizer import InboxOrganizer

        organizer = InboxOrganizer(
            limit=limit,
            folder=folder,
            unread_only=unread_only,
            account_id=account_id,
        )
        result = await asyncio.to_thread(organizer.organize)

        return JSONResponse(content=result, status_code=200)

    except Exception as e:
        logger.error("整理邮件时发生错误: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"整理邮件失败: {str(e)}"
        )


@app.post("/api/translate-unread", dependencies=[Depends(verify_api_key)])
async def translate_unread_emails():
    """
    获取未读邮件、翻译成中文、生成摘要 (需要 API Key)
    
    工作流程：
    1. 获取所有未读邮件
    2. 对非中文邮件进行翻译
    3. 生成中文摘要
    4. 返回翻译后的内容和邮件 ID（用于标记已读）
    
    认证: 需要在 Header 中提供 X-API-Key
    """
    try:
        logger.info("开始获取和翻译未读邮件...")
        
        # 1. 获取未读邮件
        from scripts.call_email_tool import run as call_email_tool
        
        fetch_result = await asyncio.to_thread(
            call_email_tool,
            "list_emails",
            json.dumps({"unread_only": True, "limit": 20})
        )
        
        if not fetch_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"获取邮件失败: {fetch_result.get('error')}"
            )
        
        emails = fetch_result.get("emails", [])
        logger.info(f"获取到 {len(emails)} 封未读邮件")
        
        if len(emails) == 0:
            return JSONResponse(
                content={
                    "success": True,
                    "message": "没有未读邮件",
                    "count": 0,
                    "summary": "📭 暂无未读邮件",
                    "email_ids": [],
                    "lark_message": {
                        "msg_type": "text",
                        "content": {
                            "text": "📭 暂无未读邮件"
                        }
                    }
                },
                status_code=200
            )
        
        # 2. 翻译和总结
        from scripts.email_translator import EmailTranslator
        
        translator = EmailTranslator()
        translation_result = await asyncio.to_thread(
            translator.translate_and_summarize,
            emails
        )
        
        if not translation_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"翻译失败: {translation_result.get('error')}"
            )
        
        # 3. 构建 Lark 消息
        summary = translation_result.get("summary", "")
        processed_emails = translation_result.get("emails", [])
        email_ids = [e.get("id") for e in processed_emails if e.get("id")]
        
        lark_message = {
            "msg_type": "text",
            "content": {
                "text": f"📬 未读邮件摘要\n\n{summary}"
            }
        }
        
        logger.info(f"翻译总结完成，共 {len(processed_emails)} 封邮件")
        
        return JSONResponse(
            content={
                "success": True,
                "message": "翻译总结完成",
                "count": len(processed_emails),
                "summary": summary,
                "emails": processed_emails,
                "email_ids": email_ids,
                "lark_message": lark_message
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"处理未读邮件时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"处理失败: {str(e)}"
        )


@app.post("/api/mark-read", dependencies=[Depends(verify_api_key)])
async def mark_emails_as_read(email_ids: List[str]):
    """
    标记邮件为已读 (需要 API Key)
    
    Args:
        email_ids: 邮件 ID 列表
        
    Returns:
        {
            "success": bool,
            "marked_count": int,
            "email_ids": List[str]
        }
    
    认证: 需要在 Header 中提供 X-API-Key
    """
    try:
        logger.info(f"标记 {len(email_ids)} 封邮件为已读...")
        
        from scripts.call_email_tool import run as call_email_tool
        
        # 批量标记已读
        result = await asyncio.to_thread(
            call_email_tool,
            "mark_read",
            json.dumps({"email_ids": email_ids})
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"标记已读失败: {result.get('error')}"
            )
        
        marked_count = result.get("marked_count", len(email_ids))
        logger.info(f"成功标记 {marked_count} 封邮件为已读")
        
        return JSONResponse(
            content={
                "success": True,
                "message": f"成功标记 {marked_count} 封邮件为已读",
                "marked_count": marked_count,
                "email_ids": email_ids
            },
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"标记已读时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"标记已读失败: {str(e)}"
        )


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
