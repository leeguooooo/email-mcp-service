"""
MCP tool schemas definitions
"""

# Email tools schemas
LIST_EMAILS_SCHEMA = {
    "type": "object",
    "properties": {
        "limit": {
            "type": "integer",
            "description": "Maximum number of emails to return (最少50封, default: 100)",
            "default": 100
        },
        "unread_only": {
            "type": "boolean",
            "description": "Only return unread emails (default: false)",
            "default": False
        },
        "folder": {
            "type": "string",
            "description": "Email folder to fetch from (default: 'INBOX')",
            "default": "INBOX"
        },
        "account_id": {
            "type": "string",
            "description": "Specific account to fetch from (optional)"
        }
    }
}

GET_EMAIL_DETAIL_SCHEMA = {
    "type": "object",
    "required": ["email_id"],
    "properties": {
        "email_id": {
            "type": "string",
            "description": "The ID of the email to retrieve"
        },
        "folder": {
            "type": "string",
            "description": "Email folder (default: 'INBOX')",
            "default": "INBOX"
        },
        "account_id": {
            "type": "string",
            "description": "Specific account ID (optional)"
        }
    }
}

MARK_EMAILS_SCHEMA = {
    "type": "object",
    "required": ["email_ids", "mark_as"],
    "properties": {
        "email_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of email IDs to mark"
        },
        "mark_as": {
            "type": "string",
            "enum": ["read", "unread"],
            "description": "Mark emails as 'read' or 'unread'"
        },
        "folder": {
            "type": "string",
            "description": "Email folder (default: 'INBOX')",
            "default": "INBOX"
        },
        "account_id": {
            "type": "string",
            "description": "Specific account ID (required for safety)"
        }
    }
}

DELETE_EMAILS_SCHEMA = {
    "type": "object",
    "required": ["email_ids"],
    "properties": {
        "email_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of email IDs to delete"
        },
        "folder": {
            "type": "string",
            "description": "Source folder (default: 'INBOX')",
            "default": "INBOX"
        },
        "permanent": {
            "type": "boolean",
            "description": "Permanently delete instead of moving to trash",
            "default": False
        },
        "trash_folder": {
            "type": "string",
            "description": "Trash folder name (default: 'Trash')",
            "default": "Trash"
        },
        "account_id": {
            "type": "string",
            "description": "Specific account ID (required for safety)"
        }
    }
}

SEARCH_EMAILS_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Search query text"
        },
        "search_in": {
            "type": "string",
            "enum": ["subject", "from", "body", "to", "all"],
            "description": "Where to search (default: 'all')",
            "default": "all"
        },
        "date_from": {
            "type": "string",
            "description": "Start date (YYYY-MM-DD format)"
        },
        "date_to": {
            "type": "string",
            "description": "End date (YYYY-MM-DD format)"
        },
        "folder": {
            "type": "string",
            "description": "Folder to search in (default: 'all' for all folders)",
            "default": "all"
        },
        "unread_only": {
            "type": "boolean",
            "description": "Only search unread emails",
            "default": False
        },
        "has_attachments": {
            "type": "boolean",
            "description": "Filter by attachment presence"
        },
        "limit": {
            "type": "integer",
            "description": "Maximum results (default: 50)",
            "default": 50
        },
        "account_id": {
            "type": "string",
            "description": "Search specific account only"
        }
    }
}

SEND_EMAIL_SCHEMA = {
    "type": "object",
    "required": ["to", "subject", "body"],
    "properties": {
        "to": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Recipient email addresses"
        },
        "subject": {
            "type": "string",
            "description": "Email subject"
        },
        "body": {
            "type": "string",
            "description": "Email body content"
        },
        "cc": {
            "type": "array",
            "items": {"type": "string"},
            "description": "CC recipients"
        },
        "bcc": {
            "type": "array",
            "items": {"type": "string"},
            "description": "BCC recipients"
        },
        "attachments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["filename", "content"],
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string", "description": "Base64 encoded content"}
                }
            },
            "description": "File attachments"
        },
        "is_html": {
            "type": "boolean",
            "description": "Whether body is HTML",
            "default": False
        },
        "account_id": {
            "type": "string",
            "description": "Send from specific account"
        }
    }
}

