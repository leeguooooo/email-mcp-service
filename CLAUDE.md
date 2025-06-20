# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with the MCP Email Service codebase.

## Repository Overview

MCP Email Service is a Model Context Protocol email management service that provides unified access to multiple email accounts through a standardized interface. It supports 163, Gmail, QQ, Outlook, and custom email providers with full IMAP/SMTP functionality.

**Key Features:**
- Multi-account email management with account isolation
- Parallel operations for all batch tasks (fetch, search, delete, mark)
- 22+ MCP tools for comprehensive email operations
- Special support for 163.com email authentication
- Thread-safe modular architecture with safety checks

## Quick Start

```bash
# Install dependencies
uv sync

# Configure email accounts
uv run python setup.py

# Test connections
uv run python test_connection.py

# Run the service
./run.sh
```

## Development Commands

### Running the Service
```bash
# Production run (used by MCP clients)
./run.sh

# Direct Python execution
uv run python src/main_refactored.py

# Legacy version
uv run python src/main.py
```

### Testing
```bash
# Run all unit tests
uv run pytest

# Run safe tests only (no external deps)
uv run python tests/run_tests.py

# Test specific module
uv run pytest tests/test_account_manager.py -v

# Test connections
uv run python test_connection.py
```

### Linting & Type Checking
```bash
# Format code
uv run black src/ tests/

# Sort imports
uv run isort src/ tests/

# Type check
uv run mypy src/
```

## Architecture Overview

### Directory Structure
```
mcp-email-service/
├── src/
│   ├── main_refactored.py     # Primary entry point (NEW)
│   ├── main.py                # Legacy entry point
│   ├── account_manager.py     # Multi-account management
│   ├── connection_manager.py  # IMAP/SMTP connections
│   ├── mcp_tools.py          # MCP tool definitions (13 tools)
│   ├── models.py             # Data models
│   ├── legacy_operations.py  # Backward compatibility
│   ├── core/                 # Core infrastructure
│   │   ├── connection_pool.py # Connection pooling
│   │   └── __init__.py
│   └── operations/           # Modular operations
│       ├── parallel_fetch.py # Parallel email fetching
│       ├── batch_fetch.py    # Batch IMAP operations
│       ├── uid_search.py     # UID-based search engine
│       ├── optimized_search.py # Cached parallel search
│       ├── optimized_fetch.py # Optimized email fetching
│       ├── fast_fetch.py     # Fast fetch with caching
│       ├── email_operations.py
│       ├── folder_operations.py
│       ├── search_operations.py
│       └── smtp_operations.py
├── tests/                    # Unit tests
├── accounts.json            # Account configurations
└── run.sh                   # Service launcher
```

### Core Components

1. **AccountManager**: Manages multiple email accounts stored in `accounts.json`
   - CRUD operations for accounts
   - Default account handling
   - Account listing and validation

2. **ConnectionManager**: Handles IMAP/SMTP connections
   - Provider-specific settings (ports, security)
   - Special 163.com IMAP ID support
   - Connection pooling and retry logic

3. **MCPTools**: Defines and handles all MCP tool calls
   - 13 streamlined tools for email operations
   - Unified error handling
   - Multi-account operation support

4. **Parallel Operations**: Thread-safe batch processing across accounts
   - ParallelEmailFetcher: Concurrent email fetching
   - ParallelOperations: Safe batch delete/mark/move with account isolation
   - ParallelSearchOperations: Multi-account concurrent search
   - Account ID validation to prevent cross-account operations

### Key Design Patterns

- **Modular Architecture**: Operations separated by concern (email, folder, search, smtp)
- **Provider Abstraction**: ConnectionManager handles provider-specific quirks
- **Parallel Processing**: Multi-account operations run concurrently
- **Graceful Degradation**: Single account failures don't affect others
- **Legacy Compatibility**: Original operations preserved in legacy_operations.py

## Configuration

### Email Account Setup
Run the interactive setup tool:
```bash
uv run python setup.py
```

### Manual Configuration (accounts.json)
```json
{
  "accounts": [
    {
      "id": "unique-id",
      "email": "user@163.com",
      "password": "authorization_code",
      "provider": "163",
      "is_default": true
    }
  ]
}
```

### Provider-Specific Notes

**163/126 Email:**
- Must use authorization code (not password)
- Enable IMAP in email settings first
- Service implements IMAP ID to prevent "Unsafe Login"

**Gmail:**
- Requires app-specific password
- Enable 2FA and generate app password

**QQ Email:**
- Use authorization code from settings
- Enable IMAP/SMTP services

**Custom Servers:**
- Specify imap_server, smtp_server, and ports

## Available MCP Tools (13)

### Email Reading & Status
- `list_emails` - List emails from all/specific accounts (auto-checks all folders when unread_only=true)
- `get_email_detail` - Get full email content
- `mark_emails` - Mark one or more emails as read/unread
- `flag_email` - Star/unstar emails

### Email Management
- `delete_emails` - Delete emails (move to trash or permanently)
- `move_emails_to_folder` - Move emails between folders

