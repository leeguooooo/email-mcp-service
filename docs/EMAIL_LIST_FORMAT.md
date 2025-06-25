# Email List Format Update

## Overview

The email list display format has been updated to be more concise while maintaining all essential information. The default limit has been increased from 50 to 100 emails.

## Changes Made

### 1. Default Limit
- Changed from 50 to 100 emails by default
- Updated in:
  - `src/core/tool_schemas.py`
  - `src/core/tool_handlers.py`
  - `src/core/hybrid_tool_handlers.py`

### 2. New Concise Format

#### Format Structure
```
📧 [Total count] emails ([unread count] unread)

【Account Email】 [account total] emails ([account unread] unread)
[mark][ID] Subject | Sender | Date Time
[mark][ID] Subject | Sender | Date Time
...

【Another Account】 [count] emails ([unread] unread)
[mark][ID] Subject | Sender | Date Time
...
```

#### Format Details
- **Mark**: 🔴 for unread, "  " (two spaces) for read
- **ID**: Email ID truncated to first 10 characters
- **Subject**: Maximum 40 characters (37 + "...")
- **Sender**: Name only (no email), max 20 characters
- **Date/Time**: Format "YYYY-MM-DD HH:MM"

### 3. Features

1. **Grouped by Account**: Emails are organized by account for better readability
2. **Account Summary**: Each account shows total and unread count
3. **Compact Lines**: Each email on a single line with pipe separators
4. **Limited Display**: Maximum 50 emails per account to prevent overflow
5. **Performance Info**: Shows fetch time at the end if available

### 4. Example Output

```
📧 134 emails (23 unread)

【leeguoo@163.com】 89 emails (15 unread)
🔴[1234567890] Important meeting reminder | John Smith | 2025-06-20 14:30
  [1234567891] Weekly report submitted | Jane Doe | 2025-06-20 12:15
🔴[1234567892] Project deadline update | Mike Johnson | 2025-06-20 10:45
...

【leeguoo@qq.com】 45 emails (8 unread)
🔴[9876543210] 您的账单已出 | 腾讯服务 | 2025-06-20 09:00
  [9876543211] 系统维护通知 | QQ邮箱团队 | 2025-06-19 18:30
...

⏱️ 2.3s
```

## Benefits

1. **More Information**: Default 100 emails vs previous 50
2. **Better Organization**: Grouped by account
3. **Space Efficient**: One line per email
4. **Quick Scanning**: Visual markers for unread emails
5. **Essential Info Only**: ID, subject, sender, time - no redundant data

## Usage

The format is automatically applied when using:
- `list_emails` tool
- Hybrid mode email listing
- Search results display

No changes needed in tool usage - the formatting is handled internally.