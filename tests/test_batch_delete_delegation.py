"""
测试 batch_delete_emails 委托给 delete_email

关键验证：
1. batch_delete_emails 调用 delete_email（而非重新实现逻辑）
2. 每次删除都有独立的 expunge（确保 QQ 邮箱兼容性）
3. 失败的邮件被正确追踪
4. 行为与单个 delete_email 一致
"""
import unittest
from unittest.mock import Mock, patch, call
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.legacy_operations import batch_delete_emails, delete_email


class TestBatchDeleteDelegation(unittest.TestCase):
    """测试 batch_delete_emails 委托逻辑"""
    
    def test_batch_delete_calls_delete_email_for_each_id(self):
        """关键测试：batch_delete_emails 为每个 ID 调用 delete_email（委托模式）"""
        with patch('src.legacy_operations.delete_email') as mock_delete:
            # Mock: delete_email 全部成功
            mock_delete.return_value = {
                'success': True,
                'message': 'Email deleted',
                'account': 'test@example.com'
            }
            
            # 执行批量删除（使用委托模式）
            email_ids = ['101', '102', '103']
            result = batch_delete_emails(
                email_ids, 
                folder='INBOX', 
                account_id='test',
                shared_connection=False  # 使用委托模式
            )
            
            # 验证：delete_email 被调用了 3 次
            self.assertEqual(mock_delete.call_count, 3)
            
            # 验证：每次调用都传递了正确的参数
            expected_calls = [
                call('101', folder='INBOX', account_id='test'),
                call('102', folder='INBOX', account_id='test'),
                call('103', folder='INBOX', account_id='test')
            ]
            mock_delete.assert_has_calls(expected_calls, any_order=False)
            
            # 验证：返回正确的统计信息
            self.assertEqual(result['deleted_count'], 3)
            self.assertEqual(result['total_count'], 3)
            self.assertNotIn('failed_ids', result)
    
    def test_batch_delete_tracks_failures(self):
        """测试批量删除追踪失败的 ID（委托模式）"""
        with patch('src.legacy_operations.delete_email') as mock_delete:
            # Mock: 部分成功，部分失败
            def delete_side_effect(email_id, *args, **kwargs):
                if email_id == '102':
                    return {'error': 'Failed to delete email 102'}
                return {'success': True, 'account': 'test@example.com'}
            
            mock_delete.side_effect = delete_side_effect
            
            # 执行批量删除（使用委托模式）
            result = batch_delete_emails(
                ['101', '102', '103'], 
                folder='INBOX', 
                account_id='test',
                shared_connection=False  # 使用委托模式
            )
            
            # 验证：2 成功，1 失败
            self.assertEqual(result['deleted_count'], 2)
            self.assertEqual(result['failed_count'], 1)
            self.assertEqual(result['failed_ids'], ['102'])
            self.assertIn('2/3', result['message'])
    
    def test_batch_delete_all_failures(self):
        """测试批量删除全部失败的情况（委托模式）"""
        with patch('src.legacy_operations.delete_email') as mock_delete:
            # Mock: 全部失败
            mock_delete.return_value = {'error': 'Connection failed'}
            
            # 执行批量删除（使用委托模式）
            result = batch_delete_emails(
                ['1', '2', '3'], 
                folder='INBOX', 
                account_id='test',
                shared_connection=False  # 使用委托模式
            )
            
            # 验证：0 成功，3 失败
            self.assertEqual(result['deleted_count'], 0)
            self.assertEqual(result['failed_count'], 3)
            self.assertEqual(set(result['failed_ids']), {'1', '2', '3'})
            # 消息应该说明全部失败
            self.assertIn('Failed to delete all', result['message'])
    
    def test_batch_delete_empty_list(self):
        """测试空列表的边界条件"""
        result = batch_delete_emails([], folder='INBOX', account_id='test')
        
        # 验证：返回成功但没有删除任何邮件
        self.assertTrue(result['success'])
        self.assertEqual(result['deleted_count'], 0)
        self.assertIn('No emails', result['message'])
    
    def test_batch_delete_uses_shared_connection_by_default(self):
        """
        集成测试：验证批量删除默认使用共享连接
        
        这确保了 QQ 邮箱兼容性（每次 expunge）+ 性能优化（共享连接）
        """
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@qq.com'  # QQ 邮箱
            
            # Mock 成功的删除
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.uid.return_value = ('OK', [])
            mock_mail.store.return_value = ('OK', [])
            mock_mail.expunge.return_value = ('OK', [])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行批量删除（2 封邮件，默认使用共享连接）
            result = batch_delete_emails(['3747', '3748'], folder='INBOX', account_id='qq_account')
            
            # 验证：应该成功
            self.assertTrue(result['success'])
            self.assertEqual(result['deleted_count'], 2)
            self.assertEqual(result['total_count'], 2)
            
            # 验证：expunge 被调用了 2 次（每次删除一次，QQ 邮箱兼容）
            self.assertEqual(mock_mail.expunge.call_count, 2)
            
            # 验证：共享连接（只 logout 一次）
            self.assertEqual(mock_mail.logout.call_count, 1)


