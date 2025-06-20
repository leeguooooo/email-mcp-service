"""
Tool registry and dispatcher for MCP tools
"""
import logging
import asyncio
from typing import Dict, Any, Callable, Optional, Awaitable, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ToolDefinition:
    """Tool definition with metadata"""
    name: str
    description: str
    handler: Callable
    schema: Dict[str, Any]
    
class ToolRegistry:
    """Registry for all MCP tools"""
    
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
    
    def register(self, name: str, description: str, schema: Dict[str, Any]):
        """Decorator to register a tool handler"""
        def decorator(handler: Callable) -> Callable:
            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                handler=handler,
                schema=schema
            )
            self._handlers[name] = handler
            logger.info(f"Registered tool: {name}")
            return handler
        return decorator
    
    def get_handler(self, name: str) -> Optional[Callable]:
        """Get handler for a tool"""
        return self._handlers.get(name)
    
    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """Get full tool definition"""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools with their schemas"""
        return [
            {
                "name": name,
                "description": tool.description,
                "inputSchema": tool.schema
            }
            for name, tool in self._tools.items()
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any], context: Any) -> Any:
        """Call a registered tool"""
        handler = self.get_handler(name)
        if not handler:
            raise ValueError(f"Unknown tool: {name}")
        
        # If handler is async, await it
        if asyncio.iscoroutinefunction(handler):
            return await handler(arguments, context)
        else:
            return handler(arguments, context)

# Global registry instance
tool_registry = ToolRegistry()