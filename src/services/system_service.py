"""
System service layer - Clean interface for system operations
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class SystemService:
    """Service layer for system operations"""
    
    def __init__(self, account_manager):
        """
        Initialize system service
        
        Args:
            account_manager: AccountManager instance
        """
        self.account_manager = account_manager
    
    def _ensure_success_field(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure result has 'success' field for consistency
        
        Args:
            result: Operation result dictionary
            
        Returns:
            Result with guaranteed 'success' field
        """
        if 'success' not in result:
            result['success'] = 'error' not in result
        return result
    
    def check_connection(self) -> Dict[str, Any]:
        """
        Test email server connections (IMAP and SMTP) for all configured accounts
        
        Returns:
            Dictionary with connection test results and 'success' field
        """
        try:
            from ..legacy_operations import check_connection
            result = check_connection()
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"Check connection failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def list_accounts(self) -> Dict[str, Any]:
        """
        List all configured email accounts
        
        Returns:
            Dictionary containing accounts list
        """
        try:
            accounts = self.account_manager.get_all_accounts()
            
            account_list = []
            for acc in accounts:
                account_info = {
                    'email': acc.email,
                    'provider': acc.provider,
                    'imap_host': acc.imap_host,
                    'smtp_host': acc.smtp_host
                }
                account_list.append(account_info)
            
            return {
                'success': True,
                'accounts': account_list,
                'count': len(account_list)
            }
            
        except Exception as e:
            logger.error(f"List accounts failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}

