"""
Multi-language message support for MCP Email Service
"""
import os
from typing import Dict, Any

# Multi-language message dictionary
MESSAGES: Dict[str, Dict[str, str]] = {
    'zh': {
        'no_email': '📭 没有找到邮件',
        'email_sent': '✅ 邮件发送成功，已发送给 {} 个收件人',
        'error': '❌ 错误：',
        'operation_failed': '❌ 操作失败：',
        'operation_success': '✅ 操作成功完成',
        'found_emails': '📧 找到 {} 封邮件 (总计 {} 封，未读 {} 封)',
        'from_accounts': '📊 来自 {} 个邮箱账户',
        'unread_mark': '🔴 ',
        'read_mark': '📧 ',
        'from': '📤 ',
        'date': '📅 ',
        'id': '🆔 ',
        'account': '📮 ',
        'fetch_time': '⏱️ 获取耗时：{:.2f} 秒',
        'failed_accounts': '⚠️ 部分账户获取失败：',
        'account_stats': '📊 各账户统计：',
        'emails_count': '{} 封 (总 {}, 未读 {})',
        'found_folders': '📁 找到 {} 个文件夹',
        'messages': '条消息'
    },
    'en': {
        'no_email': '📭 No emails found',
        'email_sent': '✅ Email sent successfully to {} recipient(s)',
        'error': '❌ Error: ',
        'operation_failed': '❌ Operation failed: ',
        'operation_success': '✅ Operation completed successfully',
        'found_emails': '📧 Found {} emails (total: {}, unread: {})',
        'from_accounts': '📊 From {} email accounts',
        'unread_mark': '🔴 ',
        'read_mark': '📧 ',
        'from': '📤 ',
        'date': '📅 ',
        'id': '🆔 ',
        'account': '📮 ',
        'fetch_time': '⏱️ Fetch time: {:.2f} seconds',
        'failed_accounts': '⚠️ Failed to fetch from some accounts:',
        'account_stats': '📊 Account statistics:',
        'emails_count': '{} emails (total: {}, unread: {})',
        'found_folders': '📁 Found {} folders',
        'messages': 'messages'
    }
}


def get_user_language() -> str:
    """
    Get user's preferred language from environment or default to English
    
    Returns:
        Language code ('en', 'zh', etc.)
    """
    lang = os.getenv('MCP_LANGUAGE', 'en')
    return lang


def get_message(key: str, *args, **kwargs) -> str:
    """
    Get localized message by key
    
    Args:
        key: Message key to lookup
        *args: Positional arguments for string formatting
        **kwargs: Keyword arguments for string formatting
        
    Returns:
        Formatted localized message string
    """
    lang = get_user_language()
    messages = MESSAGES.get(lang, MESSAGES['en'])
    msg = messages.get(key, key)
    
    if args or kwargs:
        return msg.format(*args, **kwargs)
    return msg

