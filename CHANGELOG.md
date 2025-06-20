# Changelog

## [1.1.0] - 2025-06-20

### 🚀 Major Features
- **Local SQLite Database Caching**:
  - Implemented full email metadata caching for instant search and listing
  - Added FTS5 full-text search support for blazing fast email searches
  - Automatic background synchronization every 5 minutes
  - On-demand email body fetching to save storage space
  - Support for offline email browsing and search
  - Database statistics and sync status monitoring

### 🏗️ Database Architecture
- Multi-table schema design:
  - `accounts`: Email account management
  - `folders`: Folder structure caching  
  - `emails`: Email metadata with search indexes
  - `email_contents`: Optional full email body storage
  - `attachments`: Attachment metadata tracking
  - `sync_log`: Synchronization history and monitoring
- Thread-safe connection pooling
- Incremental sync using IMAP UIDs
- Automatic cleanup of old data

### 📚 Documentation
- Added comprehensive database design document
- Created integration examples and usage guide
- Updated README with SQLite caching plans

## [1.0.5] - 2025-06-20

### 🏗️ Architecture Improvements
- **Major refactoring**: Split monolithic mcp_tools.py (660 lines) into modular architecture
- Created clean separation of concerns:
  - `tool_registry.py`: Tool registration and dispatch mechanism
  - `tool_schemas.py`: All tool JSON schema definitions
  - `tool_handlers.py`: Core email operation handlers
  - `communication_handlers.py`: Send/reply/forward handlers
  - `organization_handlers.py`: Folder/flag/attachment handlers
  - `system_handlers.py`: Account/connection management
- Reduced main tool file from 32KB to 8KB (75% reduction)
- Implemented strategy pattern for tool handling
- Cleaned up old monolithic files and consolidated entry points
- All functionality maintained with cleaner architecture

## [1.0.4] - 2025-06-20

### ⚡ Performance Optimizations
- Increased cache TTL from 30 seconds to 5 minutes for better response times
- Increased parallel workers from 5 to 10 for faster multi-account fetching
- Optimized folder scanning: 3 folders for unread emails (was 5)
- Increased per-folder email limit: 20-30 emails (was 3-10)
- Better unread email coverage for accounts with many folders

### 🐛 Bug Fixes
- Fixed QQ email showing only 4 unread emails when there are 29
- Resolved slow list_emails performance issues
- Improved multi-folder email fetching logic

## [1.0.3] - 2025-06-20

### 🎯 New Features
- Added `list_all_unread` tool to fetch unread emails from ALL folders (not just INBOX)
- Support for 163.com's UTF-7 encoded folder names (垃圾邮件, 广告邮件, etc.)
- Multi-folder parallel fetching across all accounts

### 🐛 Bug Fixes
- Fixed folder name parsing for various IMAP server formats
- Fixed account data retrieval to include ID field
- Improved folder detection for non-standard folder structures

### ⚡ Performance
- Parallel folder scanning across accounts
- Configurable per-folder email limits
- Automatic folder name translation for better readability

## [1.0.2] - 2025-06-20

### 🔒 Security & Safety
- Enhanced account isolation for all batch operations
- Added mandatory account_id requirement for delete operations
- Implemented thread-safe parallel operations with proper locking

### ⚡ Performance
- Extended parallel processing to search operations across multiple accounts
- Batch operations (delete, mark, move) now execute with account safety checks
- Parallel search can query all accounts simultaneously

### 🏗️ Architecture
- Added `parallel_operations.py` for safe batch processing
- Added `parallel_search.py` for multi-account search
- Refactored batch operations to use new parallel infrastructure

### 🧪 Testing
- Added comprehensive tests for parallel operation safety
- Added thread safety and account isolation tests
- Performance comparison tests for parallel vs sequential

## [1.0.1] - 2025-06-20

### 🐛 Bug Fixes
- Fixed "Unknown error" in list_emails by improving error handling
- Implemented parallel email fetching for better performance (5x faster with multiple accounts)
- Single account failures no longer affect other accounts
- Added detailed error reporting for failed accounts

### ⚡ Performance
- Email fetching from multiple accounts now runs in parallel
- Configurable max workers (default: 5 concurrent connections)
- Automatic fallback to sequential fetching if parallel fails

## [1.0.0] - 2025-06-20

### 🎉 Major Release

#### ✨ Features
- **Email Sending**: New `send_email`, `reply_email`, and `forward_email` tools
- **Advanced Search**: `search_emails` with multiple criteria (subject, from, date range, etc.)
- **Folder Management**: `list_folders`, `create_folder`, `move_email_to_folder`
- **Enhanced Email Operations**: `mark_email_unread`, `flag_email`, `get_email_attachments`
- **Batch Operations**: Support for batch mark unread and archive
- **Account Management**: `list_accounts`, `switch_default_account` tools

#### 🏗️ Architecture
- Refactored to modular architecture with separate operation modules
- Added comprehensive connection management
- Improved error handling and retry logic
- Better multi-account support

#### 🧪 Testing
- Added 29 unit tests covering core functionality
- Test coverage for account management, utilities, and MCP tools
- Automated test runner

#### 📚 Documentation
- Simplified README for better user experience
- Added command quick reference (COMMANDS.md)
- Improved configuration examples
- Added setup.py interactive configuration tool

#### 🐛 Bug Fixes
- Fixed 163 email IMAP ID authentication issue
- Improved error messages for authentication failures
- Better handling of multi-account edge cases

### 🔄 Migration Notes
- Service now uses `main_refactored.py` instead of `main.py`
- Total of 22+ MCP tools available (up from 10)
- Default behavior: `list_emails` now shows unread emails from all accounts

### 🙏 Acknowledgments
Thanks to all users who reported issues and suggested features!