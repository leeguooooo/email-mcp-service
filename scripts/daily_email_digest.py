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


def _resolve_config_path(argv: list[str]) -> str | None:
    if "--config" in argv:
        idx = argv.index("--config")
        if idx + 1 < len(argv):
            return argv[idx + 1]
    return None


def run_once(config_path: str | None) -> None:
    service = DailyDigestService(config_path=config_path)
    result = service.run()
    print(json.dumps(result, indent=2, ensure_ascii=False))


def run_daemon(config_path: str | None) -> None:
    config_manager = DigestConfigManager(config_path)
    service = DailyDigestService(config_manager=config_manager)
    schedule_cfg = config_manager.config.get("schedule", {})

    if not schedule_cfg.get("enabled", True):
        print(json.dumps({"message": "Scheduler disabled in config"}, ensure_ascii=False))
        return

    run_time = schedule_cfg.get("time", "08:30")
    try:
        schedule.every().day.at(run_time).do(service.run)
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
                "run": "python scripts/daily_email_digest.py run",
                "daemon": "python scripts/daily_email_digest.py daemon",
                "config": "python scripts/daily_email_digest.py config"
            }
        }, indent=2))
        sys.exit(1)

    command = sys.argv[1]
    config_path = _resolve_config_path(sys.argv)

    if command == "run":
        run_once(config_path)
    elif command == "daemon":
        run_daemon(config_path)
    elif command == "config":
        config_manager = DigestConfigManager(config_path)
        print(json.dumps(config_manager.config, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"error": f"Unknown command: {command}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
