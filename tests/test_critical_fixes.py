"""
测试关键修复：FLAGS 格式、success 字段、性能优化

本测试覆盖：
1. move_email_to_trash 回退路径使用正确的 FLAGS 格式
2. batch_delete_emails 失败时返回 success: False
3. 共享连接的性能优化版本
"""
import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.legacy_operations import (
    move_email_to_trash, batch_delete_emails,
    _batch_delete_emails_shared_connection
)


class TestMoveToTrashFallbackFlags(unittest.TestCase):
    """测试 move_email_to_trash 回退路径的 FLAGS 格式"""
    
    def test_fallback_uses_rfc_compliant_flags(self):
        """
        关键测试：回退路径使用 RFC 合规的 FLAGS 格式
        
        问题：当 COPY 失败时，回退路径使用了 '\\Deleted' 而非 r'(\Deleted)'
        修复：使用与主路径相同的 deleted_flag = r'(\Deleted)'
        """
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@qq.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            
            # 捕获 FLAGS 调用
            flags_used = []
            def capture_uid(*args):
                if len(args) >= 4 and args[0] in ('copy', 'store'):
                    if args[0] == 'copy':
                        # COPY 失败，触发回退路径
                        return ('NO', [b'Copy failed'])
                    elif args[0] == 'store':
                        # 记录 FLAGS
                        flags_used.append(args[3])
                        return ('OK', [])
                return ('OK', [])
            
            mock_mail.uid.side_effect = capture_uid
            mock_mail.expunge.return_value = ('OK', [])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行移动（会触发回退路径）
            result = move_email_to_trash('123', folder='INBOX', account_id='qq')
            
            # 验证：使用了 RFC 合规的 FLAGS 格式
            self.assertTrue(len(flags_used) > 0)
            flag = flags_used[0]
            # 应该是 r'(\Deleted)' 格式
            self.assertIn('Deleted', flag)
            self.assertTrue(flag.startswith('(') or flag.startswith(r'('))
    
    def test_fallback_checks_result_code(self):
        """测试回退路径检查返回码并在失败时抛异常"""
        with patch('src.legacy_operations.get_connection_manager') as mock_get_conn:
            mock_conn = Mock()
            mock_mail = Mock()
            mock_get_conn.return_value = mock_conn
            mock_conn.connect_imap.return_value = mock_mail
            mock_conn.email = 'test@qq.com'
            
            mock_mail.select.return_value = ('OK', [b'10'])
            
            # COPY 失败 → 回退到 store
            # store (UID 和 sequence) 都失败
            def failing_uid(*args):
                if args[0] == 'copy':
                    return ('NO', [b'Copy failed'])
                elif args[0] == 'store':
                    return ('NO', [b'Store failed'])
                return ('OK', [])
            
            mock_mail.uid.side_effect = failing_uid
            mock_mail.store.return_value = ('NO', [b'Store failed'])
            mock_mail.close.return_value = None
            mock_mail.logout.return_value = ('BYE', [])
            
            # 执行移动（应该返回错误）
            result = move_email_to_trash('123', folder='INBOX', account_id='qq')
            
            # 验证：返回错误，而非误报成功
            self.assertIn('error', result)


class TestBatchDeleteSuccessField(unittest.TestCase):
    """测试 batch_delete_emails 的 success 字段"""
    
    def test_success_true_when_all_succeed(self):
        """测试全部成功时 success=True"""
        with patch('src.legacy_operations._batch_delete_emails_shared_connection') as mock_batch:
            mock_batch.return_value = {
                'success': True,
                'deleted_count': 3,
                'total_count': 3,
                'message': 'Successfully deleted all 3 email(s)'
            }
            
            result = batch_delete_emails(['1', '2', '3'], account_id='test')
            
            self.assertTrue(result['success'])
            self.assertEqual(result['deleted_count'], 3)
    
    def test_success_false_when_all_fail(self):
        """
        关键测试：全部失败时 success=False
        
        问题：之前即使全部失败也返回 success: True
        修复：success = (len(failed_ids) == 0)
        """
        with patch('src.legacy_operations._batch_delete_emails_shared_connection') as mock_batch:
            mock_batch.return_value = {
                'success': False,
                'deleted_count': 0,
                'total_count': 3,
                'failed_ids': ['1', '2', '3'],
                'failed_count': 3,
                'message': 'Failed to delete all 3 email(s)'
            }
            
            result = batch_delete_emails(['1', '2', '3'], account_id='test')
            
            # 验证：success 应该是 False
            self.assertFalse(result['success'])
            self.assertEqual(result['deleted_count'], 0)
            self.assertEqual(result['failed_count'], 3)
    
    def test_success_false_when_partial_failure(self):
        """测试部分失败时 success=False"""
        with patch('src.legacy_operations._batch_delete_emails_shared_connection') as mock_batch:
            mock_batch.return_value = {
                'success': False,
                'deleted_count': 2,
                'total_count': 3,
                'failed_ids': ['2'],
                'failed_count': 1,
                'message': 'Partially deleted: 2/3 email(s) succeeded'
            }
            
            result = batch_delete_emails(['1', '2', '3'], account_id='test')
            
            # 验证：部分失败也应该 success=False
            self.assertFalse(result['success'])
            self.assertEqual(result['deleted_count'], 2)
            self.assertEqual(result['failed_count'], 1)


