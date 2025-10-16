# MCP Email Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20by-uv-purple)](https://github.com/astral-sh/uv)

A unified MCP email service supporting multi-account management with **AI-powered intelligent monitoring and notifications**.

> **🌟 New Feature**: Email translation & summarization with n8n automation - automatically translate non-Chinese emails, generate summaries, and send to Feishu/Lark!

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

📚 **Documentation**: See [N8N_EMAIL_MONITORING_GUIDE.md](docs/guides/N8N_EMAIL_MONITORING_GUIDE.md) for complete setup guide.

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
cd email-mcp-service
uv sync
```

### 2. Configure Email Accounts

```bash
# Interactive setup
uv run python setup.py

# Or manually copy example config
cp examples/accounts.example.json accounts.json
# Then edit accounts.json with your email settings
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

### Quick Start Guides
- **[docs/guides/EMAIL_TRANSLATE_WORKFLOW_GUIDE.md](docs/guides/EMAIL_TRANSLATE_WORKFLOW_GUIDE.md)** - Email translation & summarization workflow
- **[docs/guides/HTTP_API_QUICK_START.md](docs/guides/HTTP_API_QUICK_START.md)** - HTTP API quick start
- **[docs/guides/N8N_EMAIL_MONITORING_GUIDE.md](docs/guides/N8N_EMAIL_MONITORING_GUIDE.md)** - n8n email monitoring guide
- **[docs/guides/LARK_SETUP_GUIDE.md](docs/guides/LARK_SETUP_GUIDE.md)** - Feishu/Lark webhook setup

### Deployment & Security
- **[docs/guides/FINAL_DEPLOYMENT_CHECKLIST.md](docs/guides/FINAL_DEPLOYMENT_CHECKLIST.md)** - Deployment checklist
- **[docs/guides/PRODUCTION_DEPLOYMENT_GUIDE.md](docs/guides/PRODUCTION_DEPLOYMENT_GUIDE.md)** - Production deployment guide
- **[docs/guides/SECURITY_SETUP_GUIDE.md](docs/guides/SECURITY_SETUP_GUIDE.md)** - Security configuration

### Technical Documentation
- **[docs/README.md](docs/README.md)** - Complete documentation index
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture
- **[n8n/README.md](n8n/README.md)** - n8n workflow details
- **[config_templates/](config_templates/)** - Configuration templates

## 🤝 Contributing

We welcome contributions! Please feel free to submit issues and pull requests.

### Development Setup
```bash
# Clone the repository
git clone https://github.com/leeguooooo/email-mcp-service.git
cd email-mcp-service

# Install dependencies (including dev tools)
uv sync --extra dev

# Run tests
uv run pytest

# Set up development environment
cp config_templates/env.n8n.example .env
# Edit .env with your configuration
```

### Running Tests
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_mcp_tools.py

# Run with coverage
uv run pytest --cov=src --cov-report=html
```

### Code Quality

**Option 1: Install dev dependencies** (recommended)
```bash
# Install with dev extras (includes black, ruff, mypy)
uv sync --extra dev

# Then run tools
uv run black src/ scripts/ tests/
uv run ruff check src/ scripts/ tests/
uv run mypy src/
```

**Option 2: Use uv tool** (no installation needed)
```bash
# Format code
uvx black src/ scripts/ tests/

# Lint code
uvx ruff check src/ scripts/ tests/

# Type check
uvx mypy src/
```

## ⭐ Features Roadmap

- [x] Multi-account email management
- [x] AI-powered email filtering
- [x] Email translation & summarization (OpenAI)
- [x] Multi-platform notifications
- [x] n8n workflow automation
- [x] Production-ready error handling
- [ ] Email auto-reply with AI
- [ ] Smart email categorization
- [ ] Advanced analytics dashboard
- [ ] Mobile app notifications

## 🔒 Security

### API Key Protection
All sensitive endpoints are protected with API key authentication. See [SECURITY_SETUP_GUIDE.md](docs/guides/SECURITY_SETUP_GUIDE.md) for details.

### Environment Variables
Never commit sensitive information. Always use environment variables:
- `.env` files are automatically ignored by git
- Use `.env.example` templates for documentation
- Rotate API keys regularly

### Reporting Security Issues
Please report security vulnerabilities to the repository maintainers privately before public disclosure.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.