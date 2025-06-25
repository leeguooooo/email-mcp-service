# Unified Sync Tool Documentation

## Overview

All email synchronization functionality has been consolidated into a single `sync_emails` tool that provides comprehensive sync management through different actions.

## Tool: sync_emails

**Description**: Unified email synchronization tool for managing email sync operations

### Actions

#### 1. Start Scheduler (`action: "start"`)
Starts the background email sync scheduler.

```json
{
  "action": "start"
}
```

**Response**: Scheduler status with sync intervals and next sync time

#### 2. Stop Scheduler (`action: "stop"`)
Stops the background email sync scheduler.

```json
{
  "action": "stop"
}
```

**Response**: Confirmation of scheduler stop

#### 3. Force Sync (`action: "force"`)
Forces an immediate synchronization.

```json
{
  "action": "force",
  "full_sync": false,      // Optional: true for full sync, false for incremental (default)
  "account_id": "env_163"  // Optional: specific account only
}
```

**Parameters**:
- `full_sync` (boolean, optional): Perform full sync instead of incremental
- `account_id` (string, optional): Target specific account only

**Response**: Sync results with emails added/updated and sync time

#### 4. Get Status (`action: "status"`)
Gets current sync status and statistics.

```json
{
  "action": "status"
}
```

**Response**: 
- Scheduler running status
- Account information (email counts, last sync time)
- Total statistics
- Next scheduled sync

#### 5. Search Cached Emails (`action: "search"`)
Searches through locally cached emails.

```json
{
  "action": "search",
  "query": "important meeting",
  "account_id": "env_gmail",  // Optional
  "limit": 20                 // Optional, default: 20
}
```

**Parameters**:
- `query` (string, required): Search keywords
- `account_id` (string, optional): Search specific account only
- `limit` (integer, optional): Maximum results to return

**Response**: List of matching emails from local cache

#### 6. Get Recent Emails (`action: "recent"`)
Gets recently cached emails.

```json
{
  "action": "recent",
  "account_id": "env_qq",  // Optional
  "limit": 20              // Optional, default: 20
}
```

**Parameters**:
- `account_id` (string, optional): Get from specific account only
- `limit` (integer, optional): Maximum results to return

**Response**: List of recent emails from local cache

#### 7. Manage Config (`action: "config"`)
View or update sync configuration.

**Get current config:**
```json
{
  "action": "config"
}
```

**Update config:**
```json
{
  "action": "config",
  "config_updates": {
    "interval_minutes": 15,          // Sync interval (1-1440)
    "full_sync_hours": 24,          // Full sync interval (1-168)
    "enabled": true,                // Enable/disable sync
    "max_concurrent_accounts": 3,   // Max concurrent accounts (1-10)
    "cleanup_days": 30              // Days to keep emails (1-3650)
  }
}
```

**Response**: Current configuration or update confirmation

## Examples

### Example 1: Start sync and check status
```json
// Start sync
{
  "action": "start"
}

// Check status
{
  "action": "status"
}
```

### Example 2: Force sync a specific account
```json
{
  "action": "force",
  "account_id": "env_163",
  "full_sync": false
}
```

### Example 3: Search for important emails
```json
{
  "action": "search",
  "query": "invoice",
  "limit": 50
}
```

### Example 4: Update sync interval
```json
{
  "action": "config",
  "config_updates": {
    "interval_minutes": 30,
    "full_sync_hours": 48
  }
}
```

## Architecture

The unified sync tool uses:
- **SyncHandlers**: Main handler class in `src/core/sync_handlers.py`
- **EmailSyncManager**: Core sync logic in `src/operations/email_sync.py`
- **SyncScheduler**: Background scheduler in `src/background/sync_scheduler.py`
- **SyncConfig**: Configuration management in `src/background/sync_config.py`

## Benefits of Unified Tool

1. **Single Entry Point**: All sync operations through one tool
2. **Consistent Interface**: Same tool structure for all sync operations
3. **Simplified Usage**: No need to remember multiple tool names
4. **Better Organization**: Related functionality grouped together
5. **Easier Maintenance**: Single codebase for all sync operations

## Migration from Old Tools

If you were using the old separate tools:
- `start_sync` → `sync_emails` with `action: "start"`
- `stop_sync` → `sync_emails` with `action: "stop"`
- `force_sync` → `sync_emails` with `action: "force"`
- `get_sync_status` → `sync_emails` with `action: "status"`
- `search_cached_emails` → `sync_emails` with `action: "search"`
- `get_recent_cached_emails` → `sync_emails` with `action: "recent"`
- `update_sync_config` → `sync_emails` with `action: "config"`