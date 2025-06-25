# MCP Email Service

A unified MCP email service supporting multi-account management.

## Supported Email Providers

- **163 Mail** (mail.163.com / mail.126.com)
- **QQ Mail** (mail.qq.com)  
- **Gmail** (mail.google.com)
- **Outlook/Hotmail**
- **Custom IMAP servers**

## Quick Start

### Option 1: Install via Smithery (Recommended)

```bash
npx -y @smithery/cli install mcp-email-service --client claude
```

After installation, you'll need to configure your email accounts:
```bash
cd ~/.config/smithery/servers/mcp-email-service
python setup.py
```

### Option 2: Manual Installation

Requires Python 3.11+ and [UV](https://github.com/astral-sh/uv).

```bash
git clone https://github.com/leeguooooo/email-mcp-service.git
cd mcp-email-service
uv sync
```

### 2. Configure Email Accounts

```bash
uv run python setup.py
```

#### Email Configuration Guide

| Provider | Configuration Steps |
|----------|-------------------|
| **163 Mail** | Login to mail.163.com → Settings → Enable IMAP → Get authorization code (use code, not password) |
| **QQ Mail** | Settings → Account → Enable IMAP → Generate authorization code |
| **Gmail** | Enable 2FA → [Generate app password](https://myaccount.google.com/apppasswords) |
| **Outlook** | Use email password directly |

### 3. Add to MCP Client (Manual Installation Only)

If you installed manually, add to your MCP client (e.g., Claude Desktop) config:

```json
{
    "mcpServers": {
        "mcp-email-service": {
            "command": "/your/path/mcp-email-service/run.sh",
            "args": []
        }
    }
}
```

## Main Features

### View Emails
```bash
list_emails                              # View unread emails
list_emails with unread_only=false       # View all emails
list_emails with limit=100               # View more emails
```

### Search Emails
```bash
search_emails with query="meeting"                 # Search emails containing "meeting"
search_emails with query="john" search_in="from"   # Search by sender
search_emails with date_from="2024-01-01"         # Search by date
```

### Email Operations
```bash
get_email_detail with email_id="123"              # View email details
mark_emails with email_ids=["123"] mark_as="read" # Mark as read
delete_emails with email_ids=["123"]              # Delete email
flag_email with email_id="123" set_flag=true      # Add star
```

### Send Emails
```bash
send_email with to=["user@example.com"] subject="Subject" body="Content"
reply_email with email_id="123" body="Reply content"
```

## Available Commands

- `list_emails` - List emails
- `get_email_detail` - View email details
- `search_emails` - Search emails
- `mark_emails` - Mark as read/unread
- `delete_emails` - Delete emails
- `flag_email` - Star/unstar emails
- `send_email` - Send new email
- `reply_email` - Reply to email
- `forward_email` - Forward email
- `move_emails_to_folder` - Move emails
- `list_folders` - View folders
- `get_email_attachments` - Get attachments
- `check_connection` - Test connections

## Troubleshooting

1. **Login Failed**: 163/QQ Mail use authorization codes, Gmail uses app passwords
2. **Can't Find Emails**: Default shows unread only, use `unread_only=false`
3. **Connection Timeout**: Check network and firewall settings

## License

MIT License