# MCP Email Service

A unified MCP email service supporting multi-account management with **AI-powered intelligent monitoring and notifications**.

## 🌟 New Feature: n8n + AI Email Monitoring

**Automatically monitor emails, filter important ones with AI, and send real-time notifications to your team chat!**

- 🤖 **AI Smart Filtering**: Uses OpenAI/Claude to intelligently identify important emails
- 📱 **Multi-platform Notifications**: Supports Feishu/DingTalk/WeChat Work/Slack
- ⏰ **Automated Monitoring**: n8n workflow runs every 5 minutes automatically  
- 🔄 **Deduplication**: Prevents duplicate notifications
- 🛡️ **Production Ready**: Comprehensive error handling and fallback mechanisms

### Quick Start with AI Monitoring

```bash
# 1. Set up the monitoring system
python scripts/setup_n8n_monitoring.py

# 2. Configure environment variables
export FEISHU_WEBHOOK="your_webhook_url"
export OPENAI_API_KEY="your_api_key"  # Optional for AI filtering

# 3. Import n8n workflow
# Import n8n/email_monitoring_workflow.json in your n8n instance

# 4. Start monitoring!
# The system will automatically check emails every 5 minutes
```

📚 **Documentation**: See [N8N_EMAIL_MONITORING_GUIDE.md](N8N_EMAIL_MONITORING_GUIDE.md) for complete setup guide.

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

### Basic Email Operations
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

### AI Monitoring System

The AI monitoring system includes several powerful scripts:

#### Core Scripts
- `scripts/call_email_tool.py` - Bridge between n8n and MCP tools
- `scripts/ai_email_filter.py` - AI-powered email importance filtering
- `scripts/notification_service.py` - Multi-platform notification service
- `scripts/email_monitor.py` - Main monitoring controller
- `scripts/setup_n8n_monitoring.py` - Automated setup script

#### Usage Examples

```bash
# Test email fetching
python scripts/call_email_tool.py list_unread_emails '{"limit":5}'

# Test AI filtering
python scripts/ai_email_filter.py '[{"id":"test","subject":"Urgent meeting","from":"boss@company.com","date":"2024-01-15","body_preview":"Important project discussion..."}]'

# Test notifications
python scripts/notification_service.py test

# Run complete monitoring cycle
python scripts/email_monitor.py run

# Check system status
python scripts/email_monitor.py status
```

#### Supported Notification Platforms
- **Feishu/Lark** - Rich card notifications with interactive elements
- **DingTalk** - Markdown formatted messages with @mentions
- **WeChat Work** - Styled messages with color coding
- **Slack** - Block-based rich formatting
- **Custom Webhooks** - Flexible JSON payload support

## Troubleshooting

### Basic Email Issues
1. **Login Failed**: 163/QQ Mail use authorization codes, Gmail uses app passwords
2. **Can't Find Emails**: Default shows unread only, use `unread_only=false`
3. **Connection Timeout**: Check network and firewall settings

### AI Monitoring Issues
4. **AI Filtering Failed**: System automatically falls back to keyword filtering if AI API fails
5. **Webhook Not Working**: Verify webhook URL and test with `python scripts/test_lark_webhook.py`
6. **n8n Workflow Errors**: Check environment variables (`FEISHU_WEBHOOK`, `OPENAI_API_KEY`)
7. **Script Permission Denied**: Run `chmod +x scripts/*.py` to make scripts executable
8. **No Notifications**: Check notification config and test with `python scripts/notification_service.py test`

### Quick Diagnostics
```bash
# Check system status
python scripts/email_monitor.py status

# Test all components
python scripts/setup_n8n_monitoring.py --test-only

# View logs
tail -f email_monitor.log

# Check environment variables
env | grep -E "(FEISHU|OPENAI|PYTHONPATH)"
```

## 📚 Documentation

### Setup Guides
- **[N8N_EMAIL_MONITORING_GUIDE.md](N8N_EMAIL_MONITORING_GUIDE.md)** - Complete setup and usage guide
- **[LARK_SETUP_GUIDE.md](LARK_SETUP_GUIDE.md)** - Quick setup for Feishu/Lark webhook
- **[PRODUCTION_DEPLOYMENT_GUIDE.md](PRODUCTION_DEPLOYMENT_GUIDE.md)** - Production deployment best practices
- **[FINAL_SETUP_SUMMARY.md](FINAL_SETUP_SUMMARY.md)** - Final setup summary and checklist

### Technical Documentation
- **[n8n/README.md](n8n/README.md)** - Detailed n8n workflow configuration
- **[config_templates/](config_templates/)** - Configuration file templates and examples

## 🤝 Contributing

We welcome contributions! Please feel free to submit issues and pull requests.

### Development Setup
```bash
git clone https://github.com/leeguooooo/email-mcp-service.git
cd mcp-email-service
uv sync
python scripts/setup_n8n_monitoring.py
```

## ⭐ Features Roadmap

- [x] Multi-account email management
- [x] AI-powered email filtering
- [x] Multi-platform notifications
- [x] n8n workflow automation
- [x] Production-ready error handling
- [ ] Email auto-reply with AI
- [ ] Smart email categorization
- [ ] Advanced analytics dashboard
- [ ] Mobile app notifications

## License

MIT License