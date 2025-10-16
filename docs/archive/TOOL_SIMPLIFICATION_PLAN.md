# Tool Simplification Plan

## Current Tools (15 total)

### Email Tools (5)
1. list_emails
2. get_email_detail  
3. mark_emails
4. delete_emails
5. search_emails

### Communication Tools (3)
6. send_email
7. reply_email
8. forward_email

### Organization Tools (4)
9. list_folders
10. move_emails_to_folder
11. flag_email
12. get_email_attachments

### System Tools (2)
13. check_connection
14. list_accounts

### Sync Tool (1)
15. sync_emails

## Proposed Core 10 Tools

### Essential Email Operations (5)
1. **list_emails** - List and browse emails
2. **get_email** - Get email details (rename from get_email_detail)
3. **search_emails** - Search across all accounts
4. **send_email** - Send new emails
5. **reply_email** - Reply to emails

### Email Management (3)
6. **manage_email** - Combined tool for mark/delete/flag/move operations
   - Actions: mark_read, mark_unread, delete, flag, unflag, move
7. **manage_folders** - Combined tool for folder operations
   - Actions: list, create, rename, delete
8. **get_attachments** - Download email attachments

### System Tools (2)
9. **manage_accounts** - Combined account management
   - Actions: list, check_connection, add, remove
10. **sync_emails** - Unified sync management

## Tools to Remove/Merge
- ~~mark_emails~~ → merge into manage_email
- ~~delete_emails~~ → merge into manage_email  
- ~~forward_email~~ → less essential, can be done via send_email
- ~~list_folders~~ → merge into manage_folders
- ~~move_emails_to_folder~~ → merge into manage_email
- ~~flag_email~~ → merge into manage_email
- ~~check_connection~~ → merge into manage_accounts
- ~~list_accounts~~ → merge into manage_accounts

## Benefits
1. **Simpler API** - 10 tools vs 15 (33% reduction)
2. **More Powerful** - Combined tools offer more functionality
3. **Better UX** - Fewer tools to remember
4. **Competitive Edge** - More streamlined than mcp-mail's approach