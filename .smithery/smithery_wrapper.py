#!/usr/bin/env python3
"""
Smithery wrapper for MCP Email Service
Handles account setup and launches the main service
"""

import os
import sys
import subprocess
import json
from pathlib import Path

def check_accounts_configured():
    """Check if email accounts are configured"""
    # Get repo root (parent of .smithery/)
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "accounts.json"
    if not config_path.exists():
        return False
    
    try:
        with open(config_path, 'r') as f:
            accounts = json.load(f)
            return len(accounts) > 0
    except:
        return False

def main():
    # Check if accounts are configured
    if not check_accounts_configured():
        print("Email accounts not configured. Please run:")
        print("  python setup.py")
        print("")
        print("Then restart the MCP server.")
        sys.exit(1)
    
    # Launch the main service from repo root
    repo_root = Path(__file__).resolve().parents[1]
    main_py = repo_root / "src" / "main.py"
    subprocess.run([sys.executable, str(main_py)])

if __name__ == "__main__":
    main()