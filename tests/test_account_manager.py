"""
Unit tests for AccountManager - no external dependencies
"""
import unittest
import json
import tempfile
import os
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.account_manager import AccountManager


class TestAccountManager(unittest.TestCase):
    """Test account management functionality"""
    
    def setUp(self):
        """Create temporary config file for testing"""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        self.temp_file.close()
        self.manager = AccountManager(self.temp_file.name)
    
    def tearDown(self):
        """Clean up temporary file"""
        os.unlink(self.temp_file.name)
    
    def test_empty_config(self):
        """Test with empty configuration"""
        accounts = self.manager.list_accounts()
        self.assertEqual(len(accounts), 0)
        self.assertIsNone(self.manager.get_account())
    
    def test_add_account(self):
        """Test adding an account"""
        account_id = self.manager.add_account(
            email="test@example.com",
            password="password123",
            provider="gmail",
            description="Test account"
        )
        
        self.assertIsNotNone(account_id)
        self.assertEqual(account_id, "test_gmail")
        
        # Verify account was added
        account = self.manager.get_account(account_id)
        self.assertIsNotNone(account)
        self.assertEqual(account['email'], "test@example.com")
        self.assertEqual(account['provider'], "gmail")
    
    def test_add_duplicate_account(self):
        """Test adding duplicate accounts"""
        # Add first account
        id1 = self.manager.add_account("test@example.com", "pass1", "gmail")
        
        # Add same email again
        id2 = self.manager.add_account("test@example.com", "pass2", "gmail")
        
        # Should have different IDs
        self.assertNotEqual(id1, id2)
        self.assertEqual(id1, "test_gmail")
        self.assertEqual(id2, "test_gmail_1")
    
    def test_remove_account(self):
        """Test removing an account"""
        # Add account
        account_id = self.manager.add_account("test@example.com", "pass", "gmail")
        
        # Remove it
        success = self.manager.remove_account(account_id)
        self.assertTrue(success)
        
        # Verify it's gone
        account = self.manager.get_account(account_id)
        self.assertIsNone(account)
        
        # Try removing non-existent account
        success = self.manager.remove_account("non_existent")
        self.assertFalse(success)
    
    def test_default_account(self):
        """Test default account management"""
        # First account should be default
        id1 = self.manager.add_account("test1@example.com", "pass1", "gmail")
        self.assertEqual(self.manager.accounts_data['default_account'], id1)
        
        # Add second account
        id2 = self.manager.add_account("test2@example.com", "pass2", "gmail")
        
        # Default should still be first
        self.assertEqual(self.manager.accounts_data['default_account'], id1)
        
        # Change default
        success = self.manager.set_default_account(id2)
        self.assertTrue(success)
        self.assertEqual(self.manager.accounts_data['default_account'], id2)
        
        # Get default account
        default = self.manager.get_account()
        self.assertEqual(default['email'], "test2@example.com")
    
    def test_list_accounts(self):
        """Test listing accounts"""
        # Add multiple accounts
        id1 = self.manager.add_account("test1@example.com", "pass1", "gmail")
        id2 = self.manager.add_account("test2@example.com", "pass2", "163")
        id3 = self.manager.add_account("test3@example.com", "pass3", "qq")
        
        accounts = self.manager.list_accounts()
        self.assertEqual(len(accounts), 3)
        
        # Check account info
        emails = [acc['email'] for acc in accounts]
        self.assertIn("test1@example.com", emails)
        self.assertIn("test2@example.com", emails)
        self.assertIn("test3@example.com", emails)
        
        # Check default flag
        default_accounts = [acc for acc in accounts if acc['is_default']]
        self.assertEqual(len(default_accounts), 1)
        self.assertEqual(default_accounts[0]['id'], id1)
    
    def test_update_account(self):
        """Test updating account configuration"""
        # Add account
        account_id = self.manager.add_account("test@example.com", "pass", "gmail")
        
        # Update it
        success = self.manager.update_account(
            account_id,
            password="new_password",
            description="Updated description"
        )
        self.assertTrue(success)
        
        # Verify changes
        account = self.manager.get_account(account_id)
        self.assertEqual(account['password'], "new_password")
        self.assertEqual(account['description'], "Updated description")
        self.assertEqual(account['email'], "test@example.com")  # Unchanged
    
    def test_custom_provider(self):
        """Test custom email provider"""
        account_id = self.manager.add_account(
            email="test@company.com",
            password="pass",
            provider="custom",
            imap_server="imap.company.com",
            imap_port=993,
            smtp_server="smtp.company.com",
            smtp_port=587
        )
        
        account = self.manager.get_account(account_id)
        self.assertEqual(account['imap_server'], "imap.company.com")
        self.assertEqual(account['smtp_server'], "smtp.company.com")
        self.assertEqual(account['imap_port'], 993)
        self.assertEqual(account['smtp_port'], 587)
    
    def test_env_fallback(self):
        """Test fallback to environment variables"""
        # Set env vars
        os.environ['EMAIL_ADDRESS'] = 'env@example.com'
        os.environ['EMAIL_PASSWORD'] = 'env_password'
        os.environ['EMAIL_PROVIDER'] = 'gmail'
        
        # Get account with empty config
        account = self.manager.get_account()
        self.assertIsNotNone(account)
        self.assertEqual(account['email'], 'env@example.com')
        self.assertEqual(account['password'], 'env_password')
        self.assertEqual(account['provider'], 'gmail')
        
        # Clean up
        del os.environ['EMAIL_ADDRESS']
        del os.environ['EMAIL_PASSWORD']
        del os.environ['EMAIL_PROVIDER']


if __name__ == '__main__':
    unittest.main()