REPLY_EMAIL_SCHEMA = {
    "type": "object",
    "required": ["email_id", "body"],
    "properties": {
        "email_id": {
            "type": "string",
            "description": "ID of email to reply to"
        },
        "body": {
            "type": "string",
            "description": "Reply body content"
        },
        "reply_all": {
            "type": "boolean",
            "description": "Reply to all recipients",
            "default": False
        },
        "folder": {
            "type": "string",
            "description": "Folder containing original email",
            "default": "INBOX"
        },
        "attachments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["filename", "content"],
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string", "description": "Base64 encoded content"}
                }
            }
        },
        "is_html": {
            "type": "boolean",
            "description": "Whether body is HTML",
            "default": False
        },
        "account_id": {
            "type": "string",
            "description": "Reply from specific account"
        }
    }
}

FORWARD_EMAIL_SCHEMA = {
    "type": "object", 
    "required": ["email_id", "to"],
    "properties": {
        "email_id": {
            "type": "string",
            "description": "ID of email to forward"
        },
        "to": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Recipients to forward to"
        },
        "body": {
            "type": "string",
            "description": "Additional message (optional)"
        },
        "folder": {
            "type": "string",
            "description": "Folder containing original email",
            "default": "INBOX"
        },
        "include_attachments": {
            "type": "boolean",
            "description": "Include original attachments",
            "default": True
        },
        "account_id": {
            "type": "string",
            "description": "Forward from specific account"
        }
    }
}

LIST_FOLDERS_SCHEMA = {
    "type": "object",
    "properties": {
        "account_id": {
            "type": "string",
            "description": "List folders for specific account"
        }
    }
}

MOVE_EMAILS_TO_FOLDER_SCHEMA = {
    "type": "object",
    "required": ["email_ids", "target_folder"],
    "properties": {
        "email_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Email IDs to move"
        },
        "target_folder": {
            "type": "string",
            "description": "Target folder name"
        },
        "source_folder": {
            "type": "string",
            "description": "Source folder (default: 'INBOX')",
            "default": "INBOX"
        },
        "account_id": {
            "type": "string",
            "description": "Specific account ID (required for safety)"
        }
    }
}

FLAG_EMAIL_SCHEMA = {
    "type": "object",
    "required": ["email_id", "action"],
    "properties": {
        "email_id": {
            "type": "string",
            "description": "Email ID to flag/unflag"
        },
        "action": {
            "type": "string",
            "enum": ["add", "remove"],
            "description": "Add or remove flag"
        },
        "folder": {
            "type": "string",
            "description": "Email folder",
            "default": "INBOX"
        },
        "account_id": {
            "type": "string",
            "description": "Specific account ID"
        }
    }
}

GET_EMAIL_ATTACHMENTS_SCHEMA = {
    "type": "object",
    "required": ["email_id"],
    "properties": {
        "email_id": {
            "type": "string",
            "description": "Email ID to get attachments from"
        },
        "folder": {
            "type": "string",
            "description": "Email folder",
            "default": "INBOX"
        },
        "account_id": {
            "type": "string",
            "description": "Specific account ID"
        }
    }
}

CHECK_CONNECTION_SCHEMA = {
    "type": "object",
    "properties": {}
}

LIST_ACCOUNTS_SCHEMA = {
    "type": "object",
    "properties": {}
}

# Unified sync tool schema
SYNC_EMAILS_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["start", "stop", "force", "status", "config"],
            "description": "Action to perform: start/stop scheduler, force sync, get status, or manage config"
        },
        "full_sync": {
            "type": "boolean",
            "description": "For 'force' action: perform full sync instead of incremental",
            "default": False
        },
        "account_id": {
            "type": "string", 
            "description": "For 'force' action: target specific account only (optional)"
        },
        "config_updates": {
            "type": "object",
            "description": "For 'config' action: configuration updates",
            "properties": {
                "interval_minutes": {
                    "type": "integer",
                    "description": "Sync interval in minutes (1-1440)",
                    "minimum": 1,
                    "maximum": 1440
                },
                "full_sync_hours": {
                    "type": "integer",
                    "description": "Full sync interval in hours (1-168)",
                    "minimum": 1,
                    "maximum": 168
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Enable or disable sync"
                },
                "max_concurrent_accounts": {
                    "type": "integer",
                    "description": "Maximum concurrent accounts (1-10)",
                    "minimum": 1,
                    "maximum": 10
                },
                "cleanup_days": {
                    "type": "integer",
                    "description": "Days to keep emails (1-3650)",
                    "minimum": 1,
                    "maximum": 3650
                }
            }
        }
    }
}