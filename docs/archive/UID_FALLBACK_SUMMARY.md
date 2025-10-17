# UID优先+回退逻辑修复方案

## 问题总结

用户在 `fetch_emails()` 和 `get_email_detail()` 中实现了 UID 支持，但其他写操作函数（`mark_email_read`, `delete_email`, `move_email_to_trash` 及其批量版本）只尝试 UID，不回退到序列号，导致向后兼容性问题。

## 需要修复的函数

1. `mark_email_read` - 行 616
2. `delete_email` - 行 686
3. `move_email_to_trash` - 行 763
4. `batch_move_to_trash` - 行 849
5. `batch_delete_emails` - 行 950
6. `batch_mark_read` - 行 1009

## 修复模式

对于单个邮件操作：
```python
# Try UID first
result, data = mail.uid('store', fetch_id, '+FLAGS', '\\Seen')

# If UID fails, fallback to sequence number
if result != 'OK' or not data or data == [None]:
    logger.debug(f"UID operation failed for {fetch_id}, trying sequence number")
    result, data = mail.store(fetch_id, '+FLAGS', '\\Seen')
    
    if result != 'OK':
        raise Exception(f"Failed to mark email as read: {result}")
```

对于批量操作：
```python
for email_id in email_ids:
    try:
        # Try UID first
        result, data = mail.uid('store', email_id, '+FLAGS', '\\Seen')
        
        # Fallback to sequence number if UID fails
        if result != 'OK' or not data or data == [None]:
            result, data = mail.store(email_id, '+FLAGS', '\\Seen')
        
        if result == 'OK':
            success_count += 1
        else:
            failed_ids.append(email_id)
    except Exception as e:
        logger.warning(f"Failed to process email {email_id}: {e}")
        failed_ids.append(email_id)
```

## 关键点

1. **优先使用 UID**：UID 更稳定（删除/添加邮件时不变）
2. **自动回退**：UID 失败时自动尝试序列号
3. **向后兼容**：支持旧代码传递序列号
4. **详细日志**：记录回退行为以便调试
5. **保持函数签名**：不破坏现有 API

## 实施步骤

鉴于文件已恢复，需要：
1. 重新应用原有的 IMAP 连接泄漏修复（try/finally 块）
2. 添加 HTML 转文本和正文截断功能
3. 为所有写操作函数添加 UID 回退逻辑


