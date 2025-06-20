# MCP Email Service

支持多邮箱账户统一管理的 MCP 邮件服务。

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

### 3. 初始化数据库和同步配置

首次使用需要创建配置文件：

```bash
# 复制配置示例文件
cp sync_config.json.example sync_config.json

# 数据库会在首次同步时自动创建
# 首次同步会获取最近6个月的邮件历史
```

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

## 许可证

MIT License