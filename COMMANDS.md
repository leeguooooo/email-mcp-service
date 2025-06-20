# 命令速查表

## 常用命令

```bash
# 查看未读邮件（默认）
list_emails

# 查看所有邮件
list_emails with unread_only=false

# 搜索邮件
search_emails with query="会议"

# 查看邮件详情
get_email_detail with email_id="123"

# 标记已读
mark_email_read with email_id="123"

# 批量标记已读
batch_mark_read with email_ids=["1", "2", "3"]

# 发送邮件
send_email with to=["a@b.com"] subject="标题" body="内容"
```

## 完整命令列表

### 查看类 (4个)
- `check_connection` - 检查连接状态
- `list_emails` - 列出邮件
- `get_email_detail` - 邮件详情
- `get_unread_count` - 未读数量

### 操作类 (7个)
- `mark_email_read` - 标记已读
- `mark_email_unread` - 标记未读
- `flag_email` - 添加星标
- `delete_email` - 删除邮件
- `move_email_to_trash` - 移到垃圾箱
- `move_email_to_folder` - 移到文件夹
- `get_email_attachments` - 获取附件

### 批量操作 (4个)
- `batch_mark_read` - 批量已读
- `batch_mark_unread` - 批量未读
- `batch_delete_emails` - 批量删除
- `batch_move_to_trash` - 批量垃圾箱

### 发送邮件 (3个)
- `send_email` - 发送新邮件
- `reply_email` - 回复邮件
- `forward_email` - 转发邮件

### 搜索 (1个)
- `search_emails` - 搜索邮件

### 文件夹 (4个)
- `list_folders` - 列出文件夹
- `create_folder` - 创建文件夹
- `delete_folder` - 删除文件夹
- `empty_trash` - 清空垃圾箱

### 账户管理 (2个)
- `list_accounts` - 列出账户
- `switch_default_account` - 切换默认账户

## 参数说明

### 通用参数
- `account_id` - 指定账户（可选，默认所有账户）
- `folder` - 文件夹（默认 INBOX）
- `limit` - 数量限制（默认 50）

### 搜索参数
- `query` - 搜索关键词
- `search_in` - 搜索范围：subject/from/body/to/all
- `date_from` - 开始日期 (YYYY-MM-DD)
- `date_to` - 结束日期
- `unread_only` - 仅未读
- `has_attachments` - 有附件

### 发送参数
- `to` - 收件人列表
- `subject` - 主题
- `body` - 内容
- `cc` - 抄送
- `bcc` - 密送
- `attachments` - 附件路径列表
- `is_html` - HTML格式