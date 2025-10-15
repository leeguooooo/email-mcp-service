#!/usr/bin/env python3
"""
测试飞书 webhook 的脚本
"""
import json
import sys
import requests
from pathlib import Path

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

def test_lark_webhook():
    """测试飞书 webhook"""
    webhook_url = "https://open.larksuite.com/open-apis/bot/v2/hook/a56c9638-cb65-4f95-bb11-9eb19e09692a"
    
    # 测试不同的消息格式
    test_messages = [
        {
            "name": "简单文本消息",
            "payload": {
                "msg_type": "text",
                "content": {
                    "text": "📧 测试消息\n\n这是一个来自 MCP 邮件监控系统的测试通知。\n\n如果你收到这条消息，说明 webhook 配置成功！"
                }
            }
        },
        {
            "name": "Markdown 消息",
            "payload": {
                "msg_type": "interactive",
                "card": {
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "content": "**📧 重要邮件提醒**\n\n**主题**: 测试邮件主题\n**发件人**: test@example.com\n**时间**: 2024-01-15 10:30:00\n**重要性**: 85%\n**分类**: 测试\n\n**分析原因**: 这是一个测试消息\n\n**预览**: 这是邮件内容的预览...\n\n**建议**: 查看详情",
                                "tag": "lark_md"
                            }
                        }
                    ],
                    "header": {
                        "title": {
                            "content": "📧 重要邮件测试",
                            "tag": "plain_text"
                        },
                        "template": "red"
                    }
                }
            }
        }
    ]
    
    headers = {
        "Content-Type": "application/json"
    }
    
    for test in test_messages:
        print(f"\n🧪 测试: {test['name']}")
        print(f"📤 发送消息...")
        
        try:
            response = requests.post(
                webhook_url,
                json=test['payload'],
                headers=headers,
                timeout=10
            )
            
            print(f"📊 状态码: {response.status_code}")
            print(f"📄 响应: {response.text}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("code") == 0:
                        print("✅ 发送成功!")
                    else:
                        print(f"❌ 发送失败: {result}")
                except json.JSONDecodeError:
                    print("✅ 发送成功 (无 JSON 响应)")
            else:
                print(f"❌ HTTP 错误: {response.status_code}")
                
        except Exception as e:
            print(f"❌ 请求失败: {e}")
        
        print("-" * 50)

def test_with_notification_service():
    """使用通知服务测试"""
    print("\n🔧 使用通知服务测试...")
    
    # 创建测试通知数据
    test_notification = {
        "email_id": "test_lark_123",
        "subject": "重要会议提醒",
        "sender": "boss@company.com", 
        "date": "2024-01-15 14:30:00",
        "priority_score": 0.85,
        "reason": "来自重要联系人的会议邀请",
        "category": "work",
        "account_id": "default",
        "body_preview": "明天下午2点有重要项目会议，请准时参加...",
        "suggested_action": "reply"
    }
    
    try:
        from scripts.notification_service import NotificationService
        
        # 使用飞书配置
        service = NotificationService("lark_webhook_config.json")
        
        # 发送测试通知
        from scripts.notification_service import EmailNotification
        notification = EmailNotification(**test_notification)
        
        results = service.send_notification(notification)
        
        print(f"📊 发送结果: {results}")
        
        if any(results.values()):
            print("✅ 通知服务测试成功!")
        else:
            print("❌ 通知服务测试失败")
            
    except Exception as e:
        print(f"❌ 通知服务测试失败: {e}")

if __name__ == "__main__":
    print("🚀 开始测试飞书 webhook...")
    
    # 直接 HTTP 测试
    test_lark_webhook()
    
    # 通知服务测试
    test_with_notification_service()
    
    print("\n✅ 测试完成!")
    print("\n💡 如果测试成功，你可以:")
    print("1. 将 webhook URL 添加到 notification_config.json")
    print("2. 在 n8n 工作流中使用这个配置")
    print("3. 开始享受自动邮件通知!")
