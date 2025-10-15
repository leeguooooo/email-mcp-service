"""
Communication service layer - Clean interface for sending/replying emails
"""
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class CommunicationService:
    """Service layer for communication operations"""
    
    def __init__(self, account_manager):
        """
        Initialize communication service
        
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
    
    def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, str]]] = None,
        is_html: bool = False,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a new email
        
        Args:
            to: Recipient email addresses
            subject: Email subject
            body: Email body content
            cc: CC recipients
            bcc: BCC recipients
            attachments: File attachments
            is_html: Whether body is HTML
            account_id: Send from specific account
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.smtp_operations import SMTPOperations
            
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            smtp_ops = SMTPOperations(conn_mgr)
            
            result = smtp_ops.send_email(
                to=to,
                subject=subject,
                body=body,
                cc=cc,
                bcc=bcc,
                attachments=attachments,
                is_html=is_html
            )
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"Send email failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def reply_email(
        self,
        email_id: str,
        body: str,
        reply_all: bool = False,
        folder: str = 'INBOX',
        attachments: Optional[List[Dict[str, str]]] = None,
        is_html: bool = False,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reply to an email
        
        Args:
            email_id: ID of email to reply to
            body: Reply body content
            reply_all: Reply to all recipients
            folder: Folder containing original email
            attachments: File attachments
            is_html: Whether body is HTML
            account_id: Reply from specific account
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.smtp_operations import SMTPOperations
            
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            smtp_ops = SMTPOperations(conn_mgr)
            
            result = smtp_ops.reply_email(
                email_id=email_id,
                body=body,
                reply_all=reply_all,
                folder=folder,
                attachments=attachments,
                is_html=is_html
            )
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"Reply email failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}
    
    def forward_email(
        self,
        email_id: str,
        to: List[str],
        body: Optional[str] = None,
        folder: str = 'INBOX',
        include_attachments: bool = True,
        account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Forward an email
        
        Args:
            email_id: ID of email to forward
            to: Recipients to forward to
            body: Additional message (optional)
            folder: Folder containing original email
            include_attachments: Include original attachments
            account_id: Forward from specific account
            
        Returns:
            Dictionary with operation result and 'success' field
        """
        try:
            from ..connection_manager import ConnectionManager
            from ..operations.smtp_operations import SMTPOperations
            
            account = self.account_manager.get_account(account_id)
            if not account:
                return {'error': 'No email account configured', 'success': False}
            
            conn_mgr = ConnectionManager(account)
            smtp_ops = SMTPOperations(conn_mgr)
            
            result = smtp_ops.forward_email(
                email_id=email_id,
                to=to,
                body=body,
                folder=folder,
                include_attachments=include_attachments
            )
            return self._ensure_success_field(result)
            
        except Exception as e:
            logger.error(f"Forward email failed: {e}", exc_info=True)
            return {'error': str(e), 'success': False}

