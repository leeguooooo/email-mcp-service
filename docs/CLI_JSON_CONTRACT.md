# CLI JSON Contract (Python CLI Baseline)

This document captures the current JSON output shapes of the Python CLI.
The Node rewrite should preserve these fields for compatibility with skills.

Captured date: 2026-02-01

## Global Contract
- `--json` outputs a single JSON object to stdout.
- `success: boolean` is always present.
- `error: string` appears when `success=false`.
- Exit codes: `0` success, `1` operation failed, `2` invalid usage.

## account

### account list
```json
{
  "success": true,
  "accounts": [
    {
      "id": "acc_id",
      "email": "user@example.com",
      "provider": "gmail",
      "description": "optional",
      "imap_host": "imap.example.com",
      "smtp_host": "smtp.example.com"
    }
  ],
  "count": 1
}
```

### account test-connection
```json
{
  "success": true,
  "accounts": [
    {
      "email": "user@example.com",
      "provider": "gmail",
      "success": true,
      "imap": { "success": true, "total_emails": 123, "unread_emails": 4 },
      "smtp": { "success": true }
    }
  ],
  "total_accounts": 1
}
```
Legacy fallback: when no configured accounts exist, the output may be a single
test result without `accounts`/`total_accounts`, but still includes `success`,
`imap`, and `smtp`.

## email

### email list
CLI adds fields: `limit`, `offset`, `unread_only`, `folder`, `use_cache`,
and `account_id` when provided.

Common shape (superset):
```json
{
  "success": true,
  "emails": [
    {
      "id": "123",
      "uid": "123",
      "message_id": "<...>",
      "subject": "Hello",
      "from": "sender@example.com",
      "date": "2025-01-01 12:34:56",
      "unread": true,
      "has_attachments": false,
      "account": "user@example.com",
      "account_id": "acc_id",
      "folder": "INBOX",
      "source": "cache_sync_db"
    }
  ],
  "total_in_folder": 200,
  "unread_count": 10,
  "total_emails": 200,
  "total_unread": 10,
  "accounts_count": 1,
  "accounts_info": [
    { "account": "user@example.com", "total": 200, "unread": 10, "fetched": 50 }
  ],
  "offset": 0,
  "limit": 50,
  "from_cache": true
}
```
Notes:
- Fields vary by source (cache vs live, single vs multi-account).
- Each email may include `source` (e.g. `cache_sync_db` or `imap_fetch`).

### email search
Two main variants (optimized vs fallback). Keep a union of fields:
```json
{
  "success": true,
  "emails": [
    {
      "id": "123",
      "uid": "123",
      "subject": "Hello",
      "from": "sender@example.com",
      "to": "recipient@example.com",
      "date": "2025-01-01 12:34:56",
      "unread": true,
      "flagged": false,
      "is_flagged": false,
      "has_attachments": false,
      "message_id": "<...>",
      "account": "user@example.com",
      "account_id": "acc_id",
      "folder": "INBOX",
      "preview": "optional body preview"
    }
  ],
  "total_found": 200,
  "displayed": 50,
  "accounts_count": 1,
  "offset": 0,
  "limit": 50,
  "total_emails": 50,
  "accounts_searched": 1,
  "accounts_info": [],
  "search_time": 0.42,
  "search_params": {},
  "failed_accounts": [],
  "failed_searches": [],
  "partial_success": true
}
```

### email show
```json
{
  "success": true,
  "id": "123",
  "requested_id": "123",
  "from": "sender@example.com",
  "to": "recipient@example.com",
  "cc": "cc@example.com",
  "subject": "Hello",
  "date": "2025-01-01 12:34:56",
  "body": "plain text body",
  "html_body": "<p>HTML</p>",
  "has_html": true,
  "attachments": [
    { "filename": "a.pdf", "size": 1234, "content_type": "application/pdf" }
  ],
  "attachment_count": 1,
  "unread": true,
  "message_id": "<...>",
  "folder": "INBOX",
  "account": "user@example.com",
  "account_id": "acc_id",
  "from_cache": true
}
```

### email mark
Dry-run:
```json
{
  "success": true,
  "dry_run": true,
  "would_mark": 2,
  "mark_as": "read",
  "email_ids": ["1", "2"],
  "message": "Dry run: would mark 2 emails as read"
}
```
Batch or single:
```json
{
  "success": true,
  "marked_count": 2,
  "total": 2,
  "total_requested": 2,
  "mark_as": "read",
  "results": [
    { "success": true, "email_id": "1", "folder": "INBOX", "account_id": "acc_id" }
  ]
}
```

### email delete
Dry-run:
```json
{
  "success": true,
  "dry_run": true,
  "would_delete": 2,
  "permanent": false,
  "email_ids": ["1", "2"],
  "message": "Dry run: would move to trash 2 emails"
}
```
Batch or single:
```json
{
  "success": true,
  "deleted_count": 2,
  "total": 2,
  "total_requested": 2,
  "results": [
    { "success": true, "email_id": "1", "folder": "INBOX", "account_id": "acc_id" }
  ]
}
```

