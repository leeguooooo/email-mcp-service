#!/usr/bin/env python3
"""
邮件翻译和总结服务
使用 OpenAI 将非中文邮件翻译成中文并生成摘要
"""
import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

logger = logging.getLogger(__name__)


class EmailTranslator:
    """邮件翻译和总结器"""
    
    def __init__(self):
        """初始化翻译器"""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("⚠️  OPENAI_API_KEY 未设置，翻译功能将不可用")
    
    def detect_language(self, text: str) -> str:
        """简单的语言检测"""
        # 检查是否包含中文字符
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        total_chars = len(text.strip())
        
        if total_chars == 0:
            return "unknown"
        
        # 如果超过 30% 是中文，认为是中文
        if chinese_chars / total_chars > 0.3:
            return "zh"
        return "other"
    
    def translate_and_summarize(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        翻译并总结邮件
        
        Args:
            emails: 邮件列表，每封邮件包含 id, from, subject, body 等
            
        Returns:
            {
                "success": bool,
                "summary": str,  # 总体摘要（中文）
                "emails": [      # 处理后的邮件
                    {
                        "id": str,
                        "from": str,
                        "subject": str,
                        "subject_zh": str,  # 中文主题
                        "summary_zh": str,  # 中文摘要
                        "is_chinese": bool
                    }
                ]
            }
        """
        if not self.openai_api_key:
            return {
                "success": False,
                "error": "OpenAI API Key 未设置",
                "summary": "⚠️ 翻译服务不可用",
                "emails": []
            }
        
        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            # 准备邮件数据
            processed_emails = []
            for email in emails:
                subject = email.get('subject', '')
                body = email.get('body', '')[:500]  # 限制正文长度
                from_addr = email.get('from', '')
                
                # 检测语言
                is_chinese = self.detect_language(subject + body) == "zh"
                
                email_data = {
                    "id": email.get('id'),
                    "from": from_addr,
                    "subject": subject,
                    "is_chinese": is_chinese
                }
                
                # 如果不是中文，需要翻译
                if not is_chinese:
                    # 构建翻译提示词
                    prompt = f"""请将以下邮件翻译成中文，并提供简短摘要（不超过100字）：

发件人: {from_addr}
主题: {subject}
内容: {body}

请以 JSON 格式返回：
{{
  "subject_zh": "中文主题",
  "summary_zh": "中文摘要"
}}"""
                    
                    try:
                        response = client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "你是一个专业的邮件翻译和摘要助手。"},
                                {"role": "user", "content": prompt}
                            ],
                            temperature=0.3,
                            max_tokens=500
                        )
                        
                        result_text = response.choices[0].message.content.strip()
                        
                        # 尝试解析 JSON
                        try:
                            # 提取 JSON
                            if "```json" in result_text:
                                result_text = result_text.split("```json")[1].split("```")[0]
                            elif "```" in result_text:
                                result_text = result_text.split("```")[1].split("```")[0]
                            
                            result = json.loads(result_text.strip())
                            email_data["subject_zh"] = result.get("subject_zh", subject)
                            email_data["summary_zh"] = result.get("summary_zh", "翻译失败")
                        except json.JSONDecodeError:
                            # 如果不是 JSON，直接使用返回的文本
                            email_data["subject_zh"] = subject
                            email_data["summary_zh"] = result_text[:200]
                        
                    except Exception as e:
                        logger.error(f"翻译邮件失败: {e}")
                        email_data["subject_zh"] = subject
                        email_data["summary_zh"] = f"⚠️ 翻译失败: {str(e)}"
                else:
                    # 中文邮件，直接用原文
                    email_data["subject_zh"] = subject
                    email_data["summary_zh"] = body[:100] + "..." if len(body) > 100 else body
                
                processed_emails.append(email_data)
            
            # 生成总体摘要
            summary_parts = [f"📧 共 {len(processed_emails)} 封未读邮件\n"]
            for i, email in enumerate(processed_emails, 1):
                summary_parts.append(
                    f"{i}. {email['subject_zh']}\n"
                    f"   发件人: {email['from']}\n"
                    f"   摘要: {email['summary_zh']}\n"
                )
            
            return {
                "success": True,
                "summary": "\n".join(summary_parts),
                "emails": processed_emails
            }
            
        except Exception as e:
            logger.error(f"翻译总结失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "summary": f"⚠️ 翻译总结失败: {e}",
                "emails": []
            }


def main():
    """测试"""
    translator = EmailTranslator()
    
    # 测试邮件
    test_emails = [
        {
            "id": "1",
            "from": "test@example.com",
            "subject": "Hello World",
            "body": "This is a test email."
        },
        {
            "id": "2",
            "from": "测试@example.com",
            "subject": "测试邮件",
            "body": "这是一封中文测试邮件。"
        }
    ]
    
    result = translator.translate_and_summarize(test_emails)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

