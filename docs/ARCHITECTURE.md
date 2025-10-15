# Architecture Documentation

## Project Structure Overview

MCP Email Service follows a clean, layered architecture with clear separation of concerns. This document explains the architectural improvements implemented based on code review feedback.

## Layer Structure

```
┌─────────────────────────────────────┐
│         MCP Tools Layer             │  ← User Interface
│    (mcp_tools.py, tool_registry)    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│       Tool Handlers Layer           │  ← Request Routing
│  (tool_handlers, communication_*,   │
│   organization_*, system_*)          │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│        Service Layer                │  ← Business Logic
│  (EmailService, Communication,      │
│   FolderService, SystemService)     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Operations & Legacy Layer        │  ← Data Access
│  (operations/*, legacy_operations)  │
└─────────────────────────────────────┘
```

## Key Components

### 1. Configuration Layer (`src/config/`)

**Purpose**: Centralized configuration management for cross-cutting concerns.

**Components**:
- `messages.py`: Multi-language message support with localization
  - `MESSAGES`: Language-specific message dictionary
  - `get_message()`: Retrieve localized messages
  - `get_user_language()`: Detect user's preferred language

**Benefits**:
- Easy to add new languages without modifying core logic
- Centralized message management
- Can be extended to support loading from JSON/YAML files

### 2. Service Layer (`src/services/`)

**Purpose**: Clean interface for business operations, encapsulating complex logic and reducing coupling.

**Components**:

#### EmailService (`email_service.py`)
- `list_emails()`: Retrieve emails with optimized fetching
- `get_email_detail()`: Get detailed email content
- `mark_emails()`: Mark emails as read/unread (supports parallel operations)
- `delete_emails()`: Delete or move emails to trash
- `search_emails()`: Search emails across accounts

#### CommunicationService (`communication_service.py`)
- `send_email()`: Send new emails
- `reply_email()`: Reply to emails with thread preservation
- `forward_email()`: Forward emails with attachments

#### FolderService (`folder_service.py`)
- `list_folders()`: List email folders
- `move_emails_to_folder()`: Move emails between folders
- `flag_email()`: Flag/star emails
- `get_email_attachments()`: Extract attachments

#### SystemService (`system_service.py`)
- `check_connection()`: Test server connections
- `list_accounts()`: List configured accounts

**Benefits**:
- Single responsibility for each service
- Encapsulates parallel/optimized operation selection
- Easy to unit test in isolation
- Reduces direct dependencies on legacy/operations modules

### 3. Tool Handlers Layer (`src/core/`)

**Purpose**: Translate MCP tool calls to service layer operations and format responses.

**Components**:
- `tool_handlers.py`: Core email operation handlers
- `communication_handlers.py`: Send/reply/forward handlers
- `organization_handlers.py`: Folder/flag/attachment handlers
- `system_handlers.py`: System operation handlers
- `tool_schemas.py`: JSON schemas for all tools
- `tool_registry.py`: Registry pattern for tool management

**Key Pattern - ToolContext**:
```python
class ToolContext:
    def __init__(self, account_manager, messages_func):
        self.account_manager = account_manager
        self.get_message = messages_func
        # Initialize all services
        self.email_service = EmailService(account_manager)
        self.communication_service = CommunicationService(account_manager)
        self.folder_service = FolderService(account_manager)
        self.system_service = SystemService(account_manager)
```

**Benefits**:
- Handlers focus on input validation and output formatting
- All business logic delegated to service layer
- Clean separation between protocol (MCP) and business logic

### 4. Schema Management (`src/core/tool_schemas.py`)

**Explicit Imports Pattern**:

Instead of wildcard imports:
```python
# Bad (before)
from .core.tool_schemas import *

# Good (after)
from .core.tool_schemas import (
    LIST_EMAILS_SCHEMA,
    GET_EMAIL_DETAIL_SCHEMA,
    MARK_EMAILS_SCHEMA,
    # ... explicit list
)
```

**Benefits**:
- Better IDE support and code navigation
- Easier to track schema usage
- Prevents accidental namespace pollution
- Improves static analysis

### 5. Tool Registry Pattern (`src/core/tool_registry.py`)

**Decorator-based Registration**:
```python
tool_registry.register(
    "list_emails",
    "List emails from inbox (supports multi-account)",
    LIST_EMAILS_SCHEMA
)(EmailToolHandlers.handle_list_emails)
```

**Benefits**:
- Declarative tool registration
- Centralized tool management
- Easy to add/remove tools
- Automatic schema validation support

## Design Principles Applied

### 1. Separation of Concerns
- **Configuration**: Isolated in `config/`
- **Business Logic**: Encapsulated in `services/`
- **Protocol Handling**: Contained in `handlers/`
- **Data Access**: Separated in `operations/` and `legacy_operations`

### 2. Dependency Inversion
- Handlers depend on service abstractions, not concrete implementations
- Services encapsulate implementation details
- Easy to swap implementations (e.g., optimized vs. standard operations)

### 3. Single Responsibility
- Each service handles one domain (email, communication, folders, system)
- Each handler focuses on one tool type
- Configuration is separate from business logic

### 4. Open/Closed Principle
- Easy to add new services without modifying existing code
- New languages can be added without changing service logic
- New tools can be registered without modifying core registry

## Benefits of This Architecture

### Maintainability
- Clear structure makes it easy to locate and modify code
- Each layer has well-defined responsibilities
- Changes in one layer don't cascade to others

### Testability
- Services can be tested independently
- Handlers can be tested with mock services
- Operations layer can be tested in isolation

### Scalability
- Easy to add new services and handlers
- Configuration can be extended without code changes
- New tools can be added declaratively

### Code Quality
- Reduced coupling between components
- Better code organization and readability
- Explicit imports improve static analysis
- Consistent error handling patterns

## Migration Path

For future enhancements:

1. **Configuration Files**: Move `MESSAGES` to JSON/YAML files
2. **Service Interfaces**: Define abstract interfaces for services
3. **Dependency Injection**: Use DI container for service management
4. **Async Services**: Migrate more operations to async/await pattern
5. **Caching Layer**: Add caching between services and operations

## Code Review Improvements Addressed

1. ✅ **Explicit Schema Imports**: Changed from wildcard to explicit imports
2. ✅ **Message Configuration Separation**: Moved to dedicated `config/messages.py`
3. ✅ **Service Layer Introduction**: Created clean service interfaces
4. ✅ **Reduced Coupling**: Handlers now use services instead of direct operations
5. ✅ **Better Organization**: Clear layer separation with focused responsibilities

## Example Usage Flow

```
User Request
    ↓
MCP Server
    ↓
MCPTools.call_tool()
    ↓
ToolRegistry.get_handler()
    ↓
EmailToolHandlers.handle_list_emails()
    ↓
ToolContext.email_service.list_emails()
    ↓
[Service selects optimized vs. standard operation]
    ↓
operations/optimized_fetch or legacy_operations
    ↓
Return results through the stack with formatting at handler level
```

## Future Considerations

1. **API Documentation**: Generate OpenAPI/Swagger docs from schemas
2. **Monitoring**: Add telemetry at service layer boundaries
3. **Rate Limiting**: Implement at service layer
4. **Retry Logic**: Centralize in service layer
5. **Circuit Breaker**: Add resilience patterns to services

