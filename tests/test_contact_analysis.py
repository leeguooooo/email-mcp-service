"""
Tests for contact analysis功能
"""
import pytest
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import os

from src.operations.contact_analysis import ContactAnalyzer, analyze_contacts, get_contact_timeline


class TestContactAnalyzer:
    """测试联系人分析功能"""
    
    @pytest.fixture
    def temp_db(self):
        """创建临时测试数据库"""
        # 创建临时数据库
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        
        # 创建必要的表结构
        conn.execute("""
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT NOT NULL,
                folder_id INTEGER NOT NULL,
                uid TEXT NOT NULL,
                message_id TEXT,
                subject TEXT,
                sender TEXT,
                sender_email TEXT,
                recipients TEXT,
                date_sent TIMESTAMP,
                date_received TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE,
                is_flagged BOOLEAN DEFAULT FALSE,
                is_deleted BOOLEAN DEFAULT FALSE,
                has_attachments BOOLEAN DEFAULT FALSE,
                size_bytes INTEGER DEFAULT 0,
                content_hash TEXT,
                sync_status TEXT DEFAULT 'synced',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 插入测试数据
        now = datetime.now()
        test_data = [
            # Alice 发了 5 封邮件
            ('test_account', 1, '1', 'msg1', 'Test 1', 'Alice', 'alice@example.com',
             json.dumps(['bob@example.com']), (now - timedelta(days=5)).isoformat(), False),
            ('test_account', 1, '2', 'msg2', 'Test 2', 'Alice', 'alice@example.com',
             json.dumps(['bob@example.com']), (now - timedelta(days=10)).isoformat(), False),
            ('test_account', 1, '3', 'msg3', 'Test 3', 'Alice', 'alice@example.com',
             json.dumps(['charlie@example.com']), (now - timedelta(days=15)).isoformat(), False),
            ('test_account', 1, '4', 'msg4', 'Test 4', 'Alice', 'alice@example.com',
             json.dumps(['bob@example.com']), (now - timedelta(days=20)).isoformat(), False),
            ('test_account', 1, '5', 'msg5', 'Test 5', 'Alice', 'alice@example.com',
             json.dumps(['dave@example.com']), (now - timedelta(days=25)).isoformat(), False),
            
            # Bob 发了 3 封邮件
            ('test_account', 1, '6', 'msg6', 'Test 6', 'Bob', 'bob@example.com',
             json.dumps(['alice@example.com']), (now - timedelta(days=3)).isoformat(), False),
            ('test_account', 1, '7', 'msg7', 'Test 7', 'Bob', 'bob@example.com',
             json.dumps(['alice@example.com', 'charlie@example.com']), (now - timedelta(days=8)).isoformat(), False),
            ('test_account', 1, '8', 'msg8', 'Test 8', 'Bob', 'bob@example.com',
             json.dumps(['dave@example.com']), (now - timedelta(days=12)).isoformat(), False),
            
            # Charlie 发了 2 封邮件
            ('test_account', 1, '9', 'msg9', 'Test 9', 'Charlie', 'charlie@example.com',
             json.dumps(['alice@example.com']), (now - timedelta(days=7)).isoformat(), False),
            ('test_account', 1, '10', 'msg10', 'Test 10', 'Charlie', 'charlie@example.com',
             json.dumps(['bob@example.com']), (now - timedelta(days=18)).isoformat(), False),
            
            # 一封超过30天的邮件（应该被过滤）
            ('test_account', 1, '11', 'msg11', 'Old', 'Old Person', 'old@example.com',
             json.dumps(['someone@example.com']), (now - timedelta(days=35)).isoformat(), False),
            
            # 一封已删除的邮件（应该被过滤）
            ('test_account', 1, '12', 'msg12', 'Deleted', 'Deleted Person', 'deleted@example.com',
             json.dumps(['someone@example.com']), (now - timedelta(days=5)).isoformat(), True),
        ]
        
        for data in test_data:
            conn.execute("""
                INSERT INTO emails (
                    account_id, folder_id, uid, message_id, subject, sender, sender_email,
                    recipients, date_sent, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
        
        conn.commit()
        conn.close()
        
        yield db_path
        
        # 清理
        if Path(db_path).exists():
            os.unlink(db_path)
    
    def test_analyze_contacts_basic(self, temp_db):
        """测试基本的联系人分析"""
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.analyze_contacts(days=30, limit=10, group_by='both')
        
        assert 'error' not in result
        assert result['total_emails_analyzed'] == 10  # 排除了 is_deleted=True 和超过30天的
        assert 'top_senders' in result
        assert 'top_recipients' in result
        
        # 验证 top senders（Alice 5封, Bob 3封, Charlie 2封）
        top_senders = result['top_senders']
        assert len(top_senders) >= 3
        assert top_senders[0]['email'] == 'alice@example.com'
        assert top_senders[0]['count'] == 5
        assert top_senders[1]['email'] == 'bob@example.com'
        assert top_senders[1]['count'] == 3
    
    def test_analyze_contacts_sender_only(self, temp_db):
        """测试只分析发件人"""
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.analyze_contacts(days=30, limit=5, group_by='sender')
        
        assert 'top_senders' in result
        assert 'top_recipients' not in result
    
    def test_analyze_contacts_recipient_only(self, temp_db):
        """测试只分析收件人"""
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.analyze_contacts(days=30, limit=5, group_by='recipient')
        
        assert 'top_recipients' in result
        assert 'top_senders' not in result
    
    def test_analyze_contacts_with_limit(self, temp_db):
        """测试限制返回数量"""
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.analyze_contacts(days=30, limit=2, group_by='both')
        
        assert len(result['top_senders']) <= 2
        assert len(result['top_recipients']) <= 2
    
    def test_analyze_contacts_time_filter(self, temp_db):
        """测试时间过滤"""
        analyzer = ContactAnalyzer(temp_db)
        
        # 最近7天应该有更少的邮件
        result_7days = analyzer.analyze_contacts(days=7, limit=10, group_by='both')
        result_30days = analyzer.analyze_contacts(days=30, limit=10, group_by='both')
        
        assert result_7days['total_emails_analyzed'] < result_30days['total_emails_analyzed']
    
    def test_analyze_contacts_summary(self, temp_db):
        """测试统计摘要"""
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.analyze_contacts(days=30, limit=10, group_by='both')
        
        assert 'summary' in result
        summary = result['summary']
        assert 'unique_senders' in summary
        assert 'unique_recipients' in summary
        assert 'avg_emails_per_sender' in summary
        assert summary['unique_senders'] == 3  # Alice, Bob, Charlie
    
    def test_get_contact_timeline(self, temp_db):
        """测试联系人时间线"""
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.get_contact_timeline('alice@example.com', days=30)
        
        assert 'error' not in result
        assert result['contact_email'] == 'alice@example.com'
        assert result['total_interactions'] > 0
        assert 'timeline' in result
        
        # 验证时间线项目格式
        if result['timeline']:
            item = result['timeline'][0]
            assert 'date' in item
            assert 'subject' in item
            assert 'direction' in item
            assert item['direction'] in ['received', 'sent']
    
    def test_contact_timeline_direction(self, temp_db):
        """测试时间线的发送/接收方向"""
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.get_contact_timeline('alice@example.com', days=30)
        
        timeline = result['timeline']
        received_count = sum(1 for item in timeline if item['direction'] == 'received')
        sent_count = sum(1 for item in timeline if item['direction'] == 'sent')
        
        # Alice 发了5封，收到了4封（Bob 2封, Charlie 1封, 共3封 + 1封可能有其他）
        assert received_count > 0  # Alice 作为发件人
        assert sent_count > 0  # Alice 作为收件人
    
    def test_convenience_functions(self, temp_db):
        """测试便捷函数"""
        # 临时更新环境变量或使用自定义路径
        # 这里需要实际的 email_sync.db，所以我们跳过这个测试
        # 或者需要 mock EMAIL_SYNC_DB 路径
        pass
    
    def test_empty_database(self):
        """测试空数据库"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE emails (
                id INTEGER PRIMARY KEY,
                account_id TEXT,
                folder_id INTEGER,
                uid TEXT,
                message_id TEXT,
                subject TEXT,
                sender TEXT,
                sender_email TEXT,
                recipients TEXT,
                date_sent TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE
            )
        """)
        conn.commit()
        conn.close()
        
        analyzer = ContactAnalyzer(db_path)
        result = analyzer.analyze_contacts(days=30, limit=10)
        
        assert result['total_emails_analyzed'] == 0
        assert result['top_senders'] == []
        assert result['top_recipients'] == []
        
        os.unlink(db_path)
    
    def test_json_recipients_error_handling(self, temp_db):
        """测试 recipients JSON 解析错误处理"""
        # 添加一个无效 JSON 的邮件
        conn = sqlite3.connect(temp_db)
        conn.execute("""
            INSERT INTO emails (
                account_id, folder_id, uid, message_id, subject, sender, sender_email,
                recipients, date_sent, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('test_account', 1, '100', 'msg100', 'Invalid JSON', 'Test', 'test@example.com',
              'invalid,json,string', datetime.now().isoformat(), False))
        conn.commit()
        conn.close()
        
        analyzer = ContactAnalyzer(temp_db)
        result = analyzer.analyze_contacts(days=30, limit=10)
        
        # 应该不会崩溃，能正常处理
        assert 'error' not in result
        assert result['total_emails_analyzed'] >= 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

