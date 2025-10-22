"""Command-line client for browsing MCP-managed mailboxes."""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from typing import Any, Dict, Iterable

from .client import MailboxClient


def build_parser() -> argparse.ArgumentParser:
    """Create argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="mailbox-client",
        description="轻量级邮箱浏览客户端，访问 MCP 邮件服务中的所有账户",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)
    
    # 交互式模式
    interactive_parser = subparsers.add_parser(
        "interactive",
        help="启动交互式模式（推荐新手使用）",
    )
    interactive_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果",
    )

    # list-accounts
    list_accounts_parser = subparsers.add_parser(
        "list-accounts",
        help="列出所有已配置的邮箱账户",
    )
    list_accounts_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果",
    )

    # list-emails
    list_emails_parser = subparsers.add_parser(
        "list-emails",
        help="查看邮件列表（默认聚合所有账户）",
    )
    list_emails_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="返回的邮件数量（默认 20）",
    )
    list_emails_parser.add_argument(
        "--unread-only",
        action="store_true",
        help="仅显示未读邮件",
    )
    list_emails_parser.add_argument(
        "--account-id",
        help="指定邮箱账户 ID，只查看该账户的邮件",
    )
    list_emails_parser.add_argument(
        "--folder",
        default="INBOX",
        help="指定邮箱文件夹（默认 INBOX）",
    )
    list_emails_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果",
    )

    # show-email
    show_email_parser = subparsers.add_parser(
        "show-email",
        help="查看单封邮件的详细内容",
    )
    show_email_parser.add_argument(
        "email_id",
        help="邮件 UID（可在 list-emails 输出中找到）",
    )
    show_email_parser.add_argument(
        "--account-id",
        help="邮件所属的邮箱账户 ID（跨账户查询时必传）",
    )
    show_email_parser.add_argument(
        "--folder",
        default="INBOX",
        help="邮件所在文件夹（默认 INBOX）",
    )
    show_email_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果",
    )

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # 如果没有提供命令，启动交互式模式
    if args.command is None:
        return _interactive_mode()

    client = MailboxClient()

    if args.command == "interactive":
        return _interactive_mode(args.json)

    if args.command == "list-accounts":
        result = client.list_accounts()
        return _handle_output(result, args.json, _print_accounts)

    if args.command == "list-emails":
        result = client.list_emails(
            limit=args.limit,
            unread_only=args.unread_only,
            folder=args.folder,
            account_id=args.account_id,
        )
        return _handle_output(result, args.json, _print_emails)

    if args.command == "show-email":
        result = client.get_email_detail(
            args.email_id,
            folder=args.folder,
            account_id=args.account_id,
        )
        return _handle_output(result, args.json, _print_email_detail)

    parser.error("未知命令")
    return 2


def _handle_output(result: Dict[str, Any], as_json: bool, printer) -> int:
    """统一处理输出和退出码。"""
    if as_json:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if result.get("success") else 1

    if not result.get("success"):
        error_message = result.get("error", "未知错误")
        print(f"❌ 操作失败: {error_message}", file=sys.stderr)
        return 1

    printer(result)
    return 0


def _print_accounts(result: Dict[str, Any]) -> None:
    """打印账户列表。"""
    accounts = result.get("accounts") or []
    if not accounts:
        print("ℹ️  尚未配置任何邮箱账户。请先运行 setup.py 添加账户。")
        return

    print(f"📬 共 {len(accounts)} 个账户：")
    header = f"{'ID':<20} {'邮箱地址':<32} {'服务商':<12} {'默认?':<6} 描述"
    print(header)
    print("-" * len(header))

    for account in accounts:
        identifier = _shorten(account.get("id", ""), 20)
        email = _shorten(account.get("email", ""), 32)
        provider = _shorten(account.get("provider", ""), 12)
        is_default = "是" if account.get("is_default") else "否"
        description = account.get("description", "") or "-"
        print(f"{identifier:<20} {email:<32} {provider:<12} {is_default:<6} {description}")


def _print_emails(result: Dict[str, Any]) -> None:
    """打印邮件列表。"""
    accounts_info = result.get("accounts_info") or []
    if accounts_info:
        print("📂 各账户汇总：")
        for info in accounts_info:
            account = info.get("account", "未知账户")
            total = info.get("total", 0)
            unread = info.get("unread", 0)
            fetched = info.get("fetched", 0)
            print(f"  • {account}: 未读 {unread} / 总数 {total}，本次显示 {fetched}")
        print()

    emails = result.get("emails") or []
    if not emails:
        if result.get("unread_only"):
            print("📭 当前没有未读邮件。")
        else:
            print("📭 暂无邮件记录。")
        return

    header = f"{'UID':<18} {'账户':<28} {'账户ID':<12} {'状态':<4} {'时间':<19} 主题"
    print(header)
    print("-" * len(header))

    for email in emails:
        uid = _shorten(str(email.get("id", "")), 18)
        account = _shorten(email.get("account", ""), 28)
        account_id = _shorten(email.get("account_id", ""), 12)
        status = "未读" if email.get("unread") else "已读"
        date = _shorten(email.get("date", ""), 19)
        subject = textwrap.shorten(
            email.get("subject") or "(无主题)",
            width=50,
            placeholder="…",
        )
        print(f"{uid:<18} {account:<28} {account_id:<12} {status:<4} {date:<19} {subject}")

    print("\n提示: 可使用 `show-email <UID> --account-id <账户ID>` 查看详细内容。")


def _print_email_detail(result: Dict[str, Any]) -> None:
    """打印单封邮件详情。"""
    print("📝 邮件详情：")
    print(f"主题: {result.get('subject', '(无主题)')}")
    print(f"发件人: {result.get('from', '-')}")
    print(f"收件人: {result.get('to', '-')}")
    cc_value = result.get("cc") or "-"
    if cc_value:
        print(f"抄送: {cc_value}")
    print(f"时间: {result.get('date', '-')}")
    print(f"账户: {result.get('account', '-')}")
    if result.get("account_id"):
        print(f"账户ID: {result['account_id']}")
    print(f"状态: {'未读' if result.get('unread') else '已读'}")

    attachments = result.get("attachments") or []
    if attachments:
        print("附件:")
        for attachment in attachments:
            filename = attachment.get("filename", "未知附件")
            size = attachment.get("size", 0)
            content_type = attachment.get("content_type", "?")
            print(f"  • {filename} ({size} bytes, {content_type})")
    else:
        print("附件: 无")

    body = (result.get("body") or "").strip()
    if not body and result.get("html_body"):
        body = result["html_body"].strip()
        print("\n⚠️  正文只有 HTML 内容，以下为原始 HTML：")

    if body:
        divider = "-" * 40
        print(f"\n{divider}\n正文:\n{divider}")
        print(body)
    else:
        print("\n正文: (无内容)")


def _shorten(value: Any, width: int) -> str:
    """Helper to shorten strings with ellipsis while keeping table alignment."""
    text = str(value) if value is not None else ""
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _interactive_mode(use_json: bool = False) -> int:
    """交互式模式 - 类似 setup.py 的菜单界面"""
    client = MailboxClient()
    
    while True:
        print("\n" + "=" * 50)
        print("📧 MCP 邮箱浏览客户端 - 交互式模式")
        print("=" * 50)
        print("请选择操作:")
        print("1. 查看所有账户")
        print("2. 查看邮件列表")
        print("3. 查看未读邮件")
        print("4. 查看单封邮件详情")
        print("5. 查看指定账户的邮件")
        print("0. 退出")
        
        choice = input("\n请选择 (0-5): ").strip()
        
        if choice == "0":
            print("\n👋 再见！")
            break
        elif choice == "1":
            result = client.list_accounts()
            _handle_output(result, use_json, _print_accounts)
        elif choice == "2":
            limit = _get_limit()
            result = client.list_emails(limit=limit)
            _handle_output(result, use_json, _print_emails)
        elif choice == "3":
            limit = _get_limit()
            result = client.list_emails(limit=limit, unread_only=True)
            _handle_output(result, use_json, _print_emails)
        elif choice == "4":
            _show_email_detail_interactive(client, use_json)
        elif choice == "5":
            _show_account_emails_interactive(client, use_json)
        else:
            print("❌ 无效的选择，请重试")
        
        if choice in ["1", "2", "3", "4", "5"]:
            input("\n按回车键继续...")
    
    return 0


def _get_limit() -> int:
    """获取邮件数量限制"""
    while True:
        try:
            limit_str = input("显示多少封邮件? (默认20): ").strip()
            if not limit_str:
                return 20
            limit = int(limit_str)
            if limit > 0:
                return limit
            else:
                print("❌ 请输入大于0的数字")
        except ValueError:
            print("❌ 请输入有效的数字")


def _show_email_detail_interactive(client: MailboxClient, use_json: bool) -> None:
    """交互式查看邮件详情"""
    email_id = input("请输入邮件UID: ").strip()
    if not email_id:
        print("❌ 邮件UID不能为空")
        return
    
    account_id = input("请输入账户ID (可选): ").strip() or None
    
    result = client.get_email_detail(email_id, account_id=account_id)
    _handle_output(result, use_json, _print_email_detail)


def _show_account_emails_interactive(client: MailboxClient, use_json: bool) -> None:
    """交互式查看指定账户的邮件"""
    # 先显示账户列表
    accounts_result = client.list_accounts()
    if not accounts_result.get("success"):
        print("❌ 无法获取账户列表")
        return
    
    accounts = accounts_result.get("accounts", [])
    if not accounts:
        print("📭 没有配置任何账户")
        return
    
    print("\n📬 可用账户:")
    for i, account in enumerate(accounts, 1):
        print(f"{i}. {account.get('id', '')} - {account.get('email', '')}")
    
    try:
        choice = int(input("\n请选择账户 (输入数字): ").strip())
        if 1 <= choice <= len(accounts):
            selected_account = accounts[choice - 1]
            account_id = selected_account.get("id")
            
            limit = _get_limit()
            unread_only = input("只显示未读邮件? (y/n): ").strip().lower() == 'y'
            
            result = client.list_emails(
                limit=limit,
                unread_only=unread_only,
                account_id=account_id
            )
            _handle_output(result, use_json, _print_emails)
        else:
            print("❌ 无效的选择")
    except ValueError:
        print("❌ 请输入有效的数字")


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
