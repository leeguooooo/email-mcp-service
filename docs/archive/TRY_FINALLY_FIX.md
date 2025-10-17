# Try/Finally 结构修复计划

## 🐛 问题

**位置**: `src/legacy_operations.py:fetch_emails`

**当前结构**:
```python
conn_mgr = get_connection_manager(account_id)
mail = conn_mgr.connect_imap()

try:
    # IMAP 操作
    ...
finally:
    mail.logout()

return {  # ❌ return 在 finally 之外！
    "emails": emails,
    ...
}
```

**问题**:
1. `return` 语句在 `finally` 块之外
2. 如果在 try 块中发生异常：
   - `finally` 会执行 `mail.logout()`
   - 但 `return` 永远不会执行（异常会被外层 catch）
   - 变量 `emails`, `total_in_folder`, `unread_count` 可能未定义
3. 如果在循环中发生异常，可能在 logout 后继续使用 socket

## ✅ 正确结构

```python
conn_mgr = get_connection_manager(account_id)
mail = conn_mgr.connect_imap()

try:
    # 所有 IMAP 操作
    result, data = mail.select(folder)
    ...
    
    # ✅ return 在 try 块内，finally 之前
    return {
        "emails": emails,
        "total_in_folder": total_in_folder,
        "unread_count": unread_count,
        ...
    }
finally:
    # 清理（在 return 之后执行）
    try:
        mail.logout()
    except Exception as e:
        logger.warning(f"Error closing IMAP connection: {e}")
```

## 🎯 关键点

1. **所有 IMAP 操作在 try 块内**: select, search, fetch 等
2. **return 在 try 块内**: 确保变量已定义且在 logout 前返回
3. **finally 保证清理**: 无论成功或异常，都会 logout
4. **外层 try/except**: 捕获所有异常并返回错误

## 📝 需要应用的修复

由于文件恢复到了早期版本，需要重新应用所有优化：

1. **缓存层集成** (已丢失)
2. **UID 使用** (已丢失)
3. **键名一致性** (已丢失)
4. **Try/Finally 结构** (需要修复)
5. **Account ID 规范化** (已丢失)
6. **变量名冲突修复** (已丢失)

请重新从用户确认的版本开始，而不是 HEAD。


