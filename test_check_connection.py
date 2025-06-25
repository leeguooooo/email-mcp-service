#!/usr/bin/env python3
"""Test script to verify check_connection fix"""

import sys
sys.path.insert(0, 'src')

from legacy_operations import check_connection
from core.system_handlers import SystemHandlers
from core.tool_handlers import ToolContext
from account_manager import AccountManager
from pathlib import Path

def test_direct_connection():
    """Test the check_connection function directly"""
    print("=== Testing check_connection directly ===")
    result = check_connection()
    print(f"Result: {result}")
    print()
    return result

def test_through_handler():
    """Test through the MCP handler"""
    print("=== Testing through MCP handler ===")
    
    # Setup context
    config_path = Path(__file__).parent / "accounts.json"
    account_manager = AccountManager(str(config_path))
    
    def get_message(key, *args, **kwargs):
        messages = {
            'error': '❌ Error: ',
            'operation_failed': '❌ Operation failed: '
        }
        msg = messages.get(key, key)
        if args or kwargs:
            return msg.format(*args, **kwargs)
        return msg
    
    context = ToolContext(account_manager, get_message)
    
    # Call handler
    result = SystemHandlers.handle_check_connection({}, context)
    print(f"Handler result: {result}")
    return result

if __name__ == "__main__":
    print("Testing check_connection fix...")
    print()
    
    # Test direct call
    direct_result = test_direct_connection()
    
    # Test through handler
    handler_result = test_through_handler()
    
    # Verify results
    if 'error' in direct_result:
        print(f"\n❌ Direct test failed: {direct_result['error']}")
    elif direct_result.get('success'):
        print(f"\n✅ Direct test passed: {direct_result['total_accounts']} accounts checked")
    
    if handler_result and handler_result[0].get('type') == 'text':
        text = handler_result[0]['text']
        if '❌' in text and 'string indices' in text:
            print("\n❌ Handler test failed with string indices error")
        else:
            print("\n✅ Handler test passed")