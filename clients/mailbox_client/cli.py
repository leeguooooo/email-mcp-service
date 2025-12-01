"""Command-line client for browsing MCP-managed mailboxes."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterable
import datetime

from .client import MailboxClient
from src.background.sync_scheduler import get_scheduler, start_background_sync
from src.background.sync_health_monitor import get_health_monitor
from src.config.version import __version__


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
        help="查看邮件列表（默认聚合所有账户，优先读取缓存）",
    )
    list_emails_parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="返回的邮件数量（默认 100）",
    )
    list_emails_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="分页偏移量",
    )
    list_emails_parser.add_argument(
        "--unread-only",
        action="store_true",
        help="仅显示未读邮件",
    )
    list_emails_parser.add_argument(
        "--account-id",
        help="指定邮箱账户 ID/邮箱，只查看该账户的邮件",
    )
    list_emails_parser.add_argument(
        "--folder",
        default="all",
        help="指定邮箱文件夹（默认 all=不筛选；IMAP 回退时用 INBOX）",
    )
    list_emails_parser.add_argument(
        "--live",
        action="store_true",
        help="强制走 IMAP 实时获取（默认使用缓存）",
    )
    list_emails_parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出结果",
    )

    # search-emails
    search_parser = subparsers.add_parser(
        "search",
        help="搜索邮件（默认使用缓存）",
    )
    search_parser.add_argument("--query", required=True, help="搜索关键词")
    search_parser.add_argument("--account-id", help="账户 ID/邮箱")
    search_parser.add_argument("--date-from", help="开始日期 YYYY-MM-DD")
    search_parser.add_argument("--date-to", help="结束日期 YYYY-MM-DD")
    search_parser.add_argument("--limit", type=int, default=50, help="结果数量")
    search_parser.add_argument("--unread-only", action="store_true", help="仅未读")
    search_parser.add_argument("--live", action="store_true", help="强制走 IMAP")
    search_parser.add_argument("--json", action="store_true", help="JSON 输出")

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

    # sync control
    sync_parser = subparsers.add_parser("sync", help="同步控制")
    sync_parser.add_argument("action", choices=["start", "stop", "status", "force"], help="操作")
    sync_parser.add_argument("--account-id", help="账户 ID/邮箱（force 可用）")
    sync_parser.add_argument("--full", action="store_true", help="全量同步")
    sync_parser.add_argument("--json", action="store_true", help="JSON 输出")

    # health
    health_parser = subparsers.add_parser("health", help="同步健康状态")
    health_parser.add_argument("--json", action="store_true", help="JSON 输出")

    # version
    version_parser = subparsers.add_parser("version", help="版本信息")
    version_parser.add_argument("--json", action="store_true", help="JSON 输出")

    # db ops
    db_parser = subparsers.add_parser("db", help="数据库维护")
    db_sub = db_parser.add_subparsers(dest="db_cmd", required=True)
    db_sub.add_parser("checkpoint", help="WAL checkpoint + VACUUM")
    db_sub.add_parser("clear", help="备份后清空本地 DB (需停服务)")
    db_sub.add_parser("size", help="查看 DB/WAL 大小")

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
            offset=args.offset,
            use_cache=not args.live,
        )
        return _handle_output(result, args.json, _print_emails)

    if args.command == "search":
        result = client.search_emails(
            query=args.query,
            account_id=args.account_id,
            date_from=args.date_from,
            date_to=args.date_to,
            limit=args.limit,
            unread_only=args.unread_only,
        )
        return _handle_output(result, args.json, _print_emails)

    if args.command == "show-email":
        result = client.get_email_detail(
            args.email_id,
            folder=args.folder,
            account_id=args.account_id,
        )
        return _handle_output(result, args.json, _print_email_detail)

    if args.command == "sync":
        return _handle_output(
            _sync_action(args),
            args.json,
            _print_generic,
        )

    if args.command == "health":
        return _handle_output(_sync_health(), args.json, _print_generic)

    if args.command == "version":
        return _handle_output(_version(), args.json, _print_generic)

    if args.command == "db":
        return _handle_output(_db_action(args.db_cmd), False, _print_generic)

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


def _print_generic(result: Dict[str, Any]) -> None:
    """通用打印：键值对或列表"""
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _sync_action(args) -> Dict[str, Any]:
    """同步控制操作"""
    try:
        scheduler = get_scheduler()
        action = args.action
        if action == "start":
            scheduler.start_scheduler()
            return {"success": True, "message": "sync started"}
        if action == "stop":
            scheduler.stop_scheduler()
            return {"success": True, "message": "sync stopped"}
        if action == "status":
            status = scheduler.get_sync_status()
            status["success"] = True
            return status
        if action == "force":
            if args.account_id:
                from src.operations.email_sync import EmailSyncManager
                mgr = EmailSyncManager()
                res = mgr.sync_single_account(args.account_id, full_sync=args.full)
                mgr.close()
                res["success"] = res.get("success", True)
                return res
            res = scheduler.force_sync(args.full)
            res["success"] = res.get("success", True)
            return res
        return {"success": False, "error": f"未知同步操作: {action}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _sync_health() -> Dict[str, Any]:
    try:
        monitor = get_health_monitor()
        summary = monitor.get_overall_health()
        summary["success"] = True
        return summary
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _version() -> Dict[str, Any]:
    try:
        git_hash = ""
        repo_root = Path(__file__).resolve().parents[2]
        try:
            git_hash = (
                subprocess.check_output(
                    ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            git_hash = "unknown"
        return {"success": True, "version": __version__, "git": git_hash}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _db_action(action: str) -> Dict[str, Any]:
    db_path = Path("data/email_sync.db")
    wal_path = Path("data/email_sync.db-wal")
    shm_path = Path("data/email_sync.db-shm")
    try:
        if action == "size":
            def _size(p: Path) -> int:
                return p.stat().st_size if p.exists() else 0
            return {
                "success": True,
                "db_bytes": _size(db_path),
                "wal_bytes": _size(wal_path),
                "shm_bytes": _size(shm_path),
            }
        if action == "checkpoint":
            if not db_path.exists():
                return {"success": False, "error": "db file not found"}
            subprocess.run(
                ["sqlite3", str(db_path), "PRAGMA wal_checkpoint(TRUNCATE); VACUUM;"],
                check=True,
            )
            return {"success": True, "message": "checkpoint + vacuum done"}
        if action == "clear":
            backup_dir = Path("data/db_backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            import shutil, datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            for f in [db_path, wal_path, shm_path]:
                if f.exists():
                    shutil.move(str(f), backup_dir / f"{f.name}.{ts}.bak")
            return {"success": True, "message": "db cleared (backed up)"}
        return {"success": False, "error": f"未知 db 操作: {action}"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


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
