"""
Lightweight tests for the MCP Email Service CLI.

These tests validate argument parsing and tool exposure without
calling live IMAP/SMTP operations.
"""

from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import sys

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli import _build_parser, _collect_call_args, _initialize_tools, main as cli_main
from src.core.tool_registry import tool_registry


class TestCLI(unittest.TestCase):
    """Validate CLI behavior and parsing."""

    @classmethod
    def setUpClass(cls) -> None:
        # Ensure tools are registered for parser construction
        _initialize_tools()

    def test_list_tools_json_output(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main(["list-tools", "--json"])
        self.assertEqual(rc, 0)
        tools = json.loads(buf.getvalue())
        tool_names = {t["name"] for t in tools}
        self.assertIn("list_emails", tool_names)
        self.assertIn("send_email", tool_names)

    def test_tool_subcommand_parsing(self) -> None:
        tools = tool_registry.list_tools()
        parser = _build_parser(tools)
        ns = parser.parse_args(["list_emails", "--limit", "5", "--no-unread-only"])
        self.assertEqual(ns.command, "list_emails")
        self.assertEqual(ns.limit, 5)
        self.assertFalse(ns.unread_only)

    def test_collect_call_args(self) -> None:
        tools = tool_registry.list_tools()
        parser = _build_parser(tools)
        ns = parser.parse_args(
            [
                "call",
                "mark_emails",
                "--arg",
                'email_ids=["1","2"]',
                "--arg",
                'mark_as="read"',
            ]
        )
        payload = _collect_call_args(ns)
        self.assertEqual(payload["email_ids"], ["1", "2"])
        self.assertEqual(payload["mark_as"], "read")


if __name__ == "__main__":
    unittest.main()

