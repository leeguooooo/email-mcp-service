# MCP Email Service

支持多邮箱账户统一管理的 MCP 邮件服务。可同时管理163邮箱、Gmail、QQ邮箱等，解决多邮箱管理难题。

## 🌟 支持的邮箱服务

### 完全支持的邮箱
- **163邮箱** (mail.163.com / mail.126.com) - 中国最流行的邮箱服务之一
  - ✅ 支持授权码登录
  - ✅ 自动处理中文文件夹名称
  - ✅ 防止"不安全登录"提示
  
- **QQ邮箱** (mail.qq.com) - 腾讯邮箱服务
  - ✅ 支持授权码登录
  - ✅ 支持所有文件夹访问
  - ✅ 自动识别垃圾邮件文件夹
  
- **Gmail** (mail.google.com) - Google邮箱服务
  - ✅ 支持应用专用密码
  - ✅ 支持标签系统
  - ✅ 完整的搜索功能

### 其他支持的邮箱
- **Outlook/Hotmail** - Microsoft邮箱服务
- **自定义IMAP邮箱** - 支持任何标准IMAP协议的邮箱

## ✨ 核心功能

- 🌐 **多账户管理** - 统一查看所有邮箱的邮件
- 📧 **邮件操作** - 查看、标记、删除、移动、发送
- 🔍 **邮件搜索** - 按主题、发件人、日期等搜索
- 📎 **附件管理** - 查看和下载邮件附件
- 🚀 **批量操作** - 批量标记已读、删除等
- 📁 **文件夹管理** - 查看和管理邮箱文件夹

## 🚀 快速开始

### 1. 安装

