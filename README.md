# Mailbox CLI

CLI-first email management for multi-account IMAP/SMTP with a local sync cache.

Primary interface: the `mailbox` CLI (Node.js implementation). This repo ships
prebuilt platform binaries via npm (no Python required for end users).

## Supported Providers

- 163 Mail (mail.163.com / mail.126.com)
- QQ Mail (mail.qq.com)
- Gmail (mail.google.com)
- Outlook/Hotmail
- Custom IMAP servers

## Install

### npm (recommended)

```bash
npm install -g @leeguoo/mailbox-cli
mailbox --help
```

The npm package ships prebuilt binaries per platform (no Python required).

### From source (development)

```bash
pnpm install
pnpm test

# build a local platform binary into mailbox-cli/packages/<platform>/bin/mailbox
pnpm build:binary
```

## Configure accounts

```bash
mkdir -p ~/.config/mailbox
cp examples/accounts.example.json ~/.config/mailbox/auth.json
```

Config locations:

- Credentials: `~/.config/mailbox/auth.json`
- Other settings: `~/.config/mailbox/config.toml`

## Common commands

```bash
# CLI help
mailbox --help

# list accounts
mailbox account list --json

# list unread emails (cache by default)
mailbox email list --unread-only --limit 20 --json

# show one email
mailbox email show 123456 --account-id my_account_id --json

# mark read (use --dry-run to validate first)
mailbox email mark 123456 --read --account-id my_account_id --folder INBOX --dry-run --json
mailbox email mark 123456 --read --account-id my_account_id --folder INBOX --confirm --json

# delete
mailbox email delete 123456 --account-id my_account_id --folder INBOX --confirm --json
```

### Cache + sync

- Cache DB default: `~/.local/share/mailbox/email_sync.db`
- Listing uses cache by default where possible. Add `--live` to force IMAP.

```bash
mailbox sync status --json
mailbox sync force --json
mailbox sync init
mailbox sync daemon
```

## AI usage guide

If you're integrating this CLI into an AI agent, start here:

- `docs/AI_SKILL_MAILBOX_CLI.md`

## OpenClaw integration

This repo includes an OpenClaw skill at `skills/mailbox/SKILL.md`.

OpenClaw loads skills from:
- `<workspace>/skills`
- `~/.openclaw/skills`

Quick link helper (symlink into `~/.openclaw/skills`):

```bash
./scripts/link_openclaw_skill.sh
```

Force replace an existing link:

```bash
./scripts/link_openclaw_skill.sh --force
```

To use this repo without copying files, add the repo skills directory to
`skills.load.extraDirs` in `~/.openclaw/openclaw.json`:

```json
{
  "skills": {
    "load": {
      "extraDirs": [
        "/path/to/mcp-email-service/skills"
      ]
    }
  }
}
```

OpenClaw handles channel delivery and scheduling; mailbox returns structured
JSON outputs and optional text summaries.

Verify OpenClaw picked up the skill:

```bash
openclaw skills list --eligible
openclaw skills check
```

## Contract

- `docs/CLI_JSON_CONTRACT.md`
