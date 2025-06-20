"""
Batch email fetching for improved performance
"""
import imaplib
import logging
from typing import List, Dict, Any, Optional, Tuple
import email
from email.header import decode_header
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class BatchEmailFetcher:
    """Fetch multiple emails in a single request for better performance"""
    
    def __init__(self, connection: imaplib.IMAP4_SSL):
        self.connection = connection
    
    def fetch_batch(
        self,
        email_ids: List[str],
        include_body: bool = False,
        folder: str = "INBOX"
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple emails in a single IMAP command
        
        Args:
            email_ids: List of email IDs (sequence numbers)
            include_body: Whether to include email body
            folder: Folder to fetch from
            
        Returns:
            List of email dictionaries
        """
        if not email_ids:
            return []
        
        try:
            # Select folder
            status, data = self.connection.select(folder, readonly=True)
            if status != 'OK':
                raise Exception(f"Cannot select folder {folder}")
            
            # Convert list to IMAP sequence
            # Group consecutive numbers for efficiency
            sequence = self._optimize_sequence(email_ids)
            
            # Determine what to fetch
            if include_body:
                fetch_parts = '(RFC822.HEADER BODY.PEEK[TEXT] FLAGS)'
            else:
                fetch_parts = '(RFC822.HEADER FLAGS)'
            
            logger.info(f"Batch fetching {len(email_ids)} emails with sequence: {sequence}")
            
            # Batch fetch
            status, data = self.connection.fetch(sequence, fetch_parts)
            if status != 'OK':
                logger.error(f"Batch fetch failed: {status}")
                return []
            
            # Parse results
            emails = []
            for response_part in data:
                if isinstance(response_part, tuple):
                    email_data = self._parse_email_response(response_part, include_body)
                    if email_data:
                        emails.append(email_data)
            
            # Sort by date (newest first)
            emails.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            logger.info(f"Successfully fetched {len(emails)} emails")
            return emails
            
        except Exception as e:
            logger.error(f"Batch fetch failed: {e}")
            return []
    
    def fetch_unread_batch(
        self,
        limit: int = 50,
        folder: str = "INBOX"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Efficiently fetch unread emails using batch operations
        
        Returns:
            Tuple of (emails list, total unread count)
        """
        try:
            # Select folder
            status, data = self.connection.select(folder, readonly=True)
            if status != 'OK':
                raise Exception(f"Cannot select folder {folder}")
            
            # Search for unread emails
            status, data = self.connection.search(None, 'UNSEEN')
            if status != 'OK':
                return [], 0
            
            unread_ids = data[0].split() if data[0] else []
            total_unread = len(unread_ids)
            
            if not unread_ids:
                return [], 0
            
            # Limit and reverse (newest first)
            if len(unread_ids) > limit:
                unread_ids = unread_ids[-limit:]
            
            # Convert bytes to strings
            unread_ids = [id.decode() for id in unread_ids]
            
            # Batch fetch
            emails = self.fetch_batch(unread_ids, include_body=False, folder=folder)
            
            return emails, total_unread
            
        except Exception as e:
            logger.error(f"Failed to fetch unread batch: {e}")
            return [], 0
    
    def _optimize_sequence(self, email_ids: List[str]) -> str:
        """
        Optimize email ID list into IMAP sequence format
        Groups consecutive numbers for efficiency
        
        Example: [1,2,3,5,6,9] -> "1:3,5:6,9"
        """
        if not email_ids:
            return ""
        
        # Convert to integers and sort
        try:
            ids = sorted([int(id) for id in email_ids])
        except:
            # Fallback to simple comma-separated
            return ','.join(email_ids)
        
        # Group consecutive numbers
        sequences = []
        start = ids[0]
        end = ids[0]
        
        for i in range(1, len(ids)):
            if ids[i] == end + 1:
                end = ids[i]
            else:
                if start == end:
                    sequences.append(str(start))
                else:
                    sequences.append(f"{start}:{end}")
                start = ids[i]
                end = ids[i]
        
        # Add last sequence
        if start == end:
            sequences.append(str(start))
        else:
            sequences.append(f"{start}:{end}")
        
        return ','.join(sequences)
    
    def _parse_email_response(
        self,
        response_part: Tuple,
        include_body: bool
    ) -> Optional[Dict[str, Any]]:
        """Parse email data from IMAP response"""
        try:
            # Extract email ID from response
            match = re.search(r'(\d+) \(', response_part[0].decode())
            email_id = match.group(1) if match else None
            
            # Parse headers
            header_data = response_part[1]
            if not isinstance(header_data, bytes):
                return None
            
            msg = email.message_from_bytes(header_data)
            
            # Extract flags
            flags_match = re.search(br'FLAGS \((.*?)\)', response_part[0])
            flags = flags_match.group(1).decode() if flags_match else ""
            is_unread = '\\Seen' not in flags
            is_flagged = '\\Flagged' in flags
            
            # Decode headers
            subject = self._decode_header(msg.get('Subject', ''))
            from_addr = self._decode_header(msg.get('From', ''))
            to_addr = self._decode_header(msg.get('To', ''))
            date_str = msg.get('Date', '')
            message_id = msg.get('Message-ID', '')
            
            # Parse date
            try:
                date_tuple = email.utils.parsedate_tz(date_str)
                timestamp = email.utils.mktime_tz(date_tuple) if date_tuple else 0
                date_formatted = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            except:
                timestamp = 0
                date_formatted = date_str
            
            # Check for attachments
            has_attachments = self._has_attachments(msg)
            
            email_data = {
                'id': email_id,
                'subject': subject,
                'from': from_addr,
                'to': to_addr,
                'date': date_formatted,
                'timestamp': timestamp,
                'unread': is_unread,
                'flagged': is_flagged,
                'has_attachments': has_attachments,
                'message_id': message_id
            }
            
            # Add body preview if requested
            if include_body:
                email_data['preview'] = self._get_body_preview(msg)
            
            return email_data
            
        except Exception as e:
            logger.error(f"Failed to parse email response: {e}")
            return None
    
    def _decode_header(self, header_value: str) -> str:
        """Decode email header handling various encodings"""
        if not header_value:
            return ""
        
        try:
            decoded_parts = decode_header(header_value)
            result = []
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        try:
                            result.append(part.decode(encoding))
                        except:
                            result.append(part.decode('utf-8', errors='ignore'))
                    else:
                        result.append(part.decode('utf-8', errors='ignore'))
                else:
                    result.append(str(part))
            
            return ' '.join(result)
        except:
            return str(header_value)
    
    def _has_attachments(self, msg: email.message.Message) -> bool:
        """Check if email has attachments"""
        for part in msg.walk():
            if part.get_content_disposition() == 'attachment':
                return True
            # Also check for inline images that might be considered attachments
            if part.get_content_type().startswith('image/'):
                return True
        return False
    
    def _get_body_preview(self, msg: email.message.Message, length: int = 200) -> str:
        """Get email body preview"""
        try:
            body = ""
            
            # Try to get plain text first
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
            
            # If no plain text, try HTML
            if not body:
                for part in msg.walk():
                    if part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            html = payload.decode(charset, errors='ignore')
                            # Simple HTML to text
                            body = re.sub('<[^<]+?>', ' ', html)
                            break
            
            # Clean and truncate
            body = re.sub(r'\s+', ' ', body).strip()
            if len(body) > length:
                body = body[:length] + "..."
            
            return body
        except:
            return ""