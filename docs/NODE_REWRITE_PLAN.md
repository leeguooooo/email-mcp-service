# Node Rewrite Plan (CLI + Skill)

## Summary
Rebuild the project as a pure Node.js implementation packaged into prebuilt
platform binaries and distributed via npm. Keep the existing `mailbox` CLI
contract and config/data compatibility, but replace the Python codebase with
Node.js.

This plan targets the following commands as MVP:
- account
- email
- sync
- digest
- monitor
- inbox

## Goals
- Pure Node.js implementation (JS, not TS).
- Zero-setup user experience: `npm i -g mailbox-cli` -> `mailbox` (no Python,
  no native build/compilation on user machines).
- Keep current CLI JSON output contract for skill usage.
- Keep config/data compatibility:
  - `~/.config/mailbox/` (auth.json, config.toml)
  - `~/.local/share/mailbox/` (db + workflow configs)
  - Honor `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `MAILBOX_CONFIG_DIR`,
    `MAILBOX_DATA_DIR`.
- No MCP server/stdio support.

## Non-goals
- GUI app or desktop client.
- MCP protocol or stdio server.
- Rewriting third-party services (keep same providers/flows).
- Pure-JS distribution that requires local native builds on install.

## Distribution Decision (User Simplicity)
To keep installation as simple as possible, we will **continue the current npm
distribution model**:
- `mailbox-cli` (launcher package) provides the `mailbox` command.
- Platform packages provide the actual binary.

The difference is the **binary will be produced from the Node.js rewrite**,
not from Python. This keeps the user experience unchanged (`npm i -g
mailbox-cli`) and avoids native compilation at install time.

## Compatibility Contract
### CLI
- Global flags: `--json`, `--pretty` (same semantics).
- Exit codes:
  - 0 success
  - 1 operation failed
  - 2 invalid usage
- JSON output includes `success` and `error` fields.
- Default interactive mode when no command is given.

### Paths
Use XDG defaults:
- Config: `~/.config/mailbox/`
- Data: `~/.local/share/mailbox/`

Legacy compatibility:
- If `auth.json` missing, read legacy `accounts.json` (repo `data/` or old paths)
  and migrate to `auth.json` on first successful load.

## Proposed Node Architecture
Monorepo at repository root using pnpm workspaces (JS).

```
packages/
  core/              # IMAP/SMTP, parsing, cache, storage
  cli/               # CLI command definitions and I/O
  workflows/         # digest/monitor/inbox orchestration
  shared/            # config, logging, types, utils
```

Core layers:
- config: XDG + env overrides, config loading, validation
- storage: sqlite (cache + metadata) + file-backed configs
- email: list/search/show/mark/delete/move/flag/send
- sync: scheduler + incremental cache + health stats
- workflows: digest/monitor/inbox (CLI wrappers calling services)

## Tech Stack
- IMAP: imapflow
- SMTP: nodemailer
- Parsing: mailparser
- SQLite: better-sqlite3
- Config validation: zod
- Logging: pino
- CLI framework: commander
- Tests: vitest

## CLI Module Mapping (MVP)
- account
  - list
  - test-connection
- email
  - list, search, show
  - mark, delete, send, reply, forward
  - folders, attachments, flag, move
- sync
  - status, force, daemon, init, health, watch
- digest
  - run, daemon, config
- monitor
  - run, status, config, test
- inbox
  - organizer workflow

## Data + Config Files
Keep existing filenames and locations:
- `auth.json`
- `config.toml`
- `email_sync.db`
- `notification_history.db`
- `sync_config.json`
- `sync_health_history.json`
- `daily_digest_config.json`
- `notification_config.json`
- `email_monitor_config.json`

## Migration Strategy (No MCP)
Phase 0: Contract freeze
- Record CLI output samples for all MVP commands.
- Document JSON schema per command.

Phase 1: Node scaffolding
- Add root `package.json` with pnpm workspaces.
- Create `packages/cli`, `packages/core`, `packages/shared`, `packages/workflows`.
- Wire `mailbox` bin to CLI entry.

Phase 2: Config + storage parity
- Implement XDG path resolver + env overrides.
- Read `auth.json` or migrate legacy `accounts.json`.
- Set up sqlite schema compatible with existing data.

Phase 3: Email core
- Implement IMAP session manager, search/list/show, mark/delete/move/flag.
- Implement SMTP send/reply/forward.

Phase 4: Sync + cache
- Implement incremental sync + health stats + scheduler loop.
- Ensure `sync` commands match current JSON output contract.

Phase 5: Workflows
- Implement digest/monitor/inbox using Node services.
- Keep config file names and formats.

Phase 6: Remove Python/MCP
- Remove Python MCP code and update docs.
- Update skill docs to reference Node CLI.
- Keep launcher + platform binary packages, but swap the binary build pipeline
  to produce Node-based binaries.

## Testing Plan
- Unit tests for config resolver and parsers.
- Mocked IMAP/SMTP tests (no live credentials).
- Integration tests for sqlite schema + migrations.
- Snapshot tests for CLI JSON output.

## Release Plan
- Publish `mailbox-cli` npm package with `mailbox` bin.
- Publish platform binary packages built from the Node implementation.
- Ensure `npm i -g mailbox-cli` works with no Python dependency and no native
  compilation step on user machines.
- Document upgrade/migration for existing users.

## Open Questions
- Exact JSON schema to preserve per command (collect samples first).
- How to handle provider-specific auth (OAuth vs password) in `auth.json`.
- Binary packaging tool choice (e.g., pkg vs nexe) and native module bundling
  strategy (e.g., `better-sqlite3`).