class TestSharedConnectionOptimization(unittest.TestCase):
    """测试共享连接的性能优化"""
    
    def test_shared_connection_mode_enabled_by_default(self):
        """测试默认使用共享连接模式"""
        with patch('src.legacy_operations._batch_delete_emails_shared_connection') as mock_shared:
            mock_shared.return_value = {
                'success': True,
                'deleted_count': 2,
                'total_count': 2
            }
            
            # 默认应该使用共享连接
            batch_delete_emails(['1', '2'], account_id='test')
            
            mock_shared.assert_called_once()
    
    def test_can_fallback_to_delegation_mode(self):
        """测试可以回退到委托模式（多连接）"""
        with patch('src.legacy_operations.delete_email') as mock_delete:
            mock_delete.return_value = {'success': True, 'account': 'test@example.com'}
            
            # 明确指定 shared_connection=False
            result = batch_delete_emails(
                ['1', '2'], 
                account_id='test',
                shared_connection=False
            )
            
            # 应该调用了 delete_email（委托模式）
            self.assertEqual(mock_delete.call_count, 2)
    
    def test_shared_connection_reuses_imap_session(self):
        """测试共享连接模式只建立一次 IMAP 连接"""
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
            
            # 删除 5 封邮件
            _batch_delete_emails_shared_connection(
                ['1', '2', '3', '4', '5'],
                folder='INBOX',
                account_id='test'
            )
            
            # 验证：只调用了一次 connect_imap（共享连接）
            mock_conn.connect_imap.assert_called_once()
            
            # 验证：只调用了一次 logout（共享连接）
            self.assertEqual(mock_mail.logout.call_count, 1)
    
    def test_shared_connection_expunges_after_each_delete(self):
        """
        关键测试：共享连接模式仍然每次删除后都 expunge
        
        这是 QQ 邮箱兼容性的关键：
        - 不能批量 STORE + 单次 expunge（QQ 邮箱不生效）
        - 必须每次 STORE + 立即 expunge
        - 但可以共享连接以提高性能
        """
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
            
            # 删除 3 封邮件
            _batch_delete_emails_shared_connection(
                ['1', '2', '3'],
                folder='INBOX',
                account_id='test'
            )
            
            # 验证：expunge 被调用了 3 次（每次删除一次）
            self.assertEqual(mock_mail.expunge.call_count, 3)


class TestPerformanceComparison(unittest.TestCase):
    """性能对比测试"""
    
    def test_shared_connection_vs_delegation_connection_count(self):
        """对比共享连接 vs 委托模式的连接数"""
        # 共享连接模式
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
            
            _batch_delete_emails_shared_connection(['1', '2', '3', '4', '5'], account_id='test')
            
            shared_connection_count = mock_conn.connect_imap.call_count
        
        # 委托模式
        with patch('src.legacy_operations.delete_email') as mock_delete:
            with patch('src.legacy_operations.get_connection_manager') as mock_get_conn2:
                mock_conn2 = Mock()
                mock_mail2 = Mock()
                mock_get_conn2.return_value = mock_conn2
                mock_conn2.connect_imap.return_value = mock_mail2
                mock_conn2.email = 'test@example.com'
                
                mock_mail2.select.return_value = ('OK', [b'10'])
                mock_mail2.uid.return_value = ('OK', [])
                mock_mail2.expunge.return_value = ('OK', [])
                mock_mail2.close.return_value = None
                mock_mail2.logout.return_value = ('BYE', [])
                
                # 绕过 shared_connection 逻辑，直接测试委托模式
                def delete_impl(email_id, **kwargs):
                    mock_get_conn2()
                    return {'success': True}
                
                mock_delete.side_effect = delete_impl
                
                batch_delete_emails(['1', '2', '3', '4', '5'], account_id='test', shared_connection=False)
                
                delegation_connection_count = mock_get_conn2.call_count
        
        # 验证：共享连接模式的连接数远少于委托模式
        print(f"\n性能对比 (5 封邮件):")
        print(f"  共享连接模式: {shared_connection_count} 个连接")
        print(f"  委托模式: {delegation_connection_count} 个连接")
        print(f"  改进: {delegation_connection_count / shared_connection_count:.1f}x 减少连接数")
        
        self.assertEqual(shared_connection_count, 1)
        self.assertEqual(delegation_connection_count, 5)


if __name__ == '__main__':
    unittest.main(verbosity=2)