需要 Python 3.11+ 和 [UV](https://github.com/astral-sh/uv) 包管理器。

```bash
# 克隆项目
git clone <repo-url>
cd mcp-email-service

# 安装依赖
uv sync
```

### 2. 配置邮箱

运行配置工具添加邮箱账户：

```bash
uv run python setup.py
```

选择操作：
1. 添加邮箱账户
2. 查看所有账户  
3. 删除账户
4. 设置默认账户
5. **测试连接**（推荐）
6. 保存并退出

#### 邮箱配置说明

| 邮箱类型 | 配置步骤 | 注意事项 |
|---------|---------|---------|
| **163邮箱** | 登录 mail.163.com → 设置 → 开启IMAP → 获取授权码 | ⚠️ 使用授权码，不是密码 |
| **Gmail** | 开启两步验证 → [生成应用密码](https://myaccount.google.com/apppasswords) | 需要应用专用密码 |
| **QQ邮箱** | 设置 → 账户 → 开启IMAP → 生成授权码 | 使用授权码 |
| **Outlook** | 直接使用邮箱密码 | 一般无需特殊设置 |

### 3. 测试连接

配置完成后测试连接：

```bash
# 使用配置工具
uv run python setup.py
# 选择 "5. 测试连接"

# 或使用独立脚本
uv run python test_connection.py
```

### 4. 集成到 MCP 客户端

在 MCP 客户端配置文件中添加：

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

重启 MCP 客户端即可使用。

## 📋 可用命令

### 基础功能
| 命令 | 说明 | 示例 |
|-----|------|-----|
| `check_connection` | 检查所有邮箱连接 | `check_connection` |
| `list_emails` | 列出邮件（默认未读） | `list_emails` |
| `get_email_detail` | 查看邮件详情 | `get_email_detail with email_id="123"` |
| `search_emails` | 搜索邮件 | `search_emails with query="会议"` |

### 邮件操作
| 命令 | 说明 | 示例 |
|-----|------|-----|
| `mark_email_read` | 标记已读 | `mark_email_read with email_id="123"` |
| `mark_email_unread` | 标记未读 | `mark_email_unread with email_id="123"` |
| `flag_email` | 添加星标 | `flag_email with email_id="123"` |
| `delete_email` | 删除邮件 | `delete_email with email_id="123"` |

### 批量操作
| 命令 | 说明 | 示例 |
|-----|------|-----|
| `batch_mark_read` | 批量标记已读 | `batch_mark_read with email_ids=["1", "2", "3"]` |
| `batch_delete_emails` | 批量删除 | `batch_delete_emails with email_ids=["1", "2"]` |
| `batch_move_to_trash` | 批量移到垃圾箱 | `batch_move_to_trash with email_ids=["1", "2"]` |

### 高级功能
| 命令 | 说明 | 示例 |
|-----|------|-----|
| `send_email` | 发送邮件 | `send_email with to=["a@b.com"] subject="Hi" body="Hello"` |
| `reply_email` | 回复邮件 | `reply_email with email_id="123" body="Thanks"` |
| `list_folders` | 列出文件夹 | `list_folders` |
| `get_email_attachments` | 获取附件 | `get_email_attachments with email_id="123"` |

## 💡 使用技巧

### 1. 查看邮件
```bash
# 查看所有账户的未读邮件（默认）
list_emails

# 查看所有邮件
list_emails with unread_only=false

# 查看特定账户
list_emails with account_id="env_163"

# 增加获取数量
list_emails with limit=100
```

### 2. 搜索邮件
```bash
# 按主题搜索
search_emails with query="会议" search_in="subject"

# 按发件人搜索
search_emails with query="boss@company.com" search_in="from"

# 按日期范围搜索
search_emails with date_from="2024-01-01" date_to="2024-01-31"

# 只搜索未读
search_emails with query="重要" unread_only=true
```

### 3. 发送邮件
```bash
# 发送简单邮件
send_email with to=["user@example.com"] subject="测试" body="这是测试邮件"

# 发送HTML邮件
send_email with to=["user@example.com"] subject="测试" body="<h1>标题</h1><p>内容</p>" is_html=true

# 带附件
send_email with to=["user@example.com"] subject="文件" body="请查收附件" attachments=["/path/to/file.pdf"]
```

## 🔧 常见问题

### 登录失败
- **163邮箱**：确认使用授权码而非密码，检查是否开启IMAP
- **Gmail**：需要应用专用密码，不是Google账号密码
- **QQ邮箱**：需要授权码，在设置中生成

### 连接超时
- 检查网络连接
- 确认防火墙允许IMAP连接（端口993）
- 某些公司网络可能限制邮件端口

### 找不到邮件
- 默认只显示未读邮件，使用 `unread_only=false` 查看全部
- 检查邮件是否在其他文件夹（如垃圾箱）

### 如何添加多个邮箱？
运行 `uv run python setup.py` 可以添加多个账户，所有命令默认操作所有账户。

## 🚀 性能优化计划

### 近期优化（v1.1.0）
- [ ] **本地SQLite数据库同步**
  - 实现邮件元数据本地缓存，大幅提升查询速度
  - 支持离线搜索和查看邮件列表
  - 增量同步机制，只同步新邮件
  - 本地操作：搜索、列表、查看详情
  - 远程操作：标记、删除、发送等写操作

### 已完成优化（v1.0.x）
- [x] **模块化架构重构** - 从单体文件拆分为模块化设计
- [x] **并行处理优化** - 多账户并发获取，性能提升5-10倍
- [x] **连接池管理** - 复用IMAP连接，减少握手开销
- [x] **批量操作优化** - 使用UID批量操作，提高效率
- [x] **智能缓存机制** - 60秒缓存，减少重复请求

### 未来规划
- [ ] **交互式邮箱应用**
  - 基于本地数据库的Web/桌面客户端
  - 实时邮件推送通知
  - 高级搜索和过滤功能
  
- [ ] **机器学习集成**
  - 智能邮件分类
  - 垃圾邮件检测
  - 重要邮件识别

## 🙏 致谢

特别感谢以下项目和贡献者：

- [pyisemail](https://github.com/michaelhelmick/pyisemail) - 提供了邮件验证的参考实现
- [imaplib](https://docs.python.org/3/library/imaplib.html) - Python标准库的IMAP支持
- [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) - Anthropic的开放协议
- 所有提出Issue和PR的贡献者们

如果这个项目对你有帮助，欢迎给个⭐️！

## 📝 许可证

MIT License