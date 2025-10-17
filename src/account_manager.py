"""
Account management for multiple email accounts
"""
import json
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

class AccountManager:
    """Manages multiple email account configurations"""
    
    def __init__(self, config_file: str = "accounts.json"):
        self.config_file = Path(config_file)
        self.accounts_data = self._load_accounts()
    
    def _load_accounts(self) -> Dict[str, Any]:
        """Load accounts from configuration file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load accounts: {e}")
                return {"accounts": {}, "default_account": None}
        return {"accounts": {}, "default_account": None}
    
    def _save_accounts(self):
        """Save accounts to configuration file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.accounts_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Accounts saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")
            raise
    
    def get_account(self, account_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get account configuration by ID
        
        Args:
            account_id: Account ID to retrieve. If None, returns default account
            
        Returns:
            Account configuration dict or None
        """
        accounts = self.accounts_data.get('accounts', {})
        
        if not accounts:
            # Fallback to environment variables
            email = os.getenv('EMAIL_ADDRESS')
            password = os.getenv('EMAIL_PASSWORD')
            provider = os.getenv('EMAIL_PROVIDER', '163')
            
            if email and password:
                return {
                    'email': email,
                    'password': password,
                    'provider': provider,
                    'description': 'Environment variable account',
                    'id': 'env_default'
                }
            return None
        
        # Get specific account or default
        if account_id:
            account_data = accounts.get(account_id)
            if account_data:
                # Add the ID to the account data
                result = account_data.copy()
                result['id'] = account_id
                return result
            
            # Fallback: allow lookup by email address
            if '@' in account_id:
                for acc_id, acc_data in accounts.items():
                    if acc_data.get('email') == account_id:
                        result = acc_data.copy()
                        result['id'] = acc_id
                        return result
        
        # Return default account
        default_id = self.accounts_data.get('default_account')
        if default_id and default_id in accounts:
            result = accounts[default_id].copy()
            result['id'] = default_id
            return result
        
        # Return first account if no default
        if accounts:
            first_id = list(accounts.keys())[0]
            result = accounts[first_id].copy()
            result['id'] = first_id
            return result
        
        return None
    
    def list_accounts(self) -> List[Dict[str, Any]]:
        """
        List all configured accounts
        
        Returns:
            List of account information
        """
        accounts = self.accounts_data.get('accounts', {})
        default_id = self.accounts_data.get('default_account')
        
        account_list = []
        for account_id, account_data in accounts.items():
            account_info = {
                'id': account_id,
                'email': account_data.get('email'),
                'provider': account_data.get('provider'),
                'description': account_data.get('description', ''),
                'is_default': account_id == default_id
            }
            account_list.append(account_info)
        
        return account_list
    
    def add_account(
        self, 
        email: str, 
        password: str, 
        provider: str = "custom",
        description: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Add a new account
        
        Args:
            email: Email address
            password: Password or auth code
            provider: Email provider
            description: Optional description
            **kwargs: Additional provider-specific settings
            
        Returns:
            Account ID
        """
        # Generate account ID
        account_id = f"{email.split('@')[0]}_{provider}"
        
        # Ensure unique ID
        counter = 1
        original_id = account_id
        while account_id in self.accounts_data.get('accounts', {}):
            account_id = f"{original_id}_{counter}"
            counter += 1
        
        # Create account config
        account_config = {
            'email': email,
            'password': password,
            'provider': provider,
            'description': description or f"{provider} account"
        }
        
        # Add additional settings
        account_config.update(kwargs)
        
        # Save account
        if 'accounts' not in self.accounts_data:
            self.accounts_data['accounts'] = {}
        
        self.accounts_data['accounts'][account_id] = account_config
        
        # Set as default if first account
        if not self.accounts_data.get('default_account'):
            self.accounts_data['default_account'] = account_id
        
        self._save_accounts()
        logger.info(f"✅ Added account: {email} (ID: {account_id})")
        
        return account_id
    
    def remove_account(self, account_id: str) -> bool:
        """
        Remove an account
        
        Args:
            account_id: Account ID to remove
            
        Returns:
            True if removed successfully
        """
        accounts = self.accounts_data.get('accounts', {})
        
        if account_id not in accounts:
            logger.warning(f"Account not found: {account_id}")
            return False
        
        # Remove account
        del accounts[account_id]
        
        # Update default if needed
        if self.accounts_data.get('default_account') == account_id:
            if accounts:
                self.accounts_data['default_account'] = list(accounts.keys())[0]
            else:
                self.accounts_data['default_account'] = None
        
        self._save_accounts()
        logger.info(f"✅ Removed account: {account_id}")
        
        return True
    
    def set_default_account(self, account_id: str) -> bool:
        """
        Set default account
        
        Args:
            account_id: Account ID to set as default
            
        Returns:
            True if set successfully
        """
        accounts = self.accounts_data.get('accounts', {})
        
        if account_id not in accounts:
            logger.warning(f"Account not found: {account_id}")
            return False
        
        self.accounts_data['default_account'] = account_id
        self._save_accounts()
        
        logger.info(f"✅ Set default account: {account_id}")
        return True
    
    def get_all_accounts(self) -> Dict[str, Dict[str, Any]]:
        """Get all account configurations"""
        return self.accounts_data.get('accounts', {})
    
    def update_account(self, account_id: str, **kwargs) -> bool:
        """
        Update account configuration
        
        Args:
            account_id: Account ID to update
            **kwargs: Fields to update
            
        Returns:
            True if updated successfully
        """
        accounts = self.accounts_data.get('accounts', {})
        
        if account_id not in accounts:
            logger.warning(f"Account not found: {account_id}")
            return False
        
        # Update fields
        accounts[account_id].update(kwargs)
        self._save_accounts()
        
        logger.info(f"✅ Updated account: {account_id}")
        return True
