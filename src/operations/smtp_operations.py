"""
SMTP operations for sending emails
"""
import logging
from typing import List, Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, formatdate
import os
import mimetypes
from pathlib import Path

logger = logging.getLogger(__name__)

class SMTPOperations:
    """Handles email sending operations"""
    
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
    
    def send_email(
        self,
        to: List[str],
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        is_html: bool = False,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an email
        
        Args:
            to: List of recipient email addresses
            subject: Email subject
            body: Email body (plain text or HTML)
            cc: List of CC recipients
            bcc: List of BCC recipients
            attachments: List of file paths to attach
            is_html: Whether the body is HTML
            reply_to: Reply-to address
            
        Returns:
            Dict with success status and message
        """
        try:
            # Create message
            msg = MIMEMultipart('mixed')
            msg['From'] = formataddr((self.connection_manager.email.split('@')[0], self.connection_manager.email))
            msg['To'] = ', '.join(to)
            msg['Subject'] = subject
            msg['Date'] = formatdate(localtime=True)
            
            if cc:
                msg['Cc'] = ', '.join(cc)
            
            if reply_to:
                msg['Reply-To'] = reply_to
            
            # Add body
            if is_html:
                # Create alternative container for plain text and HTML
                msg_alternative = MIMEMultipart('alternative')
                
                # Add plain text version (simple strip of HTML tags)
                text_body = body.replace('<br>', '\n').replace('</p>', '\n\n')
                import re
                text_body = re.sub('<[^<]+?>', '', text_body)
                msg_alternative.attach(MIMEText(text_body, 'plain', 'utf-8'))
                
                # Add HTML version
                msg_alternative.attach(MIMEText(body, 'html', 'utf-8'))
                msg.attach(msg_alternative)
            else:
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if os.path.isfile(file_path):
                        self._attach_file(msg, file_path)
                    else:
                        logger.warning(f"Attachment not found: {file_path}")
            
            # Connect and send
            server = self.connection_manager.connect_smtp()
            
            try:
                # Combine all recipients
                all_recipients = list(to)
                if cc:
                    all_recipients.extend(cc)
                if bcc:
                    all_recipients.extend(bcc)
                
                # Send email
                server.send_message(msg, from_addr=self.connection_manager.email, to_addrs=all_recipients)
                
                logger.info(f"✅ Email sent successfully to {', '.join(to)}")
                
                return {
                    'success': True,
                    'message': f'Email sent successfully to {len(all_recipients)} recipient(s)',
                    'recipients': all_recipients,
                    'from': self.connection_manager.email
                }
                
            finally:
                server.quit()
                
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {
                'success': False,
                'error': str(e),
                'from': self.connection_manager.email
            }
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str):
        """Attach a file to the email message"""
        try:
            # Guess the content type
            ctype, encoding = mimetypes.guess_type(file_path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            
            maintype, subtype = ctype.split('/', 1)
            
            # Read file
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Create attachment
            attachment = MIMEBase(maintype, subtype)
            attachment.set_payload(file_data)
            encoders.encode_base64(attachment)
            
            # Add header
            filename = os.path.basename(file_path)
            attachment.add_header(
                'Content-Disposition',
                f'attachment; filename="{filename}"'
            )
            
            msg.attach(attachment)
            logger.info(f"Attached file: {filename}")
            
        except Exception as e:
            logger.error(f"Failed to attach file {file_path}: {e}")
            raise
    
    def reply_email(
        self,
        original_msg: Dict[str, Any],
        body: str,
        reply_all: bool = False,
        attachments: Optional[List[str]] = None,
        is_html: bool = False
    ) -> Dict[str, Any]:
        """
        Reply to an email
        
        Args:
            original_msg: Original message data (from get_email_detail)
            body: Reply body
            reply_all: Whether to reply to all recipients
            attachments: List of file paths to attach
            is_html: Whether the body is HTML
            
        Returns:
            Dict with success status and message
        """
        try:
            # Determine recipients
            to = [original_msg['from']]
            cc = []
            
            if reply_all:
                # Add original recipients (excluding self)
                original_to = original_msg.get('to', '').split(', ')
                original_cc = original_msg.get('cc', '').split(', ')
                
                for addr in original_to + original_cc:
                    addr = addr.strip()
                    if addr and addr != self.connection_manager.email and addr not in to:
                        cc.append(addr)
            
            # Prepare subject
            subject = original_msg['subject']
            if not subject.lower().startswith('re:'):
                subject = f"Re: {subject}"
            
            # Prepare body with quote
            quoted_body = self._quote_original_message(original_msg)
            if is_html:
                full_body = f"{body}<br><br>{quoted_body}"
            else:
                full_body = f"{body}\n\n{quoted_body}"
            
            # Add reply headers
            reply_to = original_msg.get('message-id')
            
            return self.send_email(
                to=to,
                subject=subject,
                body=full_body,
                cc=cc if cc else None,
                attachments=attachments,
                is_html=is_html,
                reply_to=reply_to
            )
            
        except Exception as e:
            logger.error(f"Failed to reply to email: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def forward_email(
        self,
        original_msg: Dict[str, Any],
        to: List[str],
        body: Optional[str] = None,
        include_attachments: bool = True
    ) -> Dict[str, Any]:
        """
        Forward an email
        
        Args:
            original_msg: Original message data (from get_email_detail)
            to: List of recipient email addresses
            body: Optional forward message
            include_attachments: Whether to include original attachments
            
        Returns:
            Dict with success status and message
        """
        try:
            # Prepare subject
            subject = original_msg['subject']
            if not subject.lower().startswith('fwd:'):
                subject = f"Fwd: {subject}"
            
            # Prepare body
            forward_header = f"""---------- Forwarded message ----------
From: {original_msg['from']}
Date: {original_msg['date']}
Subject: {original_msg['subject']}
To: {original_msg['to']}"""
            
            if original_msg.get('cc'):
                forward_header += f"\nCc: {original_msg['cc']}"
            
            forward_header += "\n\n"
            
            # Combine with original body
            original_body = original_msg.get('body', '')
            if body:
                full_body = f"{body}\n\n{forward_header}{original_body}"
            else:
                full_body = f"{forward_header}{original_body}"
            
            # Handle attachments if needed
            attachments = None
            if include_attachments and original_msg.get('attachments'):
                # Note: This would require downloading attachments first
                # For now, we'll skip actual attachment forwarding
                logger.info("Attachment forwarding not yet implemented")
            
            return self.send_email(
                to=to,
                subject=subject,
                body=full_body,
                attachments=attachments,
                is_html=False
            )
            
        except Exception as e:
            logger.error(f"Failed to forward email: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _quote_original_message(self, original_msg: Dict[str, Any]) -> str:
        """Format original message for quoting in reply"""
        quote = f"On {original_msg['date']}, {original_msg['from']} wrote:\n"
        
        # Quote each line of the original body
        original_body = original_msg.get('body', '')
        quoted_lines = [f"> {line}" for line in original_body.split('\n')]
        quote += '\n'.join(quoted_lines)
        
        return quote