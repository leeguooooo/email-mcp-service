#+#+#+#+### Mailbox CLI

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
npm install -g mailbox-cli
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
# interactive mode
mailbox

# list accounts
mailbox account list --json

# list unread emails (cache by default)
mailbox email list --unread-only --limit 20 --json

# show one email
mailbox email show 123456 --account-id my_account_id --json

# mark read (use --dry-run to validate first)
mailbox email mark 123456 --read --account-id my_account_id --folder INBOX --dry-run --json
mailbox email mark 123456 --read --account-id my_account_id --folder INBOX --json

# delete
mailbox email delete 123456 --account-id my_account_id --folder INBOX --json
```

### Cache + sync

- Cache DB default: `~/.local/share/mailbox/email_sync.db`
- Listing uses cache by default where possible. Add `--live` to force IMAP.

```bash
mailbox sync status --json
mailbox sync force --json
mailbox sync init
mailbox sync daemon
mailbox db size --json
```

## AI usage guide

If you're integrating this CLI into an AI agent, start here:

- `docs/AI_SKILL_MAILBOX_CLI.md`
