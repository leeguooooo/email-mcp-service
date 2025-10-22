# 📥 MCP 邮箱浏览客户端

这个子项目提供了一个简单的命令行客户端，可以直接读取主项目中的 MCP 邮件服务，聚合查看全部邮箱账户的邮件。

## 目录结构

```
clients/
└── mailbox_client/
    ├── README.md          # 本说明文件
    ├── __init__.py        # 包初始化
    ├── __main__.py        # 允许 python -m clients.mailbox_client 运行
    ├── client.py          # 复用主项目服务层的封装
    └── cli.py             # 命令行实现
```

## 快速开始

> 运行前请确保已经通过 `python setup.py` 配置好了邮箱账户，并完成过至少一次同步。

### 🎯 交互式模式（推荐新手）

最简单的使用方式，类似 `setup.py` 的菜单界面：

```bash
# 启动交互式模式
uv run python -m clients.mailbox_client

# 或者显式指定交互式模式
uv run python -m clients.mailbox_client interactive
```

交互式模式提供友好的菜单界面，无需记忆命令参数。

### 📋 命令行模式（适合脚本）

```bash
# 列出所有账户
uv run python -m clients.mailbox_client list-accounts

# 查看最近 20 封邮件（默认聚合全部账户）
uv run python -m clients.mailbox_client list-emails --limit 20

# 查看未读邮件
uv run python -m clients.mailbox_client list-emails --unread-only

# 查看指定账户的邮件
uv run python -m clients.mailbox_client list-emails --account-id my_account_id

# 查看单封邮件详情（需要提供账户 ID）
uv run python -m clients.mailbox_client show-email 123456 --account-id my_account_id
```

所有命令都支持 `--json` 参数，以 JSON 方式输出原始数据，方便与其他工具集成。

## 功能特性

- ✅ 聚合浏览多个邮箱的收件箱
- ✅ 支持中文终端输出 & JSON 输出
- ✅ 可快速查看单封邮件详情（主题、正文、附件等）
- ✅ 不与主项目代码混合：全部逻辑位于 `clients/mailbox_client/` 子目录

如需定制更复杂的展示界面，可以直接基于 `client.py` 中的 `MailboxClient` 类进行二次开发。
