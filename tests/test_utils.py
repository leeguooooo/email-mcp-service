"""
Unit tests for utility functions - no external dependencies
"""
import unittest
from datetime import datetime
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.legacy_operations import decode_mime_words
from src.operations.email_operations import EmailOperations


class TestUtils(unittest.TestCase):
    """Test utility functions"""
    
    def test_decode_mime_words_ascii(self):
        """Test decoding plain ASCII text"""
        result = decode_mime_words("Hello World")
        self.assertEqual(result, "Hello World")
    
    def test_decode_mime_words_encoded(self):
        """Test decoding MIME encoded text"""
        # UTF-8 encoded Chinese text
        encoded = "=?UTF-8?B?5L2g5aW9?="
        result = decode_mime_words(encoded)
        self.assertEqual(result, "你好")
        
        # ISO-8859-1 encoded text
        encoded = "=?ISO-8859-1?Q?Caf=E9?="
        result = decode_mime_words(encoded)
        self.assertEqual(result, "Café")
    
    def test_decode_mime_words_mixed(self):
        """Test decoding mixed encoded and plain text"""
        encoded = "=?UTF-8?B?5L2g5aW9?= Hello =?UTF-8?B?5LiW55WM?="
        result = decode_mime_words(encoded)
        self.assertEqual(result, "你好 Hello 世界")
    
    def test_decode_mime_words_empty(self):
        """Test decoding empty or None"""
        self.assertEqual(decode_mime_words(""), "")
        self.assertEqual(decode_mime_words(None), "")
    
    def test_format_size(self):
        """Test file size formatting"""
        email_ops = EmailOperations(None)
        
        self.assertEqual(email_ops._format_size(0), "0.0 B")
        self.assertEqual(email_ops._format_size(512), "512.0 B")
        self.assertEqual(email_ops._format_size(1024), "1.0 KB")
        self.assertEqual(email_ops._format_size(1536), "1.5 KB")
        self.assertEqual(email_ops._format_size(1048576), "1.0 MB")
        self.assertEqual(email_ops._format_size(1073741824), "1.0 GB")


class TestSearchCriteria(unittest.TestCase):
    """Test search criteria building"""
    
    def setUp(self):
        from src.operations.search_operations import SearchOperations
        self.search_ops = SearchOperations(None)
    
    def test_empty_criteria(self):
        """Test empty search criteria"""
        criteria = self.search_ops._build_search_criteria(
            None, "all", None, None, False
        )
        self.assertEqual(criteria, "ALL")
    
    def test_subject_search(self):
        """Test subject search criteria"""
        criteria = self.search_ops._build_search_criteria(
            "meeting", "subject", None, None, False
        )
        self.assertEqual(criteria, 'SUBJECT "meeting"')
    
    def test_from_search(self):
        """Test from search criteria"""
        criteria = self.search_ops._build_search_criteria(
            "john@example.com", "from", None, None, False
        )
        self.assertEqual(criteria, 'FROM "john@example.com"')
    
    def test_unread_only(self):
        """Test unread only criteria"""
        criteria = self.search_ops._build_search_criteria(
            None, "all", None, None, True
        )
        self.assertEqual(criteria, "UNSEEN")
    
    def test_date_range(self):
        """Test date range criteria"""
        criteria = self.search_ops._build_search_criteria(
            None, "all", "2024-01-01", "2024-01-31", False
        )
        self.assertIn("SINCE", criteria)
        self.assertIn("BEFORE", criteria)
    
    def test_combined_criteria(self):
        """Test combined search criteria"""
        criteria = self.search_ops._build_search_criteria(
            "important", "subject", "2024-01-01", None, True
        )
        self.assertIn('SUBJECT "important"', criteria)
        self.assertIn("SINCE", criteria)
        self.assertIn("UNSEEN", criteria)


class TestConfigValidation(unittest.TestCase):
    """Test configuration validation"""
    
    def test_provider_config(self):
        """Test email provider configurations"""
        from src.connection_manager import ConnectionManager
        
        # Test known provider
        config = {'email': 'test@gmail.com', 'password': 'pass', 'provider': 'gmail'}
        conn_mgr = ConnectionManager(config)
        self.assertEqual(conn_mgr.config['imap_server'], 'imap.gmail.com')
        self.assertEqual(conn_mgr.config['smtp_server'], 'smtp.gmail.com')
        
        # Test custom provider
        config = {
            'email': 'test@company.com',
            'password': 'pass',
            'provider': 'custom',
            'imap_server': 'mail.company.com',
            'smtp_server': 'smtp.company.com'
        }
        conn_mgr = ConnectionManager(config)
        self.assertEqual(conn_mgr.config['imap_server'], 'mail.company.com')
        self.assertEqual(conn_mgr.config['smtp_server'], 'smtp.company.com')


if __name__ == '__main__':
    unittest.main()