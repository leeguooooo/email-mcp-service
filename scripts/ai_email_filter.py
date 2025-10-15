#!/usr/bin/env python3
"""
AI 邮件过滤服务 - 使用 AI 判断邮件重要性
支持多种 AI 提供商：OpenAI, Anthropic, 本地模型等
"""
import json
import sys
import os
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from pathlib import Path

# 添加项目根目录到 Python 路径
repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

# 配置日志
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


@dataclass
class EmailContent:
    """邮件内容结构"""
    email_id: str
    subject: str
    sender: str
    date: str
    body_preview: str = ""
    has_attachments: bool = False
    folder: str = "INBOX"
    account_id: Optional[str] = None


@dataclass
class FilterResult:
    """过滤结果结构"""
    email_id: str
    is_important: bool
    priority_score: float  # 0-1 之间的重要性评分
    reason: str
    category: str = "general"  # 邮件分类：urgent, work, personal, spam, etc.
    suggested_action: str = "none"  # 建议操作：reply, forward, archive, etc.


class AIEmailFilter:
    """AI 邮件过滤器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 AI 过滤器
        
        Args:
            config_path: 配置文件路径，默认为 ai_filter_config.json
        """
        self.config_path = config_path or "ai_filter_config.json"
        self.config = self._load_config()
        self.ai_client = self._init_ai_client()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "ai_provider": "openai",  # openai, anthropic, local
            "model": "gpt-3.5-turbo",
            "api_key_env": "OPENAI_API_KEY",
            "base_url": None,
            "priority_threshold": 0.7,  # 重要性阈值
            "max_body_length": 500,  # 发送给 AI 的邮件正文最大长度
            "filter_rules": {
                "high_priority_senders": [],  # 高优先级发件人
                "high_priority_keywords": ["urgent", "important", "asap", "紧急", "重要"],
                "low_priority_keywords": ["newsletter", "promotion", "unsubscribe", "广告", "推广"],
                "spam_indicators": ["lottery", "winner", "congratulations", "中奖", "恭喜"]
            },
            "categories": {
                "work": ["meeting", "project", "deadline", "会议", "项目", "截止"],
                "personal": ["family", "friend", "birthday", "家人", "朋友", "生日"],
                "finance": ["invoice", "payment", "bank", "发票", "付款", "银行"],
                "urgent": ["urgent", "emergency", "asap", "紧急", "急"]
            }
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
            except Exception as e:
                logger.warning(f"Failed to load config from {self.config_path}: {e}")
        else:
            # 创建默认配置文件
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
                logger.info(f"Created default config at {self.config_path}")
            except Exception as e:
                logger.warning(f"Failed to create config file: {e}")
        
        return default_config
    
    def _init_ai_client(self):
        """初始化 AI 客户端"""
        provider = self.config.get("ai_provider", "openai")
        
        if provider == "openai":
            try:
                import openai
                api_key = os.getenv(self.config.get("api_key_env", "OPENAI_API_KEY"))
                if not api_key:
                    raise ValueError(f"API key not found in environment variable: {self.config.get('api_key_env')}")
                
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=self.config.get("base_url")
                )
                return client
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        elif provider == "anthropic":
            try:
                import anthropic
                api_key = os.getenv(self.config.get("api_key_env", "ANTHROPIC_API_KEY"))
                if not api_key:
                    raise ValueError(f"API key not found in environment variable: {self.config.get('api_key_env')}")
                
                client = anthropic.Anthropic(api_key=api_key)
                return client
            except ImportError:
                raise ImportError("Anthropic library not installed. Run: pip install anthropic")
        
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")
    
    def _create_filter_prompt(self, email: EmailContent) -> str:
        """创建过滤提示词"""
        categories = list(self.config.get("categories", {}).keys())
        
        prompt = f"""
请分析以下邮件并判断其重要性：

邮件信息：
- 发件人：{email.sender}
- 主题：{email.subject}
- 日期：{email.date}
- 正文预览：{email.body_preview[:self.config.get('max_body_length', 500)]}
- 有附件：{'是' if email.has_attachments else '否'}

请根据以下标准评估邮件：
1. 紧急程度（是否需要立即处理）
2. 重要性（对收件人的重要程度）
3. 发件人的重要性
4. 内容的相关性

请以 JSON 格式返回结果：
{{
    "is_important": true/false,
    "priority_score": 0.0-1.0,
    "reason": "判断理由",
    "category": "{'/'.join(categories)}中的一个或general",
    "suggested_action": "reply/forward/archive/none"
}}

重要邮件的特征：
- 来自重要联系人或机构
- 包含紧急、重要等关键词
- 工作相关的会议、项目、截止日期
- 财务相关的账单、发票
- 个人重要事务

不重要邮件的特征：
- 营销推广邮件
- 新闻订阅
- 自动通知
- 垃圾邮件

请仅返回 JSON，不要包含其他内容。
"""
        return prompt.strip()
    
    def _call_ai_api(self, prompt: str) -> Dict[str, Any]:
        """调用 AI API"""
        provider = self.config.get("ai_provider", "openai")
        model = self.config.get("model", "gpt-3.5-turbo")
        
        try:
            if provider == "openai":
                response = self.ai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的邮件过滤助手，能够准确判断邮件的重要性。请严格按照要求返回 JSON 格式的结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=300
                )
                content = response.choices[0].message.content.strip()
                
            elif provider == "anthropic":
                response = self.ai_client.messages.create(
                    model=model,
                    max_tokens=300,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                content = response.content[0].text.strip()
            
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            
            # 尝试解析 JSON
            try:
                # 提取 JSON 部分（去除可能的前后文）
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    return json.loads(json_str)
                else:
                    raise ValueError("No JSON found in response")
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse AI response as JSON: {content}")
                return self._fallback_analysis(content)
                
        except Exception as e:
            logger.error(f"AI API call failed: {e}")
            raise
    
    def _fallback_analysis(self, ai_response: str) -> Dict[str, Any]:
        """AI 响应解析失败时的回退分析"""
        # 基于关键词的简单分析
        response_lower = ai_response.lower()
        
        is_important = any(word in response_lower for word in ["important", "urgent", "high", "重要", "紧急"])
        priority_score = 0.8 if is_important else 0.3
        
        return {
            "is_important": is_important,
            "priority_score": priority_score,
            "reason": "AI 响应解析失败，使用关键词分析",
            "category": "general",
            "suggested_action": "none"
        }
    
    def _rule_based_filter(self, email: EmailContent) -> Optional[FilterResult]:
        """基于规则的预过滤"""
        rules = self.config.get("filter_rules", {})
        
        # 检查高优先级发件人
        high_priority_senders = rules.get("high_priority_senders", [])
        for sender in high_priority_senders:
            if sender.lower() in email.sender.lower():
                return FilterResult(
                    email_id=email.email_id,
                    is_important=True,
                    priority_score=0.9,
                    reason=f"来自高优先级发件人: {sender}",
                    category="work"
                )
        
        # 检查垃圾邮件指标
        spam_indicators = rules.get("spam_indicators", [])
        text_to_check = f"{email.subject} {email.body_preview}".lower()
        for indicator in spam_indicators:
            if indicator.lower() in text_to_check:
                return FilterResult(
                    email_id=email.email_id,
                    is_important=False,
                    priority_score=0.1,
                    reason=f"包含垃圾邮件指标: {indicator}",
                    category="spam"
                )
        
        # 检查高优先级关键词
        high_priority_keywords = rules.get("high_priority_keywords", [])
        for keyword in high_priority_keywords:
            if keyword.lower() in text_to_check:
                return FilterResult(
                    email_id=email.email_id,
                    is_important=True,
                    priority_score=0.8,
                    reason=f"包含高优先级关键词: {keyword}",
                    category="urgent"
                )
        
        return None
    
    def filter_email(self, email: EmailContent) -> FilterResult:
        """过滤单个邮件"""
        # 首先尝试基于规则的过滤
        rule_result = self._rule_based_filter(email)
        if rule_result:
            return rule_result
        
        # 使用 AI 分析
        try:
            prompt = self._create_filter_prompt(email)
            ai_result = self._call_ai_api(prompt)
            
            return FilterResult(
                email_id=email.email_id,
                is_important=ai_result.get("is_important", False),
                priority_score=float(ai_result.get("priority_score", 0.5)),
                reason=ai_result.get("reason", "AI 分析结果"),
                category=ai_result.get("category", "general"),
                suggested_action=ai_result.get("suggested_action", "none")
            )
            
        except Exception as e:
            logger.error(f"AI filtering failed for email {email.email_id}: {e}")
            # 回退到基于关键词的简单分析
            return self._simple_keyword_filter(email)
    
    def _simple_keyword_filter(self, email: EmailContent) -> FilterResult:
        """简单的关键词过滤（AI 失败时的回退方案）"""
        text_to_check = f"{email.subject} {email.body_preview}".lower()
        
        # 检查重要关键词
        important_keywords = ["urgent", "important", "meeting", "deadline", "紧急", "重要", "会议", "截止"]
        importance_score = sum(1 for keyword in important_keywords if keyword in text_to_check)
        
        # 检查不重要关键词
        unimportant_keywords = ["newsletter", "promotion", "unsubscribe", "广告", "推广"]
        unimportance_score = sum(1 for keyword in unimportant_keywords if keyword in text_to_check)
        
        priority_score = max(0.1, min(0.9, 0.5 + (importance_score - unimportance_score) * 0.2))
        is_important = priority_score >= self.config.get("priority_threshold", 0.7)
        
        return FilterResult(
            email_id=email.email_id,
            is_important=is_important,
            priority_score=priority_score,
            reason="基于关键词的简单分析",
            category="general"
        )
    
    def filter_emails(self, emails: List[Dict[str, Any]]) -> List[FilterResult]:
        """批量过滤邮件"""
        results = []
        
        for email_data in emails:
            try:
                email = EmailContent(
                    email_id=email_data.get("id", ""),
                    subject=email_data.get("subject", ""),
                    sender=email_data.get("from", ""),
                    date=email_data.get("date", ""),
                    body_preview=email_data.get("body_preview", email_data.get("body", ""))[:500],
                    has_attachments=email_data.get("has_attachments", False),
                    folder=email_data.get("folder", "INBOX"),
                    account_id=email_data.get("account_id")
                )
                
                result = self.filter_email(email)
                results.append(result)
                
            except Exception as e:
                logger.error(f"Failed to filter email {email_data.get('id', 'unknown')}: {e}")
                # 添加失败的结果
                results.append(FilterResult(
                    email_id=email_data.get("id", "unknown"),
                    is_important=False,
                    priority_score=0.5,
                    reason=f"过滤失败: {str(e)}",
                    category="error"
                ))
        
        return results


def main():
    """主函数 - 命令行接口"""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python ai_email_filter.py <emails_json> [config_path]",
            "example": {
                "emails": [
                    {
                        "id": "email_123",
                        "subject": "Urgent: Meeting Tomorrow",
                        "from": "boss@company.com",
                        "date": "2024-01-15",
                        "body_preview": "We need to discuss the project deadline...",
                        "has_attachments": False
                    }
                ]
            }
        }))
        sys.exit(1)
    
    emails_json = sys.argv[1]
    config_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # 解析邮件数据
        if emails_json.startswith('[') or emails_json.startswith('{'):
            emails_data = json.loads(emails_json)
        else:
            # 假设是文件路径
            with open(emails_json, 'r', encoding='utf-8') as f:
                emails_data = json.load(f)
        
        # 确保是列表格式
        if isinstance(emails_data, dict):
            if 'emails' in emails_data:
                emails_data = emails_data['emails']
            else:
                emails_data = [emails_data]
        
        # 创建过滤器并处理
        filter_service = AIEmailFilter(config_path)
        results = filter_service.filter_emails(emails_data)
        
        # 输出结果
        output = {
            "success": True,
            "total_emails": len(emails_data),
            "important_emails": sum(1 for r in results if r.is_important),
            "results": [
                {
                    "email_id": r.email_id,
                    "is_important": r.is_important,
                    "priority_score": r.priority_score,
                    "reason": r.reason,
                    "category": r.category,
                    "suggested_action": r.suggested_action
                }
                for r in results
            ]
        }
        
        print(json.dumps(output, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "success": False
        }))
        sys.exit(1)


if __name__ == "__main__":
    main()
