"""
Test parallel operations safety and performance
"""
import unittest
from unittest.mock import Mock, patch, MagicMock
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.operations.parallel_operations import ParallelOperations, ParallelBatchOperations
from src.operations.parallel_search import ParallelSearchOperations


class TestParallelOperationsSafety(unittest.TestCase):
    """Test that parallel operations maintain account isolation"""
    
    def setUp(self):
        self.parallel_ops = ParallelOperations(max_workers=3)
        self.batch_ops = ParallelBatchOperations()
    
    def test_account_id_required_for_batch_operations(self):
        """Test that batch operations require account_id for safety"""
        # Try batch delete without account_id
        result = self.parallel_ops.execute_batch_operation(
            self.batch_ops.batch_delete_emails,
            email_ids=['1', '2', '3'],
            folder='INBOX',
            account_id=None  # No account ID
        )
        
        self.assertFalse(result['success'])
        self.assertIn('required', result['error'].lower())
    
    def test_account_isolation_in_batch_delete(self):
        """Test that batch delete only affects specified account"""
        # Mock account manager
        with patch.object(self.parallel_ops.account_manager, 'get_account') as mock_get:
            mock_get.return_value = {
                'id': 'account1',
                'email': 'test1@example.com',
                'password': 'pass1',
                'provider': 'gmail'
            }
            
            # Mock connection manager
            with patch('src.operations.parallel_operations.ConnectionManager') as MockConnMgr:
                mock_conn = Mock()
                mock_mail = Mock()
                mock_conn.connect_imap.return_value = mock_mail
                mock_conn.email = 'test1@example.com'
                MockConnMgr.return_value = mock_conn
                
                # Configure mock IMAP
                mock_mail.select.return_value = ('OK', [b'5'])
                mock_mail.store.return_value = ('OK', None)
                mock_mail.expunge.return_value = ('OK', None)
                mock_mail.close.return_value = None
                mock_mail.logout.return_value = None
                
                # Execute batch delete
                result = self.parallel_ops.execute_batch_operation(
                    self.batch_ops.batch_delete_emails,
                    email_ids=['1', '2', '3'],
                    folder='INBOX',
                    account_id='account1'
                )
                
                # Verify only account1 was accessed
                mock_get.assert_called_once_with('account1')
                MockConnMgr.assert_called_once_with(mock_get.return_value)
                
                # Verify result includes account info
                self.assertEqual(result['account'], 'test1@example.com')
                self.assertEqual(result['account_id'], 'account1')
    
    def test_concurrent_operations_thread_safety(self):
        """Test thread safety of concurrent operations"""
        results = []
        errors = []
        
        def mock_operation(connection_manager, email_ids, folder, **kwargs):
            # Simulate some work
            time.sleep(0.01)
            return {
                'success': True,
                'processed': len(email_ids),
                'thread_id': threading.current_thread().ident
            }
        
        # Mock account manager
        with patch.object(self.parallel_ops.account_manager, 'get_account') as mock_get:
            mock_get.return_value = {
                'id': 'test_account',
                'email': 'test@example.com',
                'password': 'pass',
                'provider': 'gmail'
            }
            
            # Mock ConnectionManager
            with patch('src.operations.parallel_operations.ConnectionManager'):
                # Run multiple operations concurrently
                with ThreadPoolExecutor(max_workers=5) as executor:
                    futures = []
                    
                    for i in range(10):
                        future = executor.submit(
                            self.parallel_ops.execute_batch_operation,
                            mock_operation,
                            email_ids=[str(j) for j in range(i*10, (i+1)*10)],
                            folder='INBOX',
                            account_id='test_account'
                        )
                        futures.append(future)
                    
                    # Collect results
                    for future in futures:
                        try:
                            result = future.result()
                            results.append(result)
                        except Exception as e:
                            errors.append(str(e))
                
                # Verify all operations completed successfully
                self.assertEqual(len(results), 10)
                self.assertEqual(len(errors), 0)
                
                # Verify each operation processed correct number of emails
                for i, result in enumerate(results):
                    self.assertEqual(result['processed'], 10)
                
                # Verify different threads were used
                thread_ids = set(r['thread_id'] for r in results)
                self.assertGreater(len(thread_ids), 1)


