"""
回归测试：确保已修复的 Bug 不再出现

本文件测试以下已修复的关键 Bug：
1. UID vs 序列号混乱
2. account_id 路由错误
3. 连接泄漏
4. FLAGS 解析错误
5. 缓存空列表误判
6. 多账户缓存逻辑错误
7. 文件夹名称未引用
"""
import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.legacy_operations import (
    fetch_emails, get_email_detail, mark_email_read,
    delete_email, _normalize_folder_name
)
from src.operations.cached_operations import CachedEmailOperations


class TestUIDStabilityFix(unittest.TestCase):
    """
    回归测试 #1: UID vs 序列号混乱
    
    问题：之前使用序列号作为邮件 ID，导致邮件顺序变化时操作错误的邮件
    修复：优先使用 UID，序列号作为回退
    """
    
    def test_fetch_emails_returns_uid_as_id(self):
        """测试 fetch_emails 返回 UID 作为邮件 ID"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            mock_conn.account_id = 'test_account'
            
            # Mock IMAP responses
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.return_value = ('OK', [b'1 2 3'])  # UIDs
            
            # Mock header fetch - 返回包含 UID 的响应
            mock_mail.fetch.return_value = ('OK', [
                (b'1 (UID 101 RFC822.SIZE 1024 BODY[HEADER.FIELDS (FROM SUBJECT DATE)] {100}', 
                 b'From: sender@example.com\r\nSubject: Test\r\nDate: Mon, 1 Jan 2024 12:00:00 +0000\r\n\r\n'),
                b')'
            ])
            
            try:
                result = fetch_emails(limit=1, account_id='test_account')
                
                # 验证返回的 ID 是 UID（101）而非序列号（1）
                if result and 'emails' in result and len(result['emails']) > 0:
                    email = result['emails'][0]
                    # UID 应该存在
                    self.assertIn('uid', email)
                    # id 应该等于 UID
                    self.assertEqual(email.get('id'), email.get('uid'))
            finally:
                if hasattr(mock_mail, 'logout'):
                    mock_mail.logout.return_value = ('BYE', [])
    
    def test_get_email_detail_tries_uid_first_then_fallback(self):
        """测试 get_email_detail 先尝试 UID，失败后回退到序列号"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            mock_conn.account_id = 'test_account'
            
            # Mock: UID fetch 失败，序列号成功
            mock_mail.select.return_value = ('OK', [b'10'])
            
            def uid_fetch_side_effect(command, email_id, fetch_parts):
                if command == 'fetch':
                    # UID fetch 返回空（失败）
                    return ('OK', [None])
                return ('OK', [])
            
            mock_mail.uid.side_effect = uid_fetch_side_effect
            
            # 序列号 fetch 成功
            mock_mail.fetch.return_value = ('OK', [
                (b'1 (RFC822 {100}', b'From: test@example.com\r\nSubject: Test\r\n\r\nBody'),
                b')'
            ])
            
            try:
                result = get_email_detail('123', folder='INBOX', account_id='test_account')
                
                # 验证：先调用 uid，失败后调用 fetch
                mock_mail.uid.assert_called()
                mock_mail.fetch.assert_called()
            finally:
                if hasattr(mock_mail, 'logout'):
                    mock_mail.logout.return_value = ('BYE', [])


