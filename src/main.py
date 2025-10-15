#!/usr/bin/env python3
"""
MCP Email Service - Clean Architecture Version
A Model Context Protocol server for email operations
"""

import asyncio
import logging
import sys
from pathlib import Path
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
import mcp.server.stdio
import mcp.types as types

# Import the refactored tools
if __package__ is None or __package__ == "":
    # When executed as a script, ensure repository root is on sys.path
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from src.mcp_tools import MCPTools
else:
    from .mcp_tools import MCPTools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main entry point for the email MCP server"""
    logger.info("Starting MCP Email Service (Clean Architecture)...")
    
    # Create server instance
    server = Server("mcp-email-service")
    
    # Initialize MCP tools with clean architecture
    mcp_tools = MCPTools(server)
    
    # Run the server
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logger.info("Server running with stdio transport")
        
        init_options = InitializationOptions(
            server_name="mcp-email-service",
            server_version="1.0.5-clean",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(tools_changed=True),
                experimental_capabilities={},
            )
        )
        
        await server.run(
            read_stream,
            write_stream,
            init_options
        )

if __name__ == "__main__":
    asyncio.run(main())
