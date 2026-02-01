# Project Structure

This repository is the Mailbox Node.js CLI monorepo.

Top-level layout:

```
.
├── packages/
│   ├── cli/            # CLI entry + command definitions
│   ├── core/           # IMAP/SMTP + sqlite/cache + account migration
│   ├── shared/         # XDG paths + JSON contract helpers
│   └── workflows/      # digest/monitor/inbox workflows
├── mailbox-cli/        # npm launcher + platform binary packages
├── scripts/            # build helpers (notably scripts/build_binary.js)
└── docs/               # CLI contract + release docs (legacy docs under docs/archive/)
```

Notes:

- End user install: `npm i -g mailbox-cli` → `mailbox`.
- The CLI JSON contract is documented in `docs/CLI_JSON_CONTRACT.md` and locked
  by schemas under `docs/cli_json_schemas/`.
- Python/MCP implementation has been removed; remaining legacy docs are kept in
  `docs/archive/` for reference.
