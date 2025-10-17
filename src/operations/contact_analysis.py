"""
联系人频率分析模块
"""
import sqlite3
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import Counter
import json

from ..config.paths import EMAIL_SYNC_DB

logger = logging.getLogger(__name__)


class ContactAnalyzer:
    """联系人频率分析器"""
    
    def __init__(self, db_path: str = None):
        """初始化分析器"""
        self.db_path = db_path or EMAIL_SYNC_DB
    
    def analyze_contacts(
        self,
        account_id: Optional[str] = None,
        days: int = 30,
        limit: int = 10,
        group_by: str = "both"  # sender, recipient, both
    ) -> Dict[str, Any]:
        """
        分析联系人频率
        
        Args:
            account_id: 账户ID，None表示分析所有账户
            days: 分析最近N天的数据
            limit: 返回Top N联系人
            group_by: 分组方式（sender/recipient/both）
        
        Returns:
            分析结果字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            # 计算时间范围
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_date_str = cutoff_date.isoformat()
            
            # 构建查询条件
            where_clauses = ["date_sent >= ?", "is_deleted = FALSE"]
            params = [cutoff_date_str]
            
            if account_id:
                where_clauses.append("account_id = ?")
                params.append(account_id)
            
            where_sql = " AND ".join(where_clauses)
            
            # 查询邮件数据
            query = f"""
                SELECT sender_email, recipients
                FROM emails
                WHERE {where_sql}
            """
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            # 统计发件人和收件人频率
            sender_counter = Counter()
            recipient_counter = Counter()
            
            for row in rows:
                sender = row['sender_email']
                if sender:
                    sender_counter[sender.lower()] += 1
                
                # 解析收件人（JSON格式）
                recipients_json = row['recipients']
                if recipients_json:
                    try:
                        recipients = json.loads(recipients_json)
                        if isinstance(recipients, list):
                            for recipient in recipients:
                                if recipient:
                                    recipient_counter[recipient.lower()] += 1
                    except json.JSONDecodeError:
                        # 如果不是JSON，可能是逗号分隔的字符串
                        recipients = recipients_json.split(',')
                        for recipient in recipients:
                            recipient = recipient.strip()
                            if recipient:
                                recipient_counter[recipient.lower()] += 1
            
            # 准备结果
            result = {
                "analysis_period": {
                    "days": days,
                    "start_date": cutoff_date_str,
                    "end_date": datetime.now().isoformat()
                },
                "account_id": account_id or "all_accounts",
                "total_emails_analyzed": len(rows),
            }
            
            # 根据 group_by 返回结果
            if group_by in ["sender", "both"]:
                top_senders = sender_counter.most_common(limit)
                result["top_senders"] = [
                    {
                        "email": email,
                        "count": count,
                        "percentage": round(count / len(rows) * 100, 2) if rows else 0
                    }
                    for email, count in top_senders
                ]
            
            if group_by in ["recipient", "both"]:
                top_recipients = recipient_counter.most_common(limit)
                result["top_recipients"] = [
                    {
                        "email": email,
                        "count": count,
                        "percentage": round(count / len(rows) * 100, 2) if rows else 0
                    }
                    for email, count in top_recipients
                ]
            
            # 添加统计摘要
            result["summary"] = {
                "unique_senders": len(sender_counter),
                "unique_recipients": len(recipient_counter),
                "avg_emails_per_sender": round(sum(sender_counter.values()) / len(sender_counter), 2) if sender_counter else 0,
                "avg_emails_per_recipient": round(sum(recipient_counter.values()) / len(recipient_counter), 2) if recipient_counter else 0
            }
            
            conn.close()
            return result
            
        except sqlite3.Error as e:
            logger.error(f"Database error in contact analysis: {e}")
            return {
                "error": f"Database error: {str(e)}",
                "account_id": account_id or "all_accounts"
            }
        except Exception as e:
            logger.error(f"Error analyzing contacts: {e}")
            return {
                "error": f"Analysis error: {str(e)}",
                "account_id": account_id or "all_accounts"
            }
    
    def get_contact_timeline(
        self,
        contact_email: str,
        account_id: Optional[str] = None,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        获取特定联系人的沟通时间线
        
        Args:
            contact_email: 联系人邮箱
            account_id: 账户ID
            days: 时间范围
        
        Returns:
            时间线数据
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_date_str = cutoff_date.isoformat()
            
            where_clauses = [
                "date_sent >= ?",
                "is_deleted = FALSE",
                "(sender_email = ? OR recipients LIKE ?)"
            ]
            params = [cutoff_date_str, contact_email.lower(), f"%{contact_email.lower()}%"]
            
            if account_id:
                where_clauses.append("account_id = ?")
                params.append(account_id)
            
            where_sql = " AND ".join(where_clauses)
            
            query = f"""
                SELECT 
                    date_sent,
                    subject,
                    sender_email,
                    is_read
                FROM emails
                WHERE {where_sql}
                ORDER BY date_sent DESC
                LIMIT 100
            """
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            timeline = []
            for row in rows:
                timeline.append({
                    "date": row['date_sent'],
                    "subject": row['subject'],
                    "direction": "received" if row['sender_email'].lower() == contact_email.lower() else "sent",
                    "is_read": bool(row['is_read'])
                })
            
            result = {
                "contact_email": contact_email,
                "account_id": account_id or "all_accounts",
                "total_interactions": len(timeline),
                "timeline": timeline
            }
            
            conn.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting contact timeline: {e}")
            return {
                "error": f"Timeline error: {str(e)}",
                "contact_email": contact_email
            }


def analyze_contacts(
    account_id: Optional[str] = None,
    days: int = 30,
    limit: int = 10,
    group_by: str = "both"
) -> Dict[str, Any]:
    """
    分析联系人频率（便捷函数）
    
    Args:
        account_id: 账户ID
        days: 分析天数
        limit: Top N
        group_by: 分组方式
    
    Returns:
        分析结果
    """
    analyzer = ContactAnalyzer()
    return analyzer.analyze_contacts(account_id, days, limit, group_by)


def get_contact_timeline(
    contact_email: str,
    account_id: Optional[str] = None,
    days: int = 90
) -> Dict[str, Any]:
    """
    获取联系人时间线（便捷函数）
    """
    analyzer = ContactAnalyzer()
    return analyzer.get_contact_timeline(contact_email, account_id, days)