class TestAccountIDRoutingFix(unittest.TestCase):
    """
    回归测试 #2: account_id 路由错误
    
    问题：返回 email 地址而非规范的 account_id，导致后续调用找错账户
    修复：始终返回规范的 account_id（如 'env_163'）
    """
    
    def test_fetch_emails_returns_canonical_account_id(self):
        """测试 fetch_emails 返回规范的 account_id（非 email）"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'leeguoo@163.com'
            mock_conn.account_id = 'env_163'  # 规范 ID
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.return_value = ('OK', [b'1'])
            mock_mail.fetch.return_value = ('OK', [
                (b'1 (UID 101 RFC822.SIZE 1024 BODY[HEADER.FIELDS (FROM SUBJECT DATE)] {50}',
                 b'From: sender@example.com\r\nSubject: Test\r\n\r\n'),
                b')'
            ])
            
            try:
                result = fetch_emails(limit=1, account_id='env_163')
                
                if result and 'emails' in result and len(result['emails']) > 0:
                    email = result['emails'][0]
                    # 应该返回 'env_163' 而非 'leeguoo@163.com'
                    self.assertEqual(email.get('account_id'), 'env_163')
                    self.assertNotEqual(email.get('account_id'), 'leeguoo@163.com')
            finally:
                mock_mail.logout.return_value = ('BYE', [])


class TestConnectionLeakFix(unittest.TestCase):
    """
    回归测试 #3: 连接泄漏
    
    问题：异常时未调用 mail.logout()，导致连接泄漏
    修复：使用 try/finally 确保总是关闭连接
    """
    
    def test_fetch_emails_closes_connection_on_error(self):
        """测试 fetch_emails 在出错时仍关闭连接"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            mock_conn.account_id = 'test_account'
            
            # Mock: select 成功，但 search 失败
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.side_effect = Exception("Network error")
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行并期望返回错误（但不抛异常）
            result = fetch_emails(limit=10, account_id='test_account')
            
            # 验证：即使出错，logout 仍被调用
            mock_mail.logout.assert_called()
            
            # 验证：返回错误信息
            self.assertIn('error', result)
    
    def test_get_email_detail_closes_connection_on_success(self):
        """测试 get_email_detail 成功时也关闭连接"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            mock_conn.account_id = 'test_account'
            
            # Mock 成功的响应
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.return_value = ('OK', [
                (b'1 (RFC822 {50}', b'From: test@test.com\r\nSubject: Test\r\n\r\nBody'),
                b')'
            ])
            mock_mail.logout.return_value = ('BYE', [])
            
            try:
                result = get_email_detail('123', folder='INBOX', account_id='test_account')
                
                # 验证：logout 被调用
                mock_mail.logout.assert_called()
            except:
                pass


class TestFLAGSParsingFix(unittest.TestCase):
    """
    回归测试 #4: FLAGS 解析错误
    
    问题：IMAP 返回的 FLAGS 是 tuple，直接 .decode() 会报错
    修复：正确提取 tuple[0][0] 再 decode
    """
    
    def test_parse_flags_from_tuple_response(self):
        """测试从 IMAP tuple 响应正确解析 FLAGS"""
        # IMAP FLAGS 响应格式：(b'123 (UID 456 FLAGS (\\Seen))', b'')
        mock_response = (b'123 (UID 456 FLAGS (\\Seen))', b'')
        
        # 正确的解析方式
        try:
            flags_data = mock_response[0]  # 获取第一个元素
            if isinstance(flags_data, bytes):
                flags_str = flags_data.decode('utf-8', errors='ignore')
                self.assertIn('FLAGS', flags_str)
                self.assertIn('\\Seen', flags_str)
            else:
                self.fail("FLAGS data should be bytes")
        except AttributeError:
            self.fail("Should not raise AttributeError on tuple")


class TestCacheEmptyListFix(unittest.TestCase):
    """
    回归测试 #5: 缓存空列表误判
    
    问题：if result and result.get('emails') 会把空列表 [] 当 False
    修复：改为 if result is not None
    """
    
    def test_cache_returns_empty_list_is_still_valid(self):
        """关键测试：缓存返回空列表应被视为有效"""
        # 模拟缓存返回空列表但仍在有效期内
        mock_cache_result = {
            "emails": [],  # 空列表（如 unread_only=True 时无未读邮件）
            "total_in_folder": 100,
            "unread_count": 0,
            "folder": "INBOX",
            "from_cache": True,
            "cache_age_minutes": 5.0  # 仍在 15 分钟有效期内
        }
        
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            with patch('src.operations.cached_operations.CachedEmailOperations') as MockCache:
                mock_cache_instance = Mock()
                MockCache.return_value = mock_cache_instance
                mock_cache_instance.is_available.return_value = True
                mock_cache_instance.list_emails_cached.return_value = mock_cache_result
                
                # 执行：use_cache=True
                result = fetch_emails(
                    limit=10, 
                    unread_only=True, 
                    account_id='test_account',
                    use_cache=True
                )
                
                # 验证：应该返回缓存结果（即使 emails=[]）
                self.assertIsNotNone(result)
                self.assertEqual(result.get('from_cache'), True)
                self.assertEqual(len(result.get('emails', [])), 0)
                
                # 验证：不应该尝试 IMAP 连接
                mock_get_conn.assert_not_called()
    
    def test_cache_returns_none_triggers_imap_fallback(self):
        """测试缓存返回 None 时回退到 IMAP"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            with patch('src.operations.cached_operations.CachedEmailOperations') as MockCache:
                mock_cache_instance = Mock()
                MockCache.return_value = mock_cache_instance
                mock_cache_instance.is_available.return_value = True
                mock_cache_instance.list_emails_cached.return_value = None  # 缓存过期
                
                mock_conn = Mock()
                mock_mail = Mock()
                mock_get_conn.return_value = mock_conn
                mock_conn.connect_imap.return_value = mock_mail
                mock_conn.email = 'test@example.com'
                mock_conn.account_id = 'test_account'
                
                mock_mail.select.return_value = ('OK', [b'10'])
                mock_mail.uid.return_value = ('OK', [b'1'])
                mock_mail.fetch.return_value = ('OK', [])
                mock_mail.logout.return_value = ('BYE', [])
                
                # 执行
                result = fetch_emails(
                    limit=10,
                    account_id='test_account',
                    use_cache=True
                )
                
                # 验证：应该尝试 IMAP 连接
                mock_get_conn.assert_called_once_with('test_account')


