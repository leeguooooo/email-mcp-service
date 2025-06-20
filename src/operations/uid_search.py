"""
IMAP UID-based search implementation for better performance and stability
"""
import imaplib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import email
from email.header import decode_header
import re

logger = logging.getLogger(__name__)

class UIDSearchEngine:
    """Optimized search engine using IMAP UIDs instead of sequence numbers"""
    
    def __init__(self, connection: imaplib.IMAP4_SSL):
        self.connection = connection
        
    def search_by_criteria(
        self,
        query: str,
        search_in: str = "all",
        unread_only: bool = False,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        folder: str = "INBOX",
        limit: int = 50
    ) -> Tuple[List[str], int]:
        """
        Search emails using IMAP UID commands
        
        Returns:
            Tuple of (list of UIDs, total count)
        """
        try:
            # Select folder
            status, data = self.connection.select(folder)
            if status != 'OK':
                raise Exception(f"Cannot select folder {folder}")
            
            # Build search criteria
            search_criteria = self._build_search_criteria(
                query, search_in, unread_only, date_from, date_to
            )
            
            # Use UID SEARCH instead of regular SEARCH
            logger.info(f"Searching with criteria: {search_criteria}")
            status, data = self.connection.uid('SEARCH', None, search_criteria)
            
            if status != 'OK':
                return [], 0
            
            # Get UIDs
            uids = data[0].split() if data[0] else []
            total_count = len(uids)
            
            # Limit results (get most recent)
            if total_count > limit:
                uids = uids[-limit:]  # Get last N items (most recent)
            
            return [uid.decode() for uid in uids], total_count
            
        except Exception as e:
            logger.error(f"UID search failed: {e}")
            return [], 0
    
    def fetch_emails_by_uids(
        self,
        uids: List[str],
        include_body: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails using UIDs with batch optimization
        """
        if not uids:
            return []
        
        emails = []
        
        try:
            # Batch fetch headers for all UIDs
            uid_string = ','.join(uids)
            
            # Determine what to fetch
            if include_body:
                fetch_cmd = '(RFC822.HEADER BODY.PEEK[TEXT] FLAGS UID)'
            else:
                fetch_cmd = '(RFC822.HEADER FLAGS UID)'
            
            # Batch fetch
            status, data = self.connection.uid('FETCH', uid_string, fetch_cmd)
            
            if status != 'OK':
                return []
            
            # Process fetched data
            for response_part in data:
                if isinstance(response_part, tuple):
                    # Parse email data
                    email_data = self._parse_email_data(response_part, include_body)
                    if email_data:
                        emails.append(email_data)
            
            # Sort by date (newest first)
            emails.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
            
            return emails
            
        except Exception as e:
            logger.error(f"Failed to fetch emails by UIDs: {e}")
            return []
    
    def _build_search_criteria(
        self,
        query: str,
        search_in: str,
        unread_only: bool,
        date_from: Optional[str],
        date_to: Optional[str]
    ) -> str:
        """Build IMAP search criteria string"""
        criteria_parts = []
        
        # Date range filter (default to last 30 days for performance)
        if not date_from and not date_to:
            # Default to last 30 days
            date_from = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
        
        if date_from:
            criteria_parts.append(f'SINCE {self._format_date(date_from)}')
        if date_to:
            criteria_parts.append(f'BEFORE {self._format_date(date_to)}')
        
        # Unread filter
        if unread_only:
            criteria_parts.append('UNSEEN')
        
        # Query filter
        if query:
            # Handle encoding for non-ASCII characters
            encoded_query = self._encode_search_query(query)
            
            if search_in == "subject":
                criteria_parts.append(f'SUBJECT "{encoded_query}"')
            elif search_in == "from":
                criteria_parts.append(f'FROM "{encoded_query}"')
            elif search_in == "to":
                criteria_parts.append(f'TO "{encoded_query}"')
            elif search_in == "body":
                criteria_parts.append(f'BODY "{encoded_query}"')
            else:  # all
                # Use OR for multiple fields
                criteria_parts.append(
                    f'OR OR OR SUBJECT "{encoded_query}" FROM "{encoded_query}" '
                    f'TO "{encoded_query}" BODY "{encoded_query}"'
                )
        
        # Join criteria
        if criteria_parts:
            return ' '.join(criteria_parts)
        else:
            return 'ALL'
    
    def _encode_search_query(self, query: str) -> str:
        """Encode query for IMAP search, handling CJK characters"""
        try:
            # Try UTF-8 encoding first
            query.encode('ascii')
            return query
        except UnicodeEncodeError:
            # For non-ASCII (Chinese, Japanese, etc.), use UTF-8
            # Some IMAP servers support CHARSET UTF-8
            return query
    
    def _format_date(self, date_str: str) -> str:
        """Format date for IMAP search"""
        try:
            # Parse various date formats
            for fmt in ['%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%d-%b-%Y")
                except ValueError:
                    continue
            return date_str
        except:
            return date_str
    
    def _parse_email_data(
        self,
        response_part: Tuple,
        include_body: bool
    ) -> Optional[Dict[str, Any]]:
        """Parse email data from IMAP response"""
        try:
            # Extract message parts
            msg_data = response_part[1]
            if not isinstance(msg_data, bytes):
                return None
            
            # Parse headers
            msg = email.message_from_bytes(msg_data)
            
            # Extract UID from response
            uid_match = re.search(br'UID (\d+)', response_part[0])
            uid = uid_match.group(1).decode() if uid_match else None
            
            # Extract flags
            flags_match = re.search(br'FLAGS \((.*?)\)', response_part[0])
            flags = flags_match.group(1).decode() if flags_match else ""
            is_read = '\\Seen' in flags
            is_flagged = '\\Flagged' in flags
            
            # Parse headers
            subject = self._decode_header(msg['Subject'] or '')
            from_addr = self._decode_header(msg['From'] or '')
            to_addr = self._decode_header(msg['To'] or '')
            date_str = msg['Date'] or ''
            
            # Parse date
            try:
                date_tuple = email.utils.parsedate_tz(date_str)
                timestamp = email.utils.mktime_tz(date_tuple) if date_tuple else 0
            except:
                timestamp = 0
            
            email_data = {
                'uid': uid,
                'subject': subject,
                'from': from_addr,
                'to': to_addr,
                'date': date_str,
                'timestamp': timestamp,
                'is_read': is_read,
                'is_flagged': is_flagged,
                'has_attachments': self._has_attachments(msg)
            }
            
            # Add body if requested
            if include_body:
                email_data['preview'] = self._get_email_preview(msg)
            
            return email_data
            
        except Exception as e:
            logger.error(f"Failed to parse email data: {e}")
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
        return False
    
    def _get_email_preview(self, msg: email.message.Message, length: int = 200) -> str:
        """Get email body preview"""
        try:
            body = ""
            
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
            
            # Clean and truncate
            body = re.sub(r'\s+', ' ', body).strip()
            if len(body) > length:
                body = body[:length] + "..."
            
            return body
        except:
            return ""