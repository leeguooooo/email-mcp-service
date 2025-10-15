#!/bin/bash
# MCP Email Service startup script
# Automatically detects and uses uv if available, otherwise falls back to python3
set -euo pipefail

# Change to script directory to ensure correct working directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if command -v uv >/dev/null 2>&1; then
  exec uv run python -m src.main "$@"
else
  echo "Warning: uv not found in PATH; falling back to system python3." >&2
  exec python3 -m src.main "$@"
fi
