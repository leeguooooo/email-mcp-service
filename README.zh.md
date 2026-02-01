# Mailbox CLI

以 CLI 为核心的多邮箱（IMAP/SMTP）管理工具，支持本地同步缓存（SQLite）。

主入口：`mailbox` CLI（Node.js 实现）。本仓库通过 npm 分发按平台预编译二进制，终端用户无需安装 Python。

说明：本仓库不再提供 MCP server/stdio 能力。

## 安装

### npm（推荐）

```bash
npm install -g mailbox-cli
mailbox --help
```

npm 包按平台提供预编译二进制（无需 Python）。

### 从源码开发

```bash
pnpm install
pnpm test
pnpm build:binary
```

## 配置邮箱

```bash
mkdir -p ~/.config/mailbox
cp examples/accounts.example.json ~/.config/mailbox/auth.json
```

配置文件位置：

- 认证信息：`~/.config/mailbox/auth.json`
- 其他配置：`~/.config/mailbox/config.toml`

## 常用命令

```bash
# 交互式
mailbox

# 列出账户
mailbox account list --json

# 列出未读邮件（默认优先缓存；--live 强制走 IMAP）
mailbox email list --unread-only --limit 20 --json

# 查看邮件详情
mailbox email show 123456 --account-id my_account_id --json

# 标记已读（建议先 dry-run）
mailbox email mark 123456 --read --account-id my_account_id --folder INBOX --dry-run --json
mailbox email mark 123456 --read --account-id my_account_id --folder INBOX --json

# 连接测试
mailbox account test-connection --json
```

## AI 集成说明

- `docs/AI_SKILL_MAILBOX_CLI.md`
