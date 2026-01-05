#!/usr/bin/env python3
"""
Daily email digest CLI wrapper.
"""
import json
import sys
import time
from pathlib import Path

try:
    import schedule
except ImportError as exc:
    raise ImportError("Missing schedule dependency. Install with: pip install schedule") from exc

repo_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo_root))

from src.config.digest_config import DigestConfigManager
from src.services.daily_digest_service import DailyDigestService


def _resolve_arg_value(argv: list[str], name: str) -> str | None:
    if name in argv:
        idx = argv.index(name)
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def _flag_present(argv: list[str], name: str) -> bool:
    return name in argv


def run_once(
    config_path: str | None,
    dry_run: bool,
    debug_ai: bool,
    debug_path: str | None
) -> None:
    service = DailyDigestService(config_path=config_path)
    debug_cfg = {}
    if debug_ai:
        debug_cfg["dump_ai_input"] = True
        debug_cfg["dump_ai_output"] = True
    if debug_path:
        debug_cfg["path"] = debug_path
    result = service.run(dry_run=dry_run, debug=debug_cfg or None)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_daemon(
    config_path: str | None,
    dry_run: bool,
    debug_ai: bool,
    debug_path: str | None
) -> None:
    config_manager = DigestConfigManager(config_path)
    service = DailyDigestService(config_manager=config_manager)
    debug_cfg = {}
    if debug_ai:
        debug_cfg["dump_ai_input"] = True
        debug_cfg["dump_ai_output"] = True
    if debug_path:
        debug_cfg["path"] = debug_path
    schedule_cfg = config_manager.config.get("schedule", {})

    if not schedule_cfg.get("enabled", True):
        print(json.dumps({"message": "Scheduler disabled in config"}, ensure_ascii=False))
        return

    run_time = schedule_cfg.get("time", "08:30")
    try:
        schedule.every().day.at(run_time).do(
            service.run,
            dry_run=dry_run,
            debug=debug_cfg or None
        )
    except schedule.ScheduleValueError as exc:
        print(json.dumps({"error": f"Invalid schedule time format: {exc}"}, ensure_ascii=False))
        return

    print(json.dumps({"message": f"Daily digest scheduled at {run_time}"}, ensure_ascii=False))
    while True:
        schedule.run_pending()
        time.sleep(30)


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: python daily_email_digest.py <command>",
            "commands": {
                "run": "Run once",
                "daemon": "Run scheduler loop",
                "config": "Print current configuration"
            },
            "examples": {
                "run": "python scripts/daily_email_digest.py run [--dry-run] [--debug-ai] [--debug-path <path>]",
                "daemon": "python scripts/daily_email_digest.py daemon [--debug-ai] [--debug-path <path>]",
                "config": "python scripts/daily_email_digest.py config"
            },
            "flags": {
                "--dry-run": "Generate digest but do not send notifications",
                "--debug-ai": "Dump AI inputs/outputs to debug log",
                "--debug-path": "Override debug log path"
            }
        }, indent=2))
        sys.exit(1)

    command = sys.argv[1]
    config_path = _resolve_arg_value(sys.argv, "--config")
    debug_path = _resolve_arg_value(sys.argv, "--debug-path")
    dry_run = _flag_present(sys.argv, "--dry-run")
    debug_ai = _flag_present(sys.argv, "--debug-ai")

    if command == "run":
        run_once(config_path, dry_run=dry_run, debug_ai=debug_ai, debug_path=debug_path)
    elif command == "daemon":
        run_daemon(config_path, dry_run=dry_run, debug_ai=debug_ai, debug_path=debug_path)
    elif command == "config":
        config_manager = DigestConfigManager(config_path)
        print(json.dumps(config_manager.config, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