### email send / reply / forward
```json
{
  "success": true,
  "message": "Email sent successfully to 2 recipient(s)",
  "recipients": ["a@example.com", "b@example.com"],
  "from": "user@example.com"
}
```
On error: `{"success": false, "error": "...", "from": "user@example.com"}`.

### email folders
```json
{
  "success": true,
  "folders": [
    {
      "name": "INBOX",
      "attributes": "\\HasNoChildren",
      "delimiter": "/",
      "message_count": 123,
      "path": "INBOX"
    }
  ],
  "folder_tree": {},
  "total_folders": 1,
  "account": "user@example.com"
}
```

### email attachments
```json
{
  "success": true,
  "attachments": [
    {
      "filename": "a.pdf",
      "size": 1234,
      "size_formatted": "1.2 KB",
      "content_type": "application/pdf",
      "saved_path": "/path/to/a.pdf"
    }
  ],
  "attachment_count": 1,
  "email_id": "123",
  "folder": "INBOX",
  "account": "user@example.com"
}
```

### email flag
```json
{
  "success": true,
  "message": "Flag \"flagged\" set",
  "email_id": "123",
  "flag_type": "flagged",
  "set_flag": true,
  "folder": "INBOX",
  "account": "user@example.com"
}
```

### email move
```json
{
  "success": true,
  "message": "Moved 2/2 emails to \"Archive\"",
  "moved_count": 2,
  "source_folder": "INBOX",
  "target_folder": "Archive",
  "account": "user@example.com",
  "failed_ids": []
}
```

## sync

### sync status / watch
```json
{
  "success": true,
  "scheduler_running": true,
  "config": {},
  "last_sync_times": { "incremental": "2025-01-01T00:00:00", "full": null },
  "next_jobs": [
    { "job": "<function>", "next_run": "2025-01-01T01:00:00", "interval": "5" }
  ],
  "accounts": [
    { "id": "acc_id", "email": "user@example.com", "provider": "gmail", "last_sync": null, "total_emails": 0, "sync_status": "pending" }
  ],
  "total_emails": 0,
  "database_size": 0
}
```

### sync force / sync init
All accounts:
```json
{
  "success": true,
  "accounts_synced": 1,
  "total_accounts": 1,
  "emails_added": 100,
  "emails_updated": 5,
  "sync_time": 3.2,
  "results": [
    { "success": true, "account_id": "acc_id", "folders_synced": 5, "emails_added": 100, "emails_updated": 5 }
  ]
}
```
Single account (`--account-id`):
```json
{
  "success": true,
  "account_id": "acc_id",
  "folders_synced": 5,
  "emails_added": 100,
  "emails_updated": 5
}
```

### sync health
```json
{
  "success": true,
  "status": "healthy",
  "total_accounts": 1,
  "healthy_accounts": 1,
  "warning_accounts": 0,
  "critical_accounts": 0,
  "average_health_score": 100.0,
  "total_syncs": 10,
  "total_failures": 0,
  "success_rate": 100.0,
  "timestamp": "2025-01-01T00:00:00"
}
```

## digest

### digest run / daemon
```json
{
  "success": true,
  "date": "2025-01-01",
  "total_emails": 40,
  "displayed": 40,
  "total_found": 40,
  "important_emails": 5,
  "categories": { "work": 10, "finance": 3 },
  "truncated": false,
  "summary": "summary text",
  "missing_details": 0,
  "dry_run": false,
  "debug_log": "/path/to/debug.jsonl",
  "lark_payload": {},
  "telegram_message": "text",
  "telegram_parse_mode": "HTML",
  "telegram_session_id": "token",
  "notification": {},
  "notifications": { "lark": {}, "telegram": {} }
}
```

### digest config
```json
{ "success": true, "config": { "...": "..." } }
```

## monitor

### monitor run
```json
{
  "success": true,
  "message": "Monitoring cycle completed",
  "stats": {
    "fetched_emails": 10,
    "important_emails": 10,
    "notifications_sent": 10,
    "filter_success": true,
    "notification_success": true
  },
  "important_emails": [],
  "details": {
    "fetch_result": { "...": "..." },
    "filter_result": { "...": "..." },
    "notification_result": { "...": "..." }
  }
}
```

### monitor status
```json
{
  "success": true,
  "status": {
    "config_path": "/path/to/email_monitor_config.json",
    "notification_enabled": true,
    "notification_config_path": "/path/to/notification_config.json",
    "env": { "MAILBOX_CONFIG_DIR": "" }
  }
}
```

### monitor config / test
```json
{ "success": true, "config": { "...": "..." } }
```
```json
{ "success": true, "fetch": { "...": "..." }, "notify": { "...": "..." } }
```

## inbox

### inbox (organizer)
```json
{
  "success": true,
  "processed": 15,
  "actions": {
    "delete_spam": [],
    "delete_marketing": [],
    "mark_as_read": [],
    "needs_attention": []
  },
  "important_summaries": [],
  "summary_text": "summary text",
  "stats": {
    "total_emails": 15,
    "delete_spam": 0,
    "delete_marketing": 0,
    "mark_as_read": 0,
    "needs_attention": 0
  },
  "generated_at": "2025-01-01T00:00:00Z"
}
```
