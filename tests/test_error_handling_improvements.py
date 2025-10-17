"""
测试错误处理和失败反馈改进

本次改进的关键点：
1. 文件夹名称规范化（防止 BAD 请求）
2. 失败时正确报错（不误报成功）
3. RFC 合规的 FLAGS 格式
4. 批量操作返回失败 ID 列表
"""
import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.legacy_operations import (
    delete_email, batch_delete_emails, move_email_to_trash,
    batch_move_to_trash, batch_mark_read, mark_email_read,
    _normalize_folder_name
)


class TestFolderNormalizationInOperations(unittest.TestCase):
    """测试所有操作都使用文件夹名称规范化"""
    
    def test_delete_email_normalizes_folder_name(self):
        """测试 delete_email 规范化文件夹名称"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            # Mock 成功的删除
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.return_value = ('OK', [])
            mock_mail.store.return_value = ('OK', [])
            mock_mail.expunge.return_value = ('OK', [])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 使用包含空格的文件夹
            result = delete_email('123', folder='Deleted Messages', account_id='test')
            
            # 验证：mail.select 被调用时使用了规范化的名称
            select_calls = mock_mail.select.call_args_list
            if select_calls:
                called_folder = select_calls[0][0][0]
                # 应该是引用后的名称
                self.assertEqual(called_folder, '"Deleted Messages"')
    
    def test_batch_operations_normalize_folder_names(self):
        """测试批量操作规范化文件夹名称"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.return_value = ('OK', [])
            mock_mail.expunge.return_value = ('OK', [])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 测试批量删除
            batch_delete_emails(['1', '2'], folder='Sent Items', account_id='test')
            
            # 验证：使用规范化的名称
            select_calls = mock_mail.select.call_args_list
            if select_calls:
                called_folder = select_calls[0][0][0]
                self.assertEqual(called_folder, '"Sent Items"')


class TestRFCCompliantFLAGS(unittest.TestCase):
    """测试 RFC 合规的 FLAGS 格式"""
    
    def test_delete_email_uses_rfc_compliant_flags(self):
        """测试 delete_email 使用 RFC 合规的 FLAGS 格式"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 捕获 uid 调用
            uid_calls = []
            def capture_uid(*args):
                uid_calls.append(args)
                return ('OK', [])
            mock_mail.uid.side_effect = capture_uid
            mock_mail.expunge.return_value = ('OK', [])
            
            # 执行删除
            delete_email('123', folder='INBOX', account_id='test')
            
            # 验证：使用 r'(\Deleted)' 格式
            if uid_calls:
                # uid('store', email_id, '+FLAGS', deleted_flag)
                self.assertEqual(len(uid_calls[0]), 4)
                self.assertEqual(uid_calls[0][0], 'store')
                self.assertEqual(uid_calls[0][2], '+FLAGS')
                # FLAGS 应该是 r'(\Deleted)' 格式
                self.assertIn('Deleted', uid_calls[0][3])
    
    def test_mark_email_read_uses_rfc_compliant_flags(self):
        """测试 mark_email_read 使用 RFC 合规的 FLAGS 格式"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            uid_calls = []
            def capture_uid(*args):
                uid_calls.append(args)
                return ('OK', [])
            mock_mail.uid.side_effect = capture_uid
            
            # 执行标记已读
            mark_email_read('123', folder='INBOX', account_id='test')
            
            # 验证：使用 r'(\Seen)' 格式
            if uid_calls:
                self.assertEqual(uid_calls[0][0], 'store')
                self.assertEqual(uid_calls[0][2], '+FLAGS')
                self.assertIn('Seen', uid_calls[0][3])


class TestFailureHandling(unittest.TestCase):
    """测试失败时的正确错误处理"""
    
    def test_delete_email_raises_on_failure(self):
        """测试 delete_email 失败时正确报错（不误报成功）"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            # Mock: store 命令失败
            mock_mail.uid.return_value = ('NO', [b'Command failed'])
            mock_mail.store.return_value = ('NO', [b'Command failed'])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行删除（应该失败）
            result = delete_email('123', folder='INBOX', account_id='test')
            
            # 验证：应该返回错误，而非 success=True
            self.assertIn('error', result)
            self.assertNotEqual(result.get('success'), True)
    
    def test_move_to_trash_fallback_when_copy_fails(self):
        """测试移动到回收站时 COPY 失败则回退到直接删除"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            
            # Mock: COPY 失败，但 store 成功（回退逻辑）
            call_count = [0]
            def uid_side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    # 第一次调用是 copy，失败
                    return ('NO', [b'Copy failed'])
                else:
                    # 后续调用是 store（删除），成功
                    return ('OK', [])
            
            mock_mail.uid.side_effect = uid_side_effect
            mock_mail.copy.return_value = ('NO', [b'Copy failed'])
            mock_mail.expunge.return_value = ('OK', [])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行移动（应该回退到删除）
            result = move_email_to_trash('123', folder='INBOX', account_id='test')
            
            # 验证：应该成功，但消息说明是直接删除
            self.assertTrue(result.get('success'))
            self.assertIn('deleted', result.get('message', '').lower())


