"""
Email connection manager for IMAP and SMTP connections
"""
import imaplib
import smtplib
import ssl
import logging
from typing import Optional, Dict, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages IMAP and SMTP connections for email operations"""
    
    # Email provider configurations
    EMAIL_PROVIDERS = {
        "163": {
            "imap_server": "imap.163.com",
            "imap_port": 993,
            "smtp_server": "smtp.163.com", 
            "smtp_port": 465,
            "use_imap_id": True,
            "use_ssl": True
        },
        "gmail": {
            "imap_server": "imap.gmail.com",
            "imap_port": 993,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "use_imap_id": False,
            "use_tls": True
        },
        "qq": {
            "imap_server": "imap.qq.com",
            "imap_port": 993,
            "smtp_server": "smtp.qq.com",
            "smtp_port": 465,
            "use_imap_id": False,
            "use_ssl": True
        },
        "outlook": {
            "imap_server": "outlook.office365.com",
            "imap_port": 993,
            "smtp_server": "smtp.office365.com",
            "smtp_port": 587,
            "use_imap_id": False,
            "use_tls": True
        }
    }
    
    def __init__(self, account_config: Dict[str, Any]):
        """Initialize connection manager with account configuration"""
        self.email = account_config.get('email')
        self.password = account_config.get('password')
        self.provider = account_config.get('provider', 'custom')
        self.account_config = account_config
        
        # Get provider config or use custom settings
        if self.provider in self.EMAIL_PROVIDERS:
            self.config = self.EMAIL_PROVIDERS[self.provider].copy()
        else:
            # Custom provider configuration
            self.config = {
                'imap_server': account_config.get('imap_server'),
                'imap_port': account_config.get('imap_port', 993),
                'smtp_server': account_config.get('smtp_server'),
                'smtp_port': account_config.get('smtp_port', 465),
                'use_imap_id': False,
                'use_ssl': account_config.get('use_ssl', True),
                'use_tls': account_config.get('use_tls', False)
            }
    
    def send_imap_id(self, mail: imaplib.IMAP4_SSL) -> bool:
        """Send IMAP ID to solve 163 email 'Unsafe Login' issue"""
        try:
            id_args = [
                "name", "Mozilla Thunderbird",
                "version", "91.0", 
                "vendor", "Mozilla",
                "support-url", "https://support.mozilla.org/"
            ]
            
            tag = mail._new_tag()
            id_string = " ".join(f'"{arg}"' for arg in id_args)
            command = f'{tag.decode()} ID ({id_string})'
            mail.send(command.encode() + b'\r\n')
            
            while True:
                resp = mail.readline()
                resp_str = resp.decode().strip()
                if resp_str.startswith(tag.decode()):
                    if 'OK' in resp_str:
                        logger.info("✅ IMAP ID sent successfully")
                    return True
                elif resp_str.startswith('*'):
                    continue
                else:
                    break
            return True
        except Exception as e:
            logger.warning(f"Failed to send IMAP ID: {e}")
            return False
    
    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server"""
        if not self.config.get('imap_server'):
            raise ValueError("IMAP server not configured")
        
        logger.info(f"Connecting to IMAP server {self.config['imap_server']}:{self.config['imap_port']}")
        
        try:
            # Connect to server
            mail = imaplib.IMAP4_SSL(self.config['imap_server'], self.config['imap_port'])
            logger.info("✅ IMAP server connection established")
            
            # Send IMAP ID if needed (before login)
            if self.config.get('use_imap_id', False):
                self.send_imap_id(mail)
            
            # Login
            mail.login(self.email, self.password)
            logger.info(f"✅ IMAP login successful: {self.email}")
            
            # Send IMAP ID again after login if needed
            if self.config.get('use_imap_id', False):
                self.send_imap_id(mail)
            
            return mail
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            logger.error(f"IMAP error: {error_msg}")
            
            if "LOGIN" in error_msg.upper() or "AUTHENTICATIONFAILED" in error_msg:
                raise ValueError(f"Authentication failed for {self.email}. Check your password/auth code.")
            raise ValueError(f"IMAP connection failed: {error_msg}")
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            raise ValueError(f"Failed to connect to IMAP server: {str(e)}")
    
    def connect_smtp(self) -> smtplib.SMTP:
        """Connect to SMTP server"""
        if not self.config.get('smtp_server'):
            raise ValueError("SMTP server not configured")
        
        logger.info(f"Connecting to SMTP server {self.config['smtp_server']}:{self.config['smtp_port']}")
        
        try:
            # Create SMTP connection based on security settings
            if self.config.get('use_ssl', False):
                # SSL connection (port 465)
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(
                    self.config['smtp_server'], 
                    self.config['smtp_port'],
                    context=context
                )
            else:
                # Regular connection, may use STARTTLS
                server = smtplib.SMTP(
                    self.config['smtp_server'], 
                    self.config['smtp_port']
                )
                if self.config.get('use_tls', False):
                    # Upgrade to TLS (port 587)
                    context = ssl.create_default_context()
                    server.starttls(context=context)
            
            logger.info("✅ SMTP server connection established")
            
            # Login
            server.login(self.email, self.password)
            logger.info(f"✅ SMTP login successful: {self.email}")
            
            return server
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication error: {e}")
            raise ValueError(f"SMTP authentication failed for {self.email}. Check your password/auth code.")
            
        except Exception as e:
            logger.error(f"SMTP connection error: {e}")
            raise ValueError(f"Failed to connect to SMTP server: {str(e)}")
    
    def close_imap(self, mail: Optional[imaplib.IMAP4_SSL] = None):
        """Close IMAP connection"""
        if mail:
            try:
                mail.close()
                mail.logout()
            except:
                pass
    
    def close_smtp(self, server: Optional[smtplib.SMTP] = None):
        """Close SMTP connection"""
        if server:
            try:
                server.quit()
            except:
                pass

    def test_connection(self) -> Dict[str, Any]:
        """Test both IMAP and SMTP connections"""
        result = {
            'email': self.email,
            'provider': self.provider,
            'imap': {'success': False},
            'smtp': {'success': False}
        }
        
        # Test IMAP
        try:
            mail = self.connect_imap()
            mail.select('INBOX')
            
            # Get email count
            _, data = mail.search(None, 'ALL')
            total = len(data[0].split()) if data[0] else 0
            
            _, data = mail.search(None, 'UNSEEN')
            unread = len(data[0].split()) if data[0] else 0
            
            self.close_imap(mail)
            
            result['imap'] = {
                'success': True,
                'total_emails': total,
                'unread_emails': unread
            }
        except Exception as e:
            result['imap']['error'] = str(e)
        
        # Test SMTP
        try:
            server = self.connect_smtp()
            self.close_smtp(server)
            result['smtp'] = {'success': True}
        except Exception as e:
            result['smtp']['error'] = str(e)
        
        return result