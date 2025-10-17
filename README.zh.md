# MCP Email Service

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/managed%20by-uv-purple)](https://github.com/astral-sh/uv)
[![Tests](https://img.shields.io/badge/tests-71%2F72%20passing-brightgreen)](./tests)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/leeguooooo?logo=github)](https://github.com/sponsors/leeguooooo)

支持多邮箱账户统一管理的 MCP 邮件服务，具备 **AI 智能监控和通知功能**。

> **新功能**：邮件翻译与总结 - 自动翻译非中文邮件，生成摘要，并发送到飞书！

## 支持的邮箱

- **163邮箱** (mail.163.com / mail.126.com)
- **QQ邮箱** (mail.qq.com)  
- **Gmail** (mail.google.com)
- **Outlook/Hotmail**
- **自定义IMAP邮箱**

## 快速开始

### 1. 安装

需要 Python 3.11+ 和 [UV](https://github.com/astral-sh/uv)。

```bash
git clone https://github.com/leeguooooo/email-mcp-service.git
cd mcp-email-service
uv sync
```

### 2. 配置邮箱

```bash
uv run python setup.py
```

### 3. 初始化数据库和同步

```bash
# 交互式模式（推荐新手）
uv run python init_sync.py

# 直接初始化数据库
uv run python init_sync.py init

# 启动后台守护进程（持续同步）
uv run python init_sync.py daemon
```

**功能说明：**
- 自动创建配置文件
- 检查邮箱账户配置  
- 初始化数据库并同步最近6个月的邮件
- 支持后台守护进程模式持续同步

#### 邮箱配置说明

| 邮箱 | 配置步骤 |
|-----|---------|
| **163邮箱** | 登录 mail.163.com → 设置 → 开启IMAP → 获取授权码（使用授权码，不是密码） |
| **QQ邮箱** | 设置 → 账户 → 开启IMAP → 生成授权码 |
| **Gmail** | 开启两步验证 → [生成应用密码](https://myaccount.google.com/apppasswords) |
| **Outlook** | 直接使用邮箱密码 |

### 4. 集成到 MCP 客户端

在 MCP 客户端（如 Claude Desktop）配置文件中添加：

```json
{
    "mcpServers": {
        "mcp-email-service": {
            "command": "/你的路径/mcp-email-service/run.sh",
            "args": []
        }
    }
}
```

## 主要功能

### 查看邮件
```bash
list_emails                              # 查看未读邮件
list_emails with unread_only=false       # 查看所有邮件
list_emails with limit=100               # 查看更多邮件
```

### 搜索邮件
```bash
search_emails with query="会议"                    # 搜索包含"会议"的邮件
search_emails with query="张三" search_in="from"   # 搜索发件人
search_emails with date_from="2024-01-01"         # 按日期搜索
```

### 邮件操作
```bash
get_email_detail with email_id="123"              # 查看邮件详情
mark_emails with email_ids=["123"] mark_as="read" # 标记已读
delete_emails with email_ids=["123"]              # 删除邮件
flag_email with email_id="123" set_flag=true      # 添加星标
```

### 发送邮件
```bash
send_email with to=["user@example.com"] subject="标题" body="内容"
reply_email with email_id="123" body="回复内容"
```

### 联系人分析 ⭐ 新功能
```bash
analyze_contacts                                     # 分析联系人频率（最近30天）
analyze_contacts with days=90 limit=20               # 自定义分析周期
analyze_contacts with group_by="sender"              # 只分析发件人
get_contact_timeline with contact_email="user@example.com"  # 获取沟通时间线
```

## 所有可用命令

### 邮件操作
- `list_emails` - 列出邮件
- `get_email_detail` - 查看邮件详情
- `search_emails` - 搜索邮件
- `mark_emails` - 标记已读/未读
- `delete_emails` - 删除邮件
- `flag_email` - 星标邮件

### 发送邮件
- `send_email` - 发送邮件
- `reply_email` - 回复邮件
- `forward_email` - 转发邮件

### 邮件管理
- `move_emails_to_folder` - 移动邮件
- `list_folders` - 查看文件夹
- `get_email_attachments` - 获取附件

### 联系人分析 ⭐ 新功能
- `analyze_contacts` - 分析联系人频率
- `get_contact_timeline` - 获取沟通时间线

### 系统管理
- `check_connection` - 测试连接
- `list_accounts` - 查看已配置账户
- `sync_emails` - 手动同步邮件数据库

### 数据库同步功能

```bash
# 查看同步状态
sync_emails with action="status"

# 手动触发同步
sync_emails with action="force"

# 启动后台自动同步
sync_emails with action="start"

# 停止后台同步
sync_emails with action="stop"
```

**同步机制说明：**
- 首次同步：自动获取最近6个月的邮件历史
- 增量同步：每15分钟同步最近7天的新邮件
- 完全同步：每天凌晨2点进行完整同步
- 离线浏览：同步后的邮件可离线查看和搜索

## 常见问题

1. **登录失败**：163/QQ邮箱使用授权码，Gmail使用应用密码
2. **找不到邮件**：默认只显示未读，使用 `unread_only=false`
3. **连接超时**：检查网络和防火墙设置

## 项目结构

```
mcp-email-service/
├── data/                       # 运行时数据目录（自动创建）
│   ├── email_sync.db          # 邮件同步数据库
│   ├── sync_config.json       # 同步配置
│   ├── logs/                  # 日志文件
│   ├── tmp/                   # 临时文件
│   └── attachments/           # 下载的附件
├── src/                       # 源代码
│   ├── config/               # 配置管理
│   │   └── paths.py          # 集中路径配置
│   ├── operations/           # 邮件操作
│   ├── background/           # 后台同步调度器
│   └── ...
├── tests/                     # 测试套件（71/72 通过）
├── docs/                      # 文档
│   ├── guides/               # 用户指南
│   └── archive/              # 历史文档
├── scripts/                   # 实用脚本
├── n8n/                      # n8n 工作流模板
├── config_templates/         # 配置示例
└── accounts.json             # 邮箱账户配置（用户创建）
```

### 核心特性

- **后台同步自动启动**：MCP 服务启动时自动开始同步
- **数据集中管理**：所有运行时数据在 `data/` 目录
- **基于 UID 的操作**：跨操作的稳定邮件标识
- **智能缓存**：比实时 IMAP 查询快 100-500 倍
- **多账户支持**：正确隔离管理多个邮箱账户
- **性能优化**：批量操作共享连接（快 5 倍）
- **充分测试**：71/72 测试通过，约 65% 代码覆盖率

## 文档

### 快速入门指南
- **[docs/guides/EMAIL_TRANSLATE_WORKFLOW_GUIDE.md](docs/guides/EMAIL_TRANSLATE_WORKFLOW_GUIDE.md)** - 邮件翻译与摘要工作流
- **[docs/guides/HTTP_API_QUICK_START.md](docs/guides/HTTP_API_QUICK_START.md)** - HTTP API 快速开始
- **[docs/guides/N8N_EMAIL_MONITORING_GUIDE.md](docs/guides/N8N_EMAIL_MONITORING_GUIDE.md)** - n8n 邮件监控指南
- **[docs/guides/LARK_SETUP_GUIDE.md](docs/guides/LARK_SETUP_GUIDE.md)** - 飞书 Webhook 设置

### 技术文档
- **[docs/README.md](docs/README.md)** - 完整文档索引
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 系统架构设计
- **[docs/database_design.md](docs/database_design.md)** - 数据库设计
- **[n8n/README.md](n8n/README.md)** - n8n 工作流详情
- **[config_templates/](config_templates/)** - 配置模板示例
- **[data/README.md](data/README.md)** - 数据目录指南

## 支持本项目

如果你觉得本项目有帮助，请考虑：

- **给项目加星**以示支持
- **报告 Bug** 或建议功能通过 [Issues](https://github.com/leeguooooo/email-mcp-service/issues)
- **贡献代码**或文档通过 [Pull Requests](https://github.com/leeguooooo/email-mcp-service/pulls)
- **赞助开发**通过 [GitHub Sponsors](https://github.com/sponsors/leeguooooo)

### 微信/支付宝赞赏

如果你想支持本项目，可以使用微信支付或支付宝：

<div align="center">
  <img src=".github/wechatpay.JPG" alt="微信支付二维码" width="300"/>
  <img src=".github/alipay.JPG" alt="支付宝二维码" width="300"/>
  <p><i>扫码支持本项目（微信或支付宝）</i></p>
</div>

你的支持帮助维护和改进本项目！谢谢！

## 贡献

欢迎贡献！请随时提交 Issue 和 Pull Request。

### 运行测试
```bash
# 运行所有测试
python3 -m unittest discover tests/

# 查看测试覆盖率
python3 -m coverage run -m unittest discover tests/
python3 -m coverage report
```

## 许可证

MIT License