### Email Sending
- `send_email` - Send new emails with attachments
- `reply_email` - Reply with context
- `forward_email` - Forward emails

### Search & Organization
- `search_emails` - Multi-criteria search
- `list_folders` - Show folder structure
- `get_email_attachments` - Extract attachments

### Sending & Communication
- `send_email` - Send new emails with attachments
- `reply_email` - Reply with context

### Account Management
- `check_connection` - Test all connections
- `list_accounts` - Show configured accounts

## Testing Guidelines

### Unit Tests
- Located in `tests/` directory
- Focus on components without external dependencies
- Run with `uv run pytest`

### Test Modules
- `test_account_manager.py` - Account CRUD operations
- `test_mcp_tools.py` - Tool registration and handling
- `test_utils.py` - Utility functions
- `test_connection_manager.py` - Connection handling

### Writing Tests
```python
# Example test structure
def test_feature():
    # Arrange
    manager = AccountManager()
    
    # Act
    result = manager.some_method()
    
    # Assert
    assert result['success'] == True
```

## Common Issues & Solutions

### "Tool not found" Error
- Ensure `run.sh` points to `main_refactored.py`
- Restart MCP client after changes

### 163 Email "Unsafe Login"
- Service handles this automatically with IMAP ID
- Ensure using authorization code, not password

### Slow Email Fetching
- Parallel fetching implemented in v1.0.1
- Check max_workers setting in parallel_fetch.py

### Connection Failures
- Run `test_connection.py` to diagnose
- Check provider-specific settings
- Verify authorization codes/app passwords

## Performance Optimization

### Parallel Processing
- Default: 5 concurrent workers per operation type
- Operations: fetch, search, batch delete/mark/move
- Thread-safe with proper locking mechanisms
- Account isolation enforced (account_id required for destructive ops)
- Automatic fallback to sequential on failure

### Connection Pooling
- Connections reused within operations
- Proper cleanup with context managers
- Timeout settings per provider

## Security Considerations

- Never log passwords or authorization codes
- Account credentials stored locally in accounts.json
- Use authorization codes/app passwords, not main passwords
- SMTP uses TLS/SSL by default

## Contributing Guidelines

### Code Style
- Use `black` for formatting
- Type hints for function signatures
- Comprehensive error handling
- Logging with appropriate levels

### Adding New Features
1. Create operation module in `src/operations/`
2. Add tool definition in `mcp_tools.py`
3. Implement handler in `call_tool()`
4. Add unit tests
5. Update documentation

### Pull Request Checklist
- [ ] Tests pass (`uv run pytest`)
- [ ] Code formatted (`uv run black src/`)
- [ ] Type hints added
- [ ] Documentation updated
- [ ] Error handling implemented
- [ ] Logging added for debugging

## Version History

### v1.1.0 (2025-06-20)
- **Local SQLite Database Implementation**:
  - Full email metadata caching with instant search/list operations
  - FTS5 full-text search for ultra-fast email searches
  - Automatic 5-minute background sync with incremental updates
  - On-demand body fetching to optimize storage
  - Offline browsing support with graceful fallback
  - Complete database design with 6 normalized tables
  - Thread-safe operations with connection pooling
  - Sync status monitoring and statistics API

### v1.0.5 (2025-06-20)
- **Major Performance Optimizations**:
  - Implemented IMAP UID search instead of sequence numbers (more reliable, faster)
  - Added batch email fetching - fetch multiple emails in single IMAP command
  - Connection pool management - reuse connections instead of creating new ones
  - Default 30-day date range for searches (configurable)
  - Enhanced caching with 60-second TTL for search results
  - Parallel folder searching for better coverage
  - Optimized batch operations using connection pooling

### v1.0.4 (2024-06-20)
- Streamlined tools from 22+ to 13 by merging similar operations
- Added English tool descriptions with multi-language response support
- Merged delete operations into single `delete_emails` tool
- Merged mark operations into single `mark_emails` tool
- Removed rarely used tools (create_folder, empty_trash, switch_default_account)
- **Performance improvements**:
  - Added 30-second response caching for list_emails
  - Parallel connection checking for all accounts
  - Fast fetch mode - only checks INBOX for speed
  - Reduced timeout to 10 seconds per account

### v1.0.3 (2024-06-20)
- Enhanced `list_emails` to automatically check all folders when unread_only=true
- Support for 163.com UTF-7 folder names (垃圾邮件, 广告邮件, etc.)
- Fixed folder parsing for various IMAP formats
- Multi-folder parallel fetching for all providers

### v1.0.2 (2024-06-20)
- Enhanced security with mandatory account_id for batch operations
- Extended parallel processing to all batch operations
- Added thread-safe parallel search across accounts
- Improved account isolation to prevent cross-account errors

### v1.0.1 (2024-06-20)
- Added parallel email fetching
- Improved error isolation
- Better multi-account support

### v1.0.0 (2024-06-20)
- Initial release with 22+ MCP tools
- Modular architecture
- Multi-account support
- 163 email compatibility