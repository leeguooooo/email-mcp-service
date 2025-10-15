# Services Layer

## Overview

The services layer provides clean, high-level interfaces for email operations, encapsulating business logic and reducing coupling between tool handlers and low-level operations.

## Architecture

```
Handlers → Services → Operations/Legacy
```

Services handle:
- Business logic and validation
- Automatic selection of optimized vs. standard operations
- Parallel vs. sequential operation decisions
- Error handling and result formatting
- Account management integration

## Services

### EmailService

Handles core email operations.

**Methods**:

```python
def list_emails(limit, unread_only, folder, account_id) -> Dict[str, Any]:
    """List emails with automatic optimization"""

def get_email_detail(email_id, folder, account_id) -> Dict[str, Any]:
    """Get detailed email content"""

def mark_emails(email_ids, mark_as, folder, account_id) -> Dict[str, Any]:
    """Mark emails as read/unread (auto-parallel for multiple emails)"""

def delete_emails(email_ids, folder, permanent, trash_folder, account_id) -> Dict[str, Any]:
    """Delete or move emails to trash (auto-parallel for multiple emails)"""

def search_emails(query, search_in, date_from, date_to, folder, ...) -> Dict[str, Any]:
    """Search emails across accounts"""
```

**Example**:
```python
from services import EmailService

email_service = EmailService(account_manager)

# List unread emails
result = email_service.list_emails(
    limit=50,
    unread_only=True,
    folder='INBOX'
)

# Mark multiple emails as read (automatically uses parallel operations)
result = email_service.mark_emails(
    email_ids=['1', '2', '3'],
    mark_as='read',
    folder='INBOX'
)
```

---

### CommunicationService

Handles sending, replying, and forwarding emails.

**Methods**:

```python
def send_email(to, subject, body, cc, bcc, attachments, is_html, account_id) -> Dict[str, Any]:
    """Send a new email"""

def reply_email(email_id, body, reply_all, folder, attachments, is_html, account_id) -> Dict[str, Any]:
    """Reply to an email (preserves thread)"""

def forward_email(email_id, to, body, folder, include_attachments, account_id) -> Dict[str, Any]:
    """Forward an email"""
```

**Example**:
```python
from services import CommunicationService

comm_service = CommunicationService(account_manager)

# Send email
result = comm_service.send_email(
    to=['user@example.com'],
    subject='Hello',
    body='World',
    is_html=False
)

# Reply to email
result = comm_service.reply_email(
    email_id='123',
    body='Thanks for your message!',
    reply_all=False
)
```

---

### FolderService

Handles folder operations and email organization.

**Methods**:

```python
def list_folders(account_id) -> Dict[str, Any]:
    """List all email folders"""

def move_emails_to_folder(email_ids, target_folder, source_folder, account_id) -> Dict[str, Any]:
    """Move emails to different folder (auto-parallel for multiple emails)"""

def flag_email(email_id, flag_type, set_flag, folder, account_id) -> Dict[str, Any]:
    """Flag/star or unflag an email"""

def get_email_attachments(email_id, folder, account_id) -> Dict[str, Any]:
    """Extract attachments from email"""
```

**Example**:
```python
from services import FolderService

folder_service = FolderService(account_manager)

# List folders
result = folder_service.list_folders()

# Move emails to Archive (automatically uses parallel operations)
result = folder_service.move_emails_to_folder(
    email_ids=['1', '2', '3'],
    target_folder='Archive',
    source_folder='INBOX'
)

# Flag important email
result = folder_service.flag_email(
    email_id='123',
    flag_type='flagged',
    set_flag=True
)
```

---

### SystemService

Handles system-level operations.

**Methods**:

```python
def check_connection() -> Dict[str, Any]:
    """Test email server connections (IMAP and SMTP)"""

def list_accounts() -> Dict[str, Any]:
    """List all configured email accounts"""
```

**Example**:
```python
from services import SystemService

system_service = SystemService(account_manager)

# Check connections
result = system_service.check_connection()

# List accounts
result = system_service.list_accounts()
```

---

## Service Design Principles

### 1. Consistent Return Format

All service methods return a dictionary with at least:
```python
{
    'success': bool,
    'error': str,  # Only present if success=False
    # ... additional data
}
```

### 2. Automatic Optimization

Services automatically select the best implementation:

```python
# EmailService.list_emails() automatically chooses:
if unread_only and not account_id and folder == 'INBOX':
    # Use optimized multi-account fetch
    return optimized_fetch(...)
else:
    # Use standard fetch
    return standard_fetch(...)
```

### 3. Parallel Operations

