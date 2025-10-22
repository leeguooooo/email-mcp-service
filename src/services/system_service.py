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
            for account_id, acc in accounts.items():
                account_info = {
                    'id': account_id,
                    'email': acc.get('email'),
                    'provider': acc.get('provider'),
                    'description': acc.get('description', ''),
                    'imap_host': acc.get('imap_server'),
                    'smtp_host': acc.get('smtp_server')
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
    
    def get_recent_activity(
        self,
        account_id: str = None,
        include_stats: bool = True
    ) -> Dict[str, Any]:
        """
        Get recent sync activity and connection statistics (atomic operation)
        
        Args:
            account_id: Get activity for specific account (optional)
            include_stats: Include detailed statistics
            
        Returns:
            Dictionary containing recent activity with 'success' field
        """
        try:
            from datetime import datetime
            import json
            from pathlib import Path
            
            # Try to load sync health history
            history_file = Path("data/sync_health_history.json")
            health_data = {}
            
            if history_file.exists():
                try:
                    with open(history_file, 'r') as f:
                        health_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load sync health history: {e}")
            
            # Get accounts to check
            if account_id:
                accounts_to_check = [(account_id, self.account_manager.get_account(account_id))]
            else:
                accounts_to_check = [
                    (acc_id, acc) 
                    for acc_id, acc in self.account_manager.get_all_accounts().items()
                ]
            
            activity_list = []
            
            for acc_id, account in accounts_to_check:
                if not account:
                    continue
                
                acc_health = health_data.get(acc_id, {})
                
                activity_info = {
                    'account': account.get('email', acc_id),
                    'account_id': acc_id,
                    'last_sync': acc_health.get('last_sync_time', 'Never'),
                    'last_error': acc_health.get('last_error'),
                    'include_stats': include_stats
                }
                
                if include_stats:
                    activity_info['success_rate'] = acc_health.get('success_rate', 0.0)
                    activity_info['total_syncs'] = acc_health.get('total_syncs', 0)
                    activity_info['failed_syncs'] = acc_health.get('failed_syncs', 0)
                    activity_info['health_score'] = acc_health.get('health_score', 100.0)
                
                activity_list.append(activity_info)
            
            return {
                'success': True,
                'accounts': activity_list,
                'total_accounts': len(activity_list),
                'generated_at': datetime.utcnow().isoformat() + 'Z'
            }
            
        except Exception as e:
            logger.error(f"Get recent activity failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}