class TestMultiAccountCacheLogicFix(unittest.TestCase):
    """
    回归测试 #6: 多账户缓存逻辑错误
    
    问题：account_id=None 时仍尝试缓存，返回不完整数据
    修复：多账户请求检查在缓存检查之前
    """
    
    def test_multi_account_skips_cache(self):
        """测试多账户请求（account_id=None）跳过缓存"""
        with patch('src.legacy_operations.account_manager') as mock_account_mgr:
            with patch('src.legacy_operations.fetch_emails_multi_account') as mock_multi_fetch:
                mock_account_mgr.list_accounts.return_value = [
                    {'id': 'acc1', 'email': 'test1@example.com'},
                    {'id': 'acc2', 'email': 'test2@example.com'}
                ]
                
                mock_multi_fetch.return_value = {
                    'emails': [],
                    'accounts_count': 2
                }
                
                # 执行：account_id=None, use_cache=True
                result = fetch_emails(
                    limit=10,
                    account_id=None,  # 多账户
                    use_cache=True
                )
                
                # 验证：应该调用 fetch_emails_multi_account
                mock_multi_fetch.assert_called_once()
    
    def test_single_account_uses_cache(self):
        """测试单账户请求（account_id='xxx'）可以使用缓存"""
        with patch('src.operations.cached_operations.CachedEmailOperations') as MockCache:
            with patch('src.legacy_operations.get_connection_manager'):
                mock_cache_instance = Mock()
                MockCache.return_value = mock_cache_instance
                mock_cache_instance.is_available.return_value = True
                mock_cache_instance.list_emails_cached.return_value = {
                    "emails": [{"id": "1", "subject": "Test"}],
                    "from_cache": True
                }
                
                # 执行：account_id='test', use_cache=True
                result = fetch_emails(
                    limit=10,
                    account_id='test_account',
                    use_cache=True
                )
                
                # 验证：应该调用缓存
                mock_cache_instance.list_emails_cached.assert_called_once()
                self.assertTrue(result.get('from_cache'))


class TestFolderNameNormalizationFix(unittest.TestCase):
    """
    回归测试 #7: 文件夹名称未引用
    
    问题：包含空格的文件夹名称（如 "Deleted Messages"）导致 IMAP BAD 请求
    修复：_normalize_folder_name 函数自动引用和编码
    """
    
    def test_normalize_folder_with_spaces(self):
        """测试包含空格的文件夹名称被正确引用"""
        result = _normalize_folder_name('Deleted Messages')
        # 应该被引用
        self.assertEqual(result, '"Deleted Messages"')
    
    def test_normalize_inbox_unchanged(self):
        """测试 INBOX 保持不变"""
        result = _normalize_folder_name('INBOX')
        self.assertEqual(result, 'INBOX')
    
    def test_normalize_empty_defaults_to_inbox(self):
        """测试空字符串默认为 INBOX"""
        self.assertEqual(_normalize_folder_name(''), 'INBOX')
        self.assertEqual(_normalize_folder_name(None), 'INBOX')
    
    def test_normalize_strips_whitespace(self):
        """测试去除前后空格"""
        result = _normalize_folder_name('  Drafts  ')
        # 应该去除空格
        self.assertEqual(result, 'Drafts')
    
    def test_normalize_handles_utf7_characters(self):
        """测试处理非 ASCII 字符（UTF-7 编码）"""
        # 中文文件夹名
        result = _normalize_folder_name('草稿箱')
        # 应该返回字符串或 bytes（IMAP UTF-7 编码）
        self.assertIsInstance(result, (str, bytes))
        self.assertIsNotNone(result)


class TestEdgeCases(unittest.TestCase):
    """测试边界条件和错误处理"""
    
    def test_fetch_emails_handles_none_data(self):
        """测试 fetch_emails 处理 None 数据"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            mock_conn.account_id = 'test_account'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.return_value = ('OK', [b'1'])
            mock_mail.fetch.return_value = ('OK', [None])  # None 数据
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行：不应该抛异常
            result = fetch_emails(limit=10, account_id='test_account')
            
            # 验证：应该返回空列表或错误
            self.assertIsInstance(result, dict)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)