class TestParallelSearchSafety(unittest.TestCase):
    """Test parallel search operations"""
    
    def setUp(self):
        self.parallel_search = ParallelSearchOperations(max_workers=3)
    
    def test_multi_account_search_isolation(self):
        """Test that searches are isolated per account"""
        # Mock account manager
        with patch.object(self.parallel_search.account_manager, 'list_accounts') as mock_list:
            mock_list.return_value = [
                {'id': 'acc1', 'email': 'test1@example.com', 'provider': 'gmail'},
                {'id': 'acc2', 'email': 'test2@example.com', 'provider': 'outlook'},
                {'id': 'acc3', 'email': 'test3@example.com', 'provider': '163'}
            ]
            
            # Track which accounts were accessed
            accessed_accounts = []
            
            def mock_search_single(account, *args, **kwargs):
                accessed_accounts.append(account['id'])
                return {
                    'success': True,
                    'emails': [
                        {
                            'id': f"{account['id']}_1",
                            'subject': f"Test email from {account['email']}",
                            'from': 'sender@example.com',
                            'date': '2024-01-01 12:00:00'
                        }
                    ],
                    'total_found': 1,
                    'displayed': 1
                }
            
            # Patch the search method
            with patch.object(self.parallel_search, '_search_single_account', mock_search_single):
                # Execute search
                result = self.parallel_search.search_all_accounts(
                    query='test',
                    search_in='subject'
                )
                
                # Verify all accounts were searched
                self.assertEqual(set(accessed_accounts), {'acc1', 'acc2', 'acc3'})
                
                # Verify results include account information
                self.assertEqual(len(result['emails']), 3)
                for email in result['emails']:
                    self.assertIn('account', email)
                    self.assertIn('account_id', email)
                
                # Verify each email is from correct account
                account_emails = {email['account_id']: email for email in result['emails']}
                self.assertIn('test1@example.com', account_emails['acc1']['subject'])
                self.assertIn('test2@example.com', account_emails['acc2']['subject'])
                self.assertIn('test3@example.com', account_emails['acc3']['subject'])
    
    def test_search_specific_accounts_only(self):
        """Test searching specific accounts only"""
        with patch.object(self.parallel_search.account_manager, 'get_account') as mock_get:
            # Setup mock to return different accounts
            def get_account_side_effect(acc_id):
                accounts = {
                    'acc1': {'id': 'acc1', 'email': 'test1@example.com', 'provider': 'gmail'},
                    'acc2': {'id': 'acc2', 'email': 'test2@example.com', 'provider': 'outlook'},
                    'acc3': {'id': 'acc3', 'email': 'test3@example.com', 'provider': '163'}
                }
                return accounts.get(acc_id)
            
            mock_get.side_effect = get_account_side_effect
            
            # Track accessed accounts
            accessed_accounts = []
            
            def mock_search_single(account, *args, **kwargs):
                accessed_accounts.append(account['id'])
                return {'success': True, 'emails': [], 'total_found': 0}
            
            with patch.object(self.parallel_search, '_search_single_account', mock_search_single):
                # Search only specific accounts
                result = self.parallel_search.search_all_accounts(
                    query='test',
                    account_ids=['acc1', 'acc3']  # Only search these
                )
                
                # Verify only specified accounts were searched
                self.assertEqual(set(accessed_accounts), {'acc1', 'acc3'})
                self.assertNotIn('acc2', accessed_accounts)


class TestBatchOperationPerformance(unittest.TestCase):
    """Test performance improvements with parallel operations"""
    
    def test_parallel_vs_sequential_performance(self):
        """Compare parallel vs sequential operation times"""
        # This test demonstrates the performance benefit of parallel operations
        # We'll simulate multiple accounts being processed
        
        def simulate_account_operation(account, query):
            """Simulate a search operation that takes time"""
            time.sleep(0.05)  # Simulate network delay
            return {
                'success': True,
                'emails': [{'id': f'{account["id"]}_1', 'subject': f'Test from {account["email"]}'}],
                'total_found': 1
            }
        
        # Create test accounts
        test_accounts = [
            {'id': f'acc{i}', 'email': f'test{i}@example.com', 'provider': 'gmail'}
            for i in range(5)
        ]
        
        # Test sequential processing
        start_seq = time.time()
        sequential_results = []
        for account in test_accounts:
            result = simulate_account_operation(account, 'test query')
            sequential_results.append(result)
        seq_time = time.time() - start_seq
        
        # Test parallel processing
        start_par = time.time()
        parallel_results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(simulate_account_operation, account, 'test query'): account
                for account in test_accounts
            }
            for future in as_completed(futures):
                result = future.result()
                parallel_results.append(result)
        par_time = time.time() - start_par
        
        # Verify both got same number of results
        self.assertEqual(len(sequential_results), len(parallel_results))
        
        # Parallel should be significantly faster (at least 2x faster)
        self.assertLess(par_time, seq_time * 0.6)
        print(f"\\nPerformance comparison:")
        print(f"Sequential time: {seq_time:.3f}s")
        print(f"Parallel time: {par_time:.3f}s")
        print(f"Speedup: {seq_time/par_time:.2f}x")


if __name__ == '__main__':
    unittest.main()