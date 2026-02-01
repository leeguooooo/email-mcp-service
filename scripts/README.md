# Scripts

This directory contains build helpers for the Node CLI rewrite.

Key scripts:

- `scripts/build_binary.js`: builds a `pkg`-based `mailbox` binary and copies it
  into the appropriate `mailbox-cli/packages/<platform>/bin/` directory.

Legacy:

- Older Python workflow scripts and HTTP API helpers have been removed. If you
  need historical context, see `docs/archive/`.
