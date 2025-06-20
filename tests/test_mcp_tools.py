"""
Unit tests for MCP tool definitions - no external dependencies
"""
import unittest
from pathlib import Path

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from src.mcp_tools import MCPTools


class TestMCPTools(unittest.TestCase):
    """Test MCP tool definitions and structure"""
    
    def setUp(self):
        """Create test server and tools"""
        self.server = Server("test-email-service")
        self.mcp_tools = MCPTools(self.server)
    
    def test_tool_definitions(self):
        """Test all tool definitions are present"""
        tools = self.mcp_tools.get_tool_definitions()
        tool_names = [tool['name'] for tool in tools]
        
        # Check essential tools exist
        essential_tools = [
            'check_connection', 'list_emails', 'get_email_detail',
            'mark_email_read', 'mark_email_unread', 'delete_email',
            'send_email', 'search_emails', 'list_folders',
            'batch_mark_read', 'batch_delete_emails'
        ]
        
        for tool in essential_tools:
            self.assertIn(tool, tool_names, f"Tool {tool} not found")
    
    def test_tool_schemas(self):
        """Test tool schemas are valid"""
        tools = self.mcp_tools.get_tool_definitions()
        
        for tool in tools:
            # Check required fields
            self.assertIn('name', tool)
            self.assertIn('description', tool)
            self.assertIn('inputSchema', tool)
            
            # Check input schema structure
            schema = tool['inputSchema']
            self.assertEqual(schema['type'], 'object')
            
            if 'properties' in schema:
                # Check property types
                for prop_name, prop_def in schema['properties'].items():
                    self.assertIn('type', prop_def, 
                                f"Property {prop_name} in {tool['name']} missing type")
    
    def test_list_emails_defaults(self):
        """Test list_emails has correct defaults"""
        tools = self.mcp_tools.get_tool_definitions()
        list_emails = next(t for t in tools if t['name'] == 'list_emails')
        
        # Check unread_only defaults to True
        unread_prop = list_emails['inputSchema']['properties']['unread_only']
        self.assertEqual(unread_prop['default'], True)
        
        # Check limit defaults to 50
        limit_prop = list_emails['inputSchema']['properties']['limit']
        self.assertEqual(limit_prop['default'], 50)
    
    def test_required_parameters(self):
        """Test required parameters are properly defined"""
        tools = self.mcp_tools.get_tool_definitions()
        
        # Tools that should have required parameters
        required_params = {
            'get_email_detail': ['email_id'],
            'mark_email_read': ['email_id'],
            'delete_email': ['email_id'],
            'send_email': ['to', 'subject', 'body'],
            'reply_email': ['email_id', 'body'],
            'batch_mark_read': ['email_ids'],
            'batch_delete_emails': ['email_ids']
        }
        
        for tool_name, required in required_params.items():
            tool = next((t for t in tools if t['name'] == tool_name), None)
            self.assertIsNotNone(tool, f"Tool {tool_name} not found")
            
            if 'required' in tool['inputSchema']:
                tool_required = tool['inputSchema']['required']
                for param in required:
                    self.assertIn(param, tool_required,
                                f"Required param {param} not found in {tool_name}")
    
    def test_enum_values(self):
        """Test enum values are properly defined"""
        tools = self.mcp_tools.get_tool_definitions()
        
        # Check search_in enum
        search_tool = next(t for t in tools if t['name'] == 'search_emails')
        search_in = search_tool['inputSchema']['properties']['search_in']
        self.assertIn('enum', search_in)
        expected_values = ["subject", "from", "body", "to", "all"]
        self.assertEqual(set(search_in['enum']), set(expected_values))
        
        # Check flag_type enum
        flag_tool = next(t for t in tools if t['name'] == 'flag_email')
        flag_type = flag_tool['inputSchema']['properties']['flag_type']
        self.assertIn('enum', flag_type)
        expected_flags = ["flagged", "important", "answered"]
        self.assertEqual(set(flag_type['enum']), set(expected_flags))
    
    def test_batch_operations(self):
        """Test batch operations have array inputs"""
        tools = self.mcp_tools.get_tool_definitions()
        batch_tools = [t for t in tools if 'batch' in t['name']]
        
        for tool in batch_tools:
            # Find the array parameter (usually email_ids)
            props = tool['inputSchema']['properties']
            has_array = False
            
            for prop_name, prop_def in props.items():
                if prop_def.get('type') == 'array':
                    has_array = True
                    # Check array items type
                    self.assertIn('items', prop_def)
                    self.assertEqual(prop_def['items']['type'], 'string')
            
            self.assertTrue(has_array, 
                          f"Batch tool {tool['name']} missing array parameter")
    
    def test_tool_descriptions(self):
        """Test all tools have meaningful descriptions"""
        tools = self.mcp_tools.get_tool_definitions()
        
        for tool in tools:
            desc = tool['description']
            # Description should be non-empty and meaningful
            self.assertTrue(len(desc) > 10, 
                          f"Tool {tool['name']} has too short description")
            # Description should not have placeholder text
            self.assertNotIn('TODO', desc.upper())
            self.assertNotIn('FIXME', desc.upper())
    
    def test_success_result_formatting(self):
        """Test result formatting logic"""
        # Test send_email formatting
        result = {'success': True, 'recipients': ['a@test.com', 'b@test.com']}
        formatted = self.mcp_tools._format_success_result('send_email', result)
        self.assertIn('2 recipient(s)', formatted)
        
        # Test search_emails formatting
        result = {'success': True, 'displayed': 10, 'total_found': 50}
        formatted = self.mcp_tools._format_success_result('search_emails', result)
        self.assertIn('Found 10 emails', formatted)
        self.assertIn('total: 50', formatted)
        
        # Test list_folders formatting
        result = {
            'success': True,
            'folders': [
                {'name': 'INBOX', 'message_count': 100},
                {'name': 'Sent', 'message_count': 50}
            ]
        }
        formatted = self.mcp_tools._format_success_result('list_folders', result)
        self.assertIn('Found 2 folders', formatted)
        self.assertIn('INBOX (100 messages)', formatted)


if __name__ == '__main__':
    unittest.main()