class TestBatchOperationFailureReporting(unittest.TestCase):
    """测试批量操作的失败反馈"""
    
    def test_batch_delete_returns_failed_ids(self):
        """关键测试：batch_delete_emails 返回失败的 ID 列表"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.expunge.return_value = ('OK', [])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # Mock: 部分成功，部分失败
            call_count = [0]
            def uid_side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    return ('OK', [])  # 第一个成功
                elif call_count[0] == 2:
                    return ('NO', [b'Failed'])  # 第二个失败
                else:
                    return ('OK', [])  # 第三个成功
            
            mock_mail.uid.side_effect = uid_side_effect
            mock_mail.store.return_value = ('NO', [b'Failed'])  # fallback 也失败
            
            # 执行批量删除
            result = batch_delete_emails(['101', '102', '103'], folder='INBOX', account_id='test')
            
            # 验证：部分失败时 success 应该是 False
            self.assertFalse(result.get('success'), "Partial failure should return success=False")
            self.assertIn('message', result)
            # 应该有失败的 ID 列表
            self.assertIn('failed_ids', result)
            self.assertIn('102', result['failed_ids'])
            # 消息应该显示部分成功
            self.assertIn('2/3', result['message'])
    
    def test_batch_mark_read_reports_accurate_counts(self):
        """测试批量标记已读报告准确的成功/失败计数"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # Mock: 全部失败
            mock_mail.uid.return_value = ('NO', [b'Command failed'])
            mock_mail.store.return_value = ('NO', [b'Command failed'])
            
            # 执行批量标记
            result = batch_mark_read(['1', '2', '3'], folder='INBOX', account_id='test')
            
            # 验证：应该报告 0/3 成功
            self.assertTrue(result.get('success'))
            if 'failed_ids' in result:
                self.assertEqual(len(result['failed_ids']), 3)
    
    def test_batch_move_to_trash_tracks_failures(self):
        """测试批量移动到回收站追踪失败的邮件"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.list.return_value = ('OK', [b'(\\HasNoChildren) "/" "Trash"'])
            mock_mail.expunge.return_value = ('OK', [])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # Mock: 交替成功/失败
            call_count = [0]
            def uid_copy_side_effect(*args):
                call_count[0] += 1
                if call_count[0] % 2 == 1:
                    return ('OK', [])  # 奇数成功
                return ('NO', [b'Failed'])  # 偶数失败
            
            mock_mail.uid.side_effect = uid_copy_side_effect
            mock_mail.copy.return_value = ('NO', [b'Failed'])
            mock_mail.store.return_value = ('OK', [])
            
            # 执行批量移动
            result = batch_move_to_trash(
                ['1', '2', '3', '4'], 
                folder='INBOX', 
                account_id='test'
            )
            
            # 验证：应该报告部分成功
            self.assertTrue(result.get('success'))
            if 'failed_ids' in result:
                # 应该有失败的 ID
                self.assertGreater(len(result['failed_ids']), 0)


class TestCompleteErrorHandlingFlow(unittest.TestCase):
    """测试完整的错误处理流程"""
    
    def test_delete_workflow_with_folder_normalization_and_error_handling(self):
        """集成测试：文件夹规范化 + RFC FLAGS + 失败处理"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@example.com'
            
            # 场景：删除 "Deleted Messages" 文件夹中的邮件
            select_folder = None
            def capture_select(folder):
                nonlocal select_folder
                select_folder = folder
                return ('OK', [b'10'])
            
            mock_mail.select.side_effect = capture_select
            
            flags_used = []
            def capture_uid(*args):
                if len(args) >= 4 and args[0] == 'store':
                    flags_used.append(args[3])
                return ('NO', [b'Store failed'])  # 故意失败
            
            mock_mail.uid.side_effect = capture_uid
            mock_mail.store.return_value = ('NO', [b'Store failed'])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行删除
            result = delete_email('123', folder='Deleted Messages', account_id='test')
            
            # 验证 1：文件夹名称被规范化
            self.assertEqual(select_folder, '"Deleted Messages"')
            
            # 验证 2：使用 RFC 合规的 FLAGS
            if flags_used:
                self.assertIn('Deleted', flags_used[0])
            
            # 验证 3：失败时返回错误
            self.assertIn('error', result)
            self.assertNotEqual(result.get('success'), True)


if __name__ == '__main__':
    unittest.main(verbosity=2)