Services automatically use parallel operations for batch processing:

```python
# EmailService.mark_emails() automatically decides:
if len(email_ids) > 1:
    try:
        # Try parallel operations
        return parallel_ops.execute_batch_operation(...)
    except ImportError:
        # Fall back to sequential
        return sequential_processing(...)
```

### 4. Error Handling

Services provide consistent error handling:
```python
try:
    # Operation
    return {'success': True, 'data': result}
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    return {'error': str(e), 'success': False}
```

---

## Integration with Handlers

Handlers access services through `ToolContext`:

```python
class ToolContext:
    def __init__(self, account_manager, messages_func):
        self.account_manager = account_manager
        self.get_message = messages_func
        
        # Initialize all services
        self.email_service = EmailService(account_manager)
        self.communication_service = CommunicationService(account_manager)
        self.folder_service = FolderService(account_manager)
        self.system_service = SystemService(account_manager)
```

Handler example:
```python
def handle_list_emails(args: Dict[str, Any], ctx: ToolContext):
    """Handler delegates to service"""
    result = ctx.email_service.list_emails(
        limit=args.get('limit', 50),
        unread_only=args.get('unread_only', False),
        folder=args.get('folder', 'INBOX'),
        account_id=args.get('account_id')
    )
    
    if 'error' in result:
        return format_error(result['error'])
    
    return format_success(result)
```

---

## Benefits

### For Maintainability
- ✅ Single place to modify business logic
- ✅ Clear separation of concerns
- ✅ Reduced code duplication
- ✅ Easier to understand and modify

### For Testing
- ✅ Services can be tested independently
- ✅ Handlers can use mock services
- ✅ No need to mock low-level operations
- ✅ Cleaner test code

### For Extension
- ✅ New services can be added easily
- ✅ Service methods can be reused
- ✅ Easy to switch implementations
- ✅ Plugin-friendly architecture

---

## Adding a New Service

1. Create service file in `src/services/`
2. Implement service class with methods
3. Add to `src/services/__init__.py`
4. Initialize in `ToolContext`
5. Use in handlers

Example:
```python
# 1. src/services/calendar_service.py
class CalendarService:
    def __init__(self, account_manager):
        self.account_manager = account_manager
    
    def get_events(self, start_date, end_date):
        # Implementation
        pass

# 2. src/services/__init__.py
from .calendar_service import CalendarService

# 3. src/core/tool_handlers.py
class ToolContext:
    def __init__(self, account_manager, messages_func):
        # ...
        self.calendar_service = CalendarService(account_manager)

# 4. Use in handler
def handle_list_events(args, ctx):
    result = ctx.calendar_service.get_events(...)
    return format_result(result)
```

---

## Migration Guide

If you're updating existing code to use services:

### Before (Direct operations)
```python
from ..legacy_operations import fetch_emails

def handle_list_emails(args, ctx):
    result = fetch_emails(
        args.get('limit', 50),
        args.get('unread_only', False),
        args.get('folder', 'INBOX'),
        args.get('account_id')
    )
    return format(result)
```

### After (Using service)
```python
def handle_list_emails(args, ctx):
    result = ctx.email_service.list_emails(
        limit=args.get('limit', 50),
        unread_only=args.get('unread_only', False),
        folder=args.get('folder', 'INBOX'),
        account_id=args.get('account_id')
    )
    return format(result)
```

**Changes**:
1. Remove direct imports of operations
2. Use `ctx.<service_name>.<method>()`
3. Pass named parameters for clarity
4. Service handles optimization/parallel logic

---

## Best Practices

1. **Always use services in handlers**: Never bypass services to call operations directly
2. **Let services handle complexity**: Don't duplicate optimization logic in handlers
3. **Use named parameters**: Makes code more readable and maintainable
4. **Handle service errors**: Check `success` field in returned dictionary
5. **Log at service level**: Services should log errors with context
6. **Keep services focused**: Each service should handle one domain

---

## FAQ

**Q: Why not just use operations directly?**
A: Services provide abstraction, optimization selection, error handling, and consistency. They make the codebase more maintainable.

**Q: Can I add business logic to handlers?**
A: No, handlers should only validate input and format output. Business logic belongs in services.

**Q: How do I add a new email operation?**
A: Add method to appropriate service (likely EmailService), implement using operations, then use in handler.

**Q: Can services call other services?**
A: Yes, but be careful of circular dependencies. Keep service interactions simple.

**Q: What if I need direct operation access?**
A: Consider if the logic belongs in a service. If it's truly unique, you can still access operations, but this should be rare.

