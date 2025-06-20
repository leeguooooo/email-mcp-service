# MCP Email Service

支持多邮箱账户统一管理的 MCP 邮件服务。可同时管理163邮箱、Gmail、QQ邮箱等，解决多邮箱管理难题。

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

### 待优化项目
- [ ] **代码拆分优化**
  - 将大文件（main.py, mcp_tools.py）拆分为更小的模块
  - 分离邮件操作、账户管理、工具函数等功能
  - 优化代码复用，减少重复代码

- [ ] **邮件获取性能**
  - 实现邮件缓存机制，减少重复获取
  - 添加增量同步功能，只获取新邮件
  - 优化批量操作的性能

- [ ] **连接管理优化**
  - 实现连接池管理，复用IMAP连接
  - 添加连接超时和重试机制
  - 优化多账户并发连接

- [ ] **内存优化**
  - 大邮件和附件的流式处理
  - 及时释放不需要的对象
  - 优化邮件列表的内存占用

- [ ] **错误处理改进**
  - 统一错误处理机制
  - 更详细的错误日志
  - 优雅的降级处理

## 📝 许可证

MIT License