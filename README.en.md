# MCP Email Service

A unified MCP email service supporting multi-account management. Manage 163 Mail, Gmail, QQ Mail and more from a single interface.

## ✨ Key Features

- 🌐 **Multi-Account Management** - View emails from all accounts in one place
- 📧 **Email Operations** - Read, mark, delete, move, and send emails
- 🔍 **Smart Search** - Search by subject, sender, date and more
- 📎 **Attachment Management** - View and download email attachments
- 🚀 **Batch Operations** - Bulk mark as read, delete, and more
- 📁 **Folder Management** - View and manage email folders

## 🚀 Quick Start

### 1. Installation

Requires Python 3.11+ and [UV](https://github.com/astral-sh/uv) package manager.

```bash
# Clone the repository
git clone <repo-url>
cd mcp-email-service

# Install dependencies
uv sync
```

### 2. Configure Email Accounts

Run the setup tool to add email accounts:

```bash
uv run python setup.py
```

Options:
1. Add email account
2. View all accounts  
3. Delete account
4. Set default account
5. **Test connections** (recommended)
6. Save and exit

#### Email Provider Setup

| Provider | Configuration Steps | Notes |
|----------|-------------------|-------|
| **163/126 Mail** | Login to mail.163.com → Settings → Enable IMAP → Get authorization code | ⚠️ Use authorization code, not password |
| **Gmail** | Enable 2-factor auth → [Generate app password](https://myaccount.google.com/apppasswords) | Requires app-specific password |
| **QQ Mail** | Settings → Account → Enable IMAP → Generate authorization code | Use authorization code |
| **Outlook** | Use email password directly | Usually no special setup needed |

### 3. Test Connections

Test your configuration:

```bash
# Using setup tool
uv run python setup.py
# Select "5. Test connections"

# Or use standalone script
uv run python test_connection.py
```

### 4. Integrate with MCP Client

Add to your MCP client configuration:

```json
{
    "mcpServers": {
        "mcp-email-service": {
            "command": "/path/to/mcp-email-service/run.sh",
            "args": []
        }
    }
}
```

Restart your MCP client to use the service.

## 📋 Available Commands

### Basic Functions
| Command | Description | Example |
|---------|-------------|---------|
| `check_connection` | Check all email connections | `check_connection` |
| `list_emails` | List emails (unread by default) | `list_emails` |
| `get_email_detail` | View email details | `get_email_detail with email_id="123"` |
| `search_emails` | Search emails | `search_emails with query="meeting"` |

### Email Operations
| Command | Description | Example |
|---------|-------------|---------|
| `mark_emails` | Mark emails as read/unread | `mark_emails with email_ids=["123"] mark_as="read"` |
| `flag_email` | Add/remove star | `flag_email with email_id="123"` |
| `delete_emails` | Delete emails | `delete_emails with email_ids=["123"] permanent=false` |

### Advanced Features
| Command | Description | Example |
|---------|-------------|---------|
| `send_email` | Send new email | `send_email with to=["a@b.com"] subject="Hi" body="Hello"` |
| `reply_email` | Reply to email | `reply_email with email_id="123" body="Thanks"` |
| `list_folders` | List folders | `list_folders` |
| `get_email_attachments` | Get attachments | `get_email_attachments with email_id="123"` |
| `move_emails_to_folder` | Move emails | `move_emails_to_folder with email_ids=["123"] target_folder="Important"` |

## 💡 Usage Tips

### 1. Viewing Emails
```bash
# View unread emails from all accounts (default)
list_emails

# View all emails
list_emails with unread_only=false

# View from specific account
list_emails with account_id="env_163"

# Increase limit
list_emails with limit=100
```

### 2. Searching Emails
```bash
# Search by subject
search_emails with query="meeting" search_in="subject"

# Search by sender
search_emails with query="boss@company.com" search_in="from"

# Search by date range
search_emails with date_from="2024-01-01" date_to="2024-01-31"

# Search unread only
search_emails with query="important" unread_only=true
```

### 3. Managing Emails
```bash
# Mark multiple as read
mark_emails with email_ids=["1", "2", "3"] mark_as="read"

# Move to trash (default)
delete_emails with email_ids=["1", "2"]

# Permanently delete
delete_emails with email_ids=["1", "2"] permanent=true

# Move to folder
move_emails_to_folder with email_ids=["1", "2"] target_folder="Archive"
```

### 4. Sending Emails
```bash
# Send simple email
send_email with to=["user@example.com"] subject="Test" body="This is a test"

# Send HTML email
send_email with to=["user@example.com"] subject="Test" body="<h1>Title</h1><p>Content</p>" is_html=true

# With attachments
send_email with to=["user@example.com"] subject="Files" body="Please see attached" attachments=["/path/to/file.pdf"]
```

## 🌍 Language Support

The service supports multiple languages for responses:

```bash
# Chinese (default)
./run.sh

# English
MCP_LANGUAGE=en ./run.sh
```

## 🔧 Troubleshooting

### Login Failed
- **163 Mail**: Ensure using authorization code, not password. Check IMAP is enabled
- **Gmail**: Need app-specific password, not Google account password
- **QQ Mail**: Need authorization code from settings

### Connection Timeout
- Check network connection
- Ensure firewall allows IMAP connections (port 993)
- Some corporate networks may block email ports

### Can't Find Emails
- Default shows only unread emails, use `unread_only=false` to see all
- Check if emails are in other folders (like trash)

### Multiple Accounts
Run `uv run python setup.py` to add multiple accounts. All commands operate on all accounts by default.

## 🚀 Performance Optimization Plan

### To-Do Items
- [ ] **Code Splitting Optimization**
  - Split large files (main.py, mcp_tools.py) into smaller modules
  - Separate email operations, account management, and utility functions
  - Optimize code reuse and reduce duplicate code

- [ ] **Email Fetching Performance**
  - Implement email caching mechanism to reduce redundant fetches
  - Add incremental sync to fetch only new emails
  - Optimize batch operation performance

- [ ] **Connection Management Optimization**
  - Implement connection pool to reuse IMAP connections
  - Add connection timeout and retry mechanisms
  - Optimize multi-account concurrent connections

- [ ] **Memory Optimization**
  - Stream processing for large emails and attachments
  - Timely release of unused objects
  - Optimize memory usage for email lists

- [ ] **Error Handling Improvements**
  - Unified error handling mechanism
  - More detailed error logging
  - Graceful degradation handling

## 📝 License

MIT License