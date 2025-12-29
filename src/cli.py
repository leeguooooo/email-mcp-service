#!/usr/bin/env python3
"""
Command-line interface for invoking MCP Email Service tools.

This CLI bootstraps the same tool registry used by the MCP server and exposes
each tool as a subcommand. For complex inputs (objects/arrays of objects), use
the generic `call` command with JSON arguments.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence


if __package__ is None or __package__ == "":
    # When executed as a script, ensure repository root is on sys.path
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from mcp.server import Server
    from src.mcp_tools import MCPTools
    from src.core.tool_registry import tool_registry
else:
    from mcp.server import Server
    from .mcp_tools import MCPTools
    from .core.tool_registry import tool_registry


RESERVED_NAMESPACE_KEYS = {"command", "tool_name", "json", "args", "args_file", "arg"}


def _initialize_tools() -> MCPTools:
    """Instantiate MCPTools to register all tools for CLI usage."""
    server = Server("cli-email-service")
    return MCPTools(server)


def _parse_value(raw: str) -> Any:
    """Parse a CLI value into a Python object, attempting JSON first."""
    raw = raw.strip()
    if raw == "":
        return ""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _load_json_file(path: str) -> Dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON args file must contain a top-level object")
    return data


def _collect_call_args(args: argparse.Namespace) -> Dict[str, Any]:
    """Collect arguments for the generic `call` command."""
    payload: Dict[str, Any] = {}

    if args.args:
        parsed = json.loads(args.args)
        if not isinstance(parsed, dict):
            raise ValueError("--args must be a JSON object")
        payload.update(parsed)

    if args.args_file:
        payload.update(_load_json_file(args.args_file))

    for pair in args.arg or []:
        if "=" not in pair:
            raise ValueError(f"Invalid --arg '{pair}', expected key=value")
        key, value = pair.split("=", 1)
        payload[key] = _parse_value(value)

    return payload


def _add_schema_argument(
    parser: argparse.ArgumentParser,
    name: str,
    schema: Dict[str, Any],
    required: bool,
) -> None:
    flag = f"--{name.replace('_', '-')}"
    description = schema.get("description") or ""
    default = schema.get("default")
    schema_type = schema.get("type")
    choices = schema.get("enum")

    if schema_type == "boolean":
        parser.add_argument(
            flag,
            help=description,
            action=argparse.BooleanOptionalAction,
            default=default if default is not None else False,
            required=required,
        )
        return

    if schema_type == "integer":
        parser.add_argument(
            flag,
            help=description,
            type=int,
            default=default,
            required=required,
            choices=choices,
        )
        return

    if schema_type == "number":
        parser.add_argument(
            flag,
            help=description,
            type=float,
            default=default,
            required=required,
            choices=choices,
        )
        return

    if schema_type == "array":
        items = schema.get("items") or {}
        item_type = items.get("type")
        if item_type == "string":
            parser.add_argument(
                flag,
                help=description,
                nargs="+",
                default=default,
                required=required,
            )
        else:
            parser.add_argument(
                flag,
                help=f"{description} (JSON array)",
                type=json.loads,
                default=default,
                required=required,
            )
        return

    if schema_type == "object":
        parser.add_argument(
            flag,
            help=f"{description} (JSON object)",
            type=json.loads,
            default=default,
            required=required,
        )
        return

    # Fallback to string
    parser.add_argument(
        flag,
        help=description,
        default=default,
        required=required,
        choices=choices,
    )


def _build_parser(tools: Iterable[Any]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-email-cli",
        description="Call MCP Email Service tools from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-tools", help="List all available tools")
    list_parser.add_argument("--json", action="store_true", help="Output JSON")

    schema_parser = subparsers.add_parser("schema", help="Print a tool's input schema")
    schema_parser.add_argument("tool_name", help="Tool name")
    schema_parser.add_argument("--json", action="store_true", help="Output JSON")

    call_parser = subparsers.add_parser(
        "call", help="Call any tool with JSON arguments"
    )
    call_parser.add_argument("tool_name", help="Tool name")
    call_parser.add_argument(
        "--args",
        help="JSON object string of arguments, e.g. '{\"limit\": 10}'",
    )
    call_parser.add_argument(
        "--args-file",
        help="Path to JSON file containing arguments",
    )
    call_parser.add_argument(
        "--arg",
        action="append",
        default=[],
        help="Single argument as key=value. Can be repeated.",
    )
    call_parser.add_argument("--json", action="store_true", help="Output raw JSON list")

    # One subcommand per tool based on schema
    for tool in tools:
        tool_name = getattr(tool, "name", None) or tool.get("name")
        description = getattr(tool, "description", "") or tool.get("description", "")
        input_schema = getattr(tool, "inputSchema", None) or tool.get("inputSchema") or {}

        # Skip meta commands if any happen to overlap
        if tool_name in {"list-tools", "schema", "call"}:
            continue

        tool_parser = subparsers.add_parser(
            tool_name,
            help=description,
            description=description,
        )
        required_props = set(input_schema.get("required", []) or [])
        for prop_name, prop_schema in (input_schema.get("properties") or {}).items():
            _add_schema_argument(
                tool_parser,
                prop_name,
                prop_schema,
                required=prop_name in required_props,
            )
        tool_parser.add_argument("--json", action="store_true", help="Output raw JSON list")

    return parser


def _namespace_to_tool_args(
    ns: argparse.Namespace, input_schema: Dict[str, Any]
) -> Dict[str, Any]:
    data = vars(ns)
    props = set((input_schema.get("properties") or {}).keys())
    payload: Dict[str, Any] = {}
    for key in props:
        if key in data:
            value = data[key]
            if value is not None:
                payload[key] = value
    return payload


def _print_result(result: List[Dict[str, Any]], as_json: bool) -> None:
    if as_json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return

    for item in result:
        if item.get("type") == "text":
            text = item.get("text", "")
            if text:
                sys.stdout.write(str(text) + "\n")
        else:
            sys.stdout.write(json.dumps(item, ensure_ascii=False) + "\n")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    mcp_tools = _initialize_tools()
    tools = sorted(tool_registry.list_tools(), key=lambda t: t.name)
    parser = _build_parser(tools)

    args = parser.parse_args(argv)

    if args.command == "list-tools":
        if args.json:
            json.dump(
                [tool.model_dump() for tool in tools],
                sys.stdout,
                ensure_ascii=False,
                indent=2,
            )
            sys.stdout.write("\n")
        else:
            for tool in tools:
                sys.stdout.write(f"{tool.name}: {tool.description}\n")
        return 0

    if args.command == "schema":
        tool_def = tool_registry.get_tool_definition(args.tool_name)
        if not tool_def:
            sys.stderr.write(f"Unknown tool: {args.tool_name}\n")
            return 1
        schema = tool_def.schema
        json.dump(schema, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    if args.command == "call":
        try:
            payload = _collect_call_args(args)
        except Exception as exc:
            sys.stderr.write(str(exc) + "\n")
            return 2
        try:
            result = asyncio.run(mcp_tools.call_tool(args.tool_name, payload))
        except Exception as exc:
            sys.stderr.write(str(exc) + "\n")
            return 1
        _print_result(result, args.json)
        return 0

    # Tool-specific subcommand
    tool_def = tool_registry.get_tool_definition(args.command)
    if not tool_def:
        sys.stderr.write(f"Unknown tool: {args.command}\n")
        return 1

    payload = _namespace_to_tool_args(args, tool_def.schema)
    try:
        result = asyncio.run(mcp_tools.call_tool(args.command, payload))
    except Exception as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1

    _print_result(result, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

