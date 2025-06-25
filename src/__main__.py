#!/usr/bin/env python3
"""
Entry point for running as a module: python -m mcp_email_service
"""

import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run main
from main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())