class TestBatchDeleteQQMailCompatibility(unittest.TestCase):
    """测试 QQ 邮箱兼容性"""
    
    def test_qq_mail_individual_expunge_per_delete(self):
        """
        关键测试：确保每次删除后都有 expunge（共享连接模式）
        
        QQ 邮箱的问题：
        - 批量 STORE + 单次 expunge = 失败
        - 单个 STORE + 立即 expunge = 成功
        
        修复后的行为：
        - 共享连接模式仍然每次 STORE 后立即 expunge
        - 确保 QQ 邮箱兼容性
        """
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'user@qq.com'
            
            # 追踪调用顺序
            call_sequence = []
            
            def track_select(*args):
                call_sequence.append('select')
                return ('OK', [b'10'])
            
            def track_uid(*args):
                call_sequence.append('uid_store')
                return ('OK', [])
            
            def track_expunge():
                call_sequence.append('expunge')
                return ('OK', [])
            
            def track_logout():
                call_sequence.append('logout')
                return ('BYE', [])
            
            mock_mail.select.side_effect = track_select
            mock_mail.uid.side_effect = track_uid
            mock_mail.expunge.side_effect = track_expunge
            mock_mail.logout.side_effect = track_logout
            mock_mail.close.return_value = None
            
            # 执行批量删除（默认使用共享连接模式）
            batch_delete_emails(['1', '2'], folder='INBOX', account_id='qq')
            
            # 验证调用序列：共享连接模式
            # select一次 -> (store + expunge) x N -> logout一次
            expected_pattern = [
                'select',           # 一次 select
                'uid_store', 'expunge',  # 第 1 封邮件
                'uid_store', 'expunge',  # 第 2 封邮件
                'logout',           # 一次 logout
            ]
            
            self.assertEqual(call_sequence, expected_pattern)
    
    def test_qq_mail_partial_success(self):
        """测试 QQ 邮箱部分成功的场景（共享连接模式）"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'user@qq.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # Mock: 第一封成功，第二封失败
            call_count = [0]
            def uid_side_effect(*args):
                call_count[0] += 1
                if call_count[0] == 1:
                    # 第一个成功
                    return ('OK', [])
                # 第二个失败
                return ('NO', [b'Failed'])
            
            mock_mail.uid.side_effect = uid_side_effect
            mock_mail.store.return_value = ('NO', [b'Failed'])  # fallback 也失败
            mock_mail.expunge.return_value = ('OK', [])
            
            # 执行批量删除（共享连接模式）
            result = batch_delete_emails(['3747', '3748'], folder='INBOX', account_id='qq')
            
            # 验证：1 成功，1 失败
            self.assertEqual(result['deleted_count'], 1)
            self.assertEqual(result['failed_count'], 1)
            self.assertEqual(result['failed_ids'], ['3748'])


class TestCodeDeduplication(unittest.TestCase):
    """测试代码去重效果"""
    
    def test_no_duplicate_deletion_logic(self):
        """
        验证删除逻辑有组织
        
        修复后架构：
        - delete_email：单个删除的权威实现
        - _batch_delete_emails_shared_connection：共享连接的优化版本
        - batch_delete_emails：路由层，选择使用哪个实现
        """
        # 读取源代码
        from pathlib import Path
        source_file = Path(__file__).parent.parent / 'src' / 'legacy_operations.py'
        source_code = source_file.read_text()
        
        # 查找 batch_delete_emails 的定义（不包括 _shared_connection 版本）
        batch_start = source_code.find('def batch_delete_emails(')
        batch_end = source_code.find('def _batch_delete_emails_shared_connection(', batch_start)
        batch_code = source_code[batch_start:batch_end]
        
        # 验证：batch_delete_emails 本身不应该有直接的 IMAP 操作
        # （它应该委托给 _batch_delete_emails_shared_connection 或 delete_email）
        self.assertNotIn('mail = conn_mgr.connect_imap()', batch_code, 
                        "batch_delete_emails should not directly connect to IMAP")
        
        # 验证：应该调用委托函数
        self.assertTrue(
            '_batch_delete_emails_shared_connection' in batch_code or 'delete_email(' in batch_code,
            "batch_delete_emails should delegate to helper functions"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)

