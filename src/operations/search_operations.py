"""
Search operations for email queries
"""
import imaplib
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header
import email.utils

logger = logging.getLogger(__name__)

class SearchOperations:
    """Handles email search operations"""
    
    def __init__(self, connection_manager):
        self.connection_manager = connection_manager
    
    def search_emails(
        self,
        query: Optional[str] = None,
        search_in: str = "all",  # subject, from, body, to, all
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        folder: str = "INBOX",
        unread_only: bool = False,
        has_attachments: Optional[bool] = None,
        limit: int = 50,
        account_id: Optional[str] = None  # Accept but ignore since connection is already account-specific
    ) -> Dict[str, Any]:
        """
        Search emails with various criteria
        
        Args:
            query: Search query text
            search_in: Where to search (subject/from/body/to/all)
            date_from: Start date (YYYY-MM-DD)
            date_to: End date (YYYY-MM-DD)
            folder: Folder to search in
            unread_only: Only search unread emails
            has_attachments: Filter by attachment presence
            limit: Maximum number of results
            
        Returns:
            Dict with search results
        """
        try:
            mail = self.connection_manager.connect_imap()
            
            try:
                # CRITICAL: Use only canonical account ID, no email fallback
                # to prevent cross-account routing issues
                canonical_account_id = self.connection_manager.account_id
                
                if not canonical_account_id:
                    logger.error("ConnectionManager missing account_id - this should never happen")
                    return {
                        'success': False,
                        'error': 'Account ID not configured properly',
                        'emails': []
                    }
                
                # Select folder
                result, data = mail.select(folder, readonly=True)
                if result != 'OK':
                    raise ValueError(f"Cannot select folder: {folder}")
                
                # Build search criteria
                search_criteria = self._build_search_criteria(
                    query, search_in, date_from, date_to, unread_only
                )
                
                logger.info(f"Search criteria: {search_criteria}")
                
                # Perform UID search (more stable than sequence numbers)
                try:
                    if isinstance(search_criteria, list):
                        result, data = mail.uid('search', None, *search_criteria)
                    else:
                        # Handle unicode in search criteria
                        if any(ord(c) > 127 for c in str(search_criteria)):
                            # Try UTF-8 charset for non-ASCII search
                            try:
                                result, data = mail.uid('search', 'UTF-8', search_criteria)
                            except Exception as e:
                                logger.warning(f"UTF-8 charset search failed (expected for 163/QQ): {e}, trying without charset")
                                # Encode the search string properly
                                search_bytes = search_criteria.encode('utf-8')
                                result, data = mail.uid('search', None, search_bytes)
                        else:
                            result, data = mail.uid('search', None, search_criteria)
                except Exception as e:
                    logger.error(f"Search error: {e}")
                    # Fallback to basic search if charset fails
                    result, data = mail.uid('search', None, 'ALL')
                
                if result != 'OK':
                    raise ValueError("Search failed")
                
                # Check for None/empty data
                if not data or not data[0]:
                    return {
                        'success': True,
                        'emails': [],
                        'total_found': 0,
                        'search_criteria': str(search_criteria),
                        'folder': folder,
                        'account': self.connection_manager.email,
                        'account_id': canonical_account_id
                    }
                
                email_uids = data[0].split()
                total_found = len(email_uids)
                
                # Limit results
                email_uids = email_uids[-limit:]
                email_uids.reverse()  # Most recent first
                
                # Fetch email details
                emails = []
                for uid in email_uids:
                    try:
                        email_data = self._fetch_email_summary(mail, uid, use_uid=True)
                        
                        # Filter by attachments if specified
                        if has_attachments is not None:
                            email_has_attachments = email_data.get('has_attachments', False)
                            if has_attachments != email_has_attachments:
                                continue
                        
                        # Additional filtering for body search (IMAP doesn't support body search well)
                        if query and search_in in ['body', 'all']:
                            if not self._check_body_contains(mail, uid, query, use_uid=True):
                                if search_in == 'body':
                                    continue
                        
                        # Add account_id to each email (use real account ID for proper routing)
                        email_data['account_id'] = canonical_account_id
                        
                        emails.append(email_data)
                        
                    except Exception as e:
                        logger.warning(f"Failed to fetch email UID {uid}: {e}")
                
                return {
                    'success': True,
                    'emails': emails,
                    'total_found': total_found,
                    'displayed': len(emails),
                    'search_criteria': str(search_criteria),
                    'folder': folder,
                    'account': self.connection_manager.email,
                    'account_id': canonical_account_id
                }
                
            finally:
                mail.close()
                mail.logout()
                
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'account': self.connection_manager.email
            }
    
    def _build_search_criteria(
        self,
        query: Optional[str],
        search_in: str,
        date_from: Optional[str],
        date_to: Optional[str],
        unread_only: bool
    ) -> str:
        """Build IMAP search criteria"""
        criteria = []
        
        # Text search
        if query:
            # For non-ASCII characters, we need to encode properly
            # Most IMAP servers support UTF-8 search
            if search_in == "subject":
                criteria.append(f'SUBJECT "{query}"')
            elif search_in == "from":
                criteria.append(f'FROM "{query}"')
            elif search_in == "to":
                criteria.append(f'TO "{query}"')
            elif search_in == "all":
                # Search in multiple fields - use simpler approach
                # Some servers don't support complex OR queries well
                criteria.append(f'TEXT "{query}"')
            elif search_in == "body":
                criteria.append(f'BODY "{query}"')
        
        # Date range
        if date_from:
            try:
                date_obj = datetime.strptime(date_from, "%Y-%m-%d")
                imap_date = date_obj.strftime("%d-%b-%Y")
                criteria.append(f'SINCE {imap_date}')
            except:
                logger.warning(f"Invalid date_from format: {date_from}")
        
        if date_to:
            try:
                date_obj = datetime.strptime(date_to, "%Y-%m-%d")
                imap_date = date_obj.strftime("%d-%b-%Y")
                criteria.append(f'BEFORE {imap_date}')
            except:
                logger.warning(f"Invalid date_to format: {date_to}")
        
        # Unread filter
        if unread_only:
            criteria.append('UNSEEN')
        
        # If no criteria, search all
        if not criteria:
            return 'ALL'
        
        # Join criteria
        if len(criteria) == 1:
            return criteria[0]
        else:
            return ' '.join(criteria)
    
    def _fetch_email_summary(self, mail: imaplib.IMAP4_SSL, email_id: str, use_uid: bool = False) -> Dict[str, Any]:
        """Fetch summary information for an email"""
        # Fetch email data using UID if specified
        if use_uid:
            result, data = mail.uid('fetch', email_id, '(RFC822.HEADER FLAGS)')
        else:
            result, data = mail.fetch(email_id, '(RFC822.HEADER FLAGS)')
        
        if result != 'OK' or not data or not data[0] or data[0] in (None, b''):
            raise ValueError(f"Failed to fetch email {email_id}")
        
        # Parse FLAGS from response - more robust parsing
        # IMAP response format: (b'1 (FLAGS (\\Seen) RFC822.HEADER {size}', b'header...')
        flags_str = ""
        try:
            # Combine all response parts to handle multi-tuple responses
            for item in data:
                if isinstance(item, tuple) and len(item) > 0:
                    if isinstance(item[0], bytes):
                        flags_str += item[0].decode('utf-8', errors='ignore')
        except:
            flags_str = ""
        
        is_unread = '\\Seen' not in flags_str
        is_flagged = '\\Flagged' in flags_str
        
        # Parse headers
        header_data = data[0][1]
        if not header_data:
            raise ValueError(f"Email {email_id} has no header data")
        msg = message_from_bytes(header_data)
        
        # Decode subject
        subject = msg.get('Subject', 'No Subject')
        decoded_subject = decode_header(subject)
        subject = ""
        for text, encoding in decoded_subject:
            if isinstance(text, bytes):
                subject += text.decode(encoding or 'utf-8', errors='ignore')
            else:
                subject += text
        
        # Get other fields
        from_addr = msg.get('From', 'Unknown')
        to_addr = msg.get('To', '')
        date_str = msg.get('Date', '')
        message_id = msg.get('Message-ID', '')
        
        # Parse date
        try:
            date_tuple = email.utils.parsedate_to_datetime(date_str)
            date_formatted = date_tuple.strftime("%Y-%m-%d %H:%M:%S")
        except:
            date_formatted = date_str
        
        # Check for attachments (simplified check based on content-type)
        has_attachments = 'multipart' in msg.get_content_type().lower()
        
        email_id_str = email_id.decode() if isinstance(email_id, bytes) else str(email_id)
        
        return {
            'id': email_id_str,
            'uid': email_id_str if use_uid else None,  # Include UID if used
            'subject': subject,
            'from': from_addr,
            'to': to_addr,
            'date': date_formatted,
            'unread': is_unread,
            'flagged': is_flagged,
            'has_attachments': has_attachments,
            'message_id': message_id
        }
    
    def _check_body_contains(self, mail: imaplib.IMAP4_SSL, email_id: str, query: str, use_uid: bool = False) -> bool:
        """Check if email body contains the query text"""
        try:
            # Fetch full email using UID if specified
            if use_uid:
                result, data = mail.uid('fetch', email_id, '(RFC822)')
            else:
                result, data = mail.fetch(email_id, '(RFC822)')
                
            if result != 'OK' or not data or not data[0] or data[0] in (None, b''):
                return False
            
            # Parse email
            raw_email = data[0][1]
            if not raw_email:
                return False
            msg = message_from_bytes(raw_email)
            
            # Extract body text
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    elif part.get_content_type() == "text/html":
                        body_text += part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                body_text = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            # Case-insensitive search
            return query.lower() in body_text.lower()
            
        except Exception as e:
            logger.warning(f"Failed to check body for email {email_id}: {e}")
            return False
    
    def search_by_sender(self, sender_email: str, folder: str = "INBOX", limit: int = 50) -> Dict[str, Any]:
        """Search emails by sender email address"""
        return self.search_emails(
            query=sender_email,
            search_in="from",
            folder=folder,
            limit=limit
        )
    
    def search_unread(self, folder: str = "INBOX", limit: int = 50) -> Dict[str, Any]:
        """Get all unread emails"""
        return self.search_emails(
            unread_only=True,
            folder=folder,
            limit=limit
        )
    
    def search_recent(self, days: int = 7, folder: str = "INBOX", limit: int = 50) -> Dict[str, Any]:
        """Search emails from the last N days"""
        date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        return self.search_emails(
            date_from=date_from,
            folder=folder,
            limit=limit
        )
    
    def search_with_attachments(self, folder: str = "INBOX", limit: int = 50) -> Dict[str, Any]:
        """Search emails that have attachments"""
        return self.search_emails(
            has_attachments=True,
            folder=folder,
            limit=limit
        )
