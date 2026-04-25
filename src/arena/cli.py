"""arena CLI entrypoint.

하위 명령:
  run-daily   — 오늘자 일일 리그 실행 (Phase 1부터 구현)
  init-db / migrate / build-web / notify / backfill — 이후 Phase 구현 예정
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

logger = logging.getLogger("arena.cli")

_PHASE_PENDING_MSG = "Not yet implemented"

# scripts/ 패키지가 설치 경로에 없으므로 프로젝트 루트를 sys.path에 추가
_PROJECT_ROOT = Path(__file__).parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _not_implemented(name: str) -> int:
    logger.info("[%s] %s", name, _PHASE_PENDING_MSG)
    return 0


def _cmd_run_daily(args: argparse.Namespace) -> int:
    from arena.engine.orchestrator import run_daily

    today: date | None
    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        today = datetime.now(timezone.utc).date()

    output_path = Path(args.output) if args.output else None
    result = run_daily(today=today, output_path=output_path)

    # stdout에도 간단 요약
    summary = {
        "date": result.get("date"),
        "snapshot_date": result.get("snapshot_date"),
        "skipped": result.get("skipped"),
        "agents": {
            name: {
                "total_value": ev.get("total_value"),
                "num_positions": ev.get("num_positions"),
            }
            for name, ev in (result.get("agents") or {}).items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _cmd_migrate_legacy(args: argparse.Namespace) -> int:
    import sys as _sys
    from pathlib import Path as _Path

    argv = []
    if args.db_path:
        argv += ["--db-path", args.db_path]
    if args.league_dir:
        argv += ["--league-dir", args.league_dir]
    if getattr(args, "dry_run", False):
        argv.append("--dry-run")

    from scripts.migrate_legacy import main as _migrate_main
    return _migrate_main(argv)


def _cmd_notify(args: argparse.Namespace) -> int:
    import json as _json
    from pathlib import Path as _Path

    result_path = getattr(args, "result", None)
    if result_path:
        try:
            result = _json.loads(_Path(result_path).read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("notify: result JSON 로드 실패: %s", e)
            return 1
    else:
        logger.error("notify: --result <json_path> 가 필요합니다.")
        return 1

    do_discord = getattr(args, "discord", False)
    do_email = getattr(args, "email", False)
    all_channels = getattr(args, "all_channels", False)
    # --all 또는 아무 플래그 없으면 모든 채널 전송
    if all_channels or (not do_discord and not do_email):
        do_discord = True
        do_email = True

    exit_code = 0

    if do_discord:
        from arena.notify.discord import send_daily_summary
        ok = send_daily_summary(result)
        if ok:
            logger.info("notify: Discord 전송 완료")
        else:
            logger.warning("notify: Discord 전송 실패 또는 스킵")
            exit_code = 1

    if do_email:
        from arena.notify.email_section import build_email_section, send_email
        html_body = build_email_section(result)
        date_str = result.get("date", "")
        subject = f"AI Trader Arena Daily — {date_str}" if date_str else "AI Trader Arena Daily"
        ok = send_email(html_body, subject=subject)
        if ok:
            logger.info("notify: 이메일 전송 완료")
        else:
            logger.warning("notify: 이메일 전송 실패 또는 스킵")
            exit_code = 1

    return exit_code


def _cmd_build_web(args: argparse.Namespace) -> int:
    from arena.web.builder import build_site

    db_path = Path(args.db_path) if args.db_path else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    out = build_site(db_path=db_path, output_dir=output_dir)
    print(str(out))
    return 0


def _cmd_backup(args: argparse.Namespace) -> int:
    argv = []
    if args.db_path:
        argv += ["--db-path", args.db_path]
    if args.out_dir:
        argv += ["--out-dir", args.out_dir]
    if args.retention is not None:
        argv += ["--retention", str(args.retention)]

    from scripts.backup_db import main as _backup_main
    return _backup_main(argv)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arena",
        description="AI Trader Arena CLI",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser("init-db", help="Initialize the arena SQLite database")
    sub.add_parser("migrate", help="Run DB migrations / legacy imports")

    p_run = sub.add_parser("run-daily", help="Run the daily orchestrator (market close cycle)")
    p_run.add_argument("--date", type=str, default=None, help="ISO date (default: today UTC)")
    p_run.add_argument("--output", type=str, default=None, help="Result JSON path")
    p_run.set_defaults(func=_cmd_run_daily)

    p_bw = sub.add_parser("build-web", help="Build the static dashboard site")
    p_bw.add_argument("--db-path", type=str, default=None, help="DB path (default: config.DB_PATH)")
    p_bw.add_argument("--output-dir", type=str, default=None, help="Output directory (default: docs/site)")
    p_bw.set_defaults(func=_cmd_build_web)
    p_notify = sub.add_parser("notify", help="Send Discord / email notifications")
    p_notify.add_argument("--result", type=str, default=None, help="Result JSON path")
    p_notify.add_argument("--discord", action="store_true", help="Send Discord notification")
    p_notify.add_argument("--email", action="store_true", help="Send email notification")
    p_notify.add_argument("--all", dest="all_channels", action="store_true", help="Send all (default)")
    p_notify.set_defaults(func=_cmd_notify)
    sub.add_parser("backfill", help="Backfill historical prices / snapshots")

    p_ml = sub.add_parser("migrate-legacy", help="Migrate legacy JSON/parquet data into arena.db")
    p_ml.add_argument("--db-path", type=str, default=None, help="DB path")
    p_ml.add_argument("--league-dir", type=str, default=None, help="League dir with *.json files")
    p_ml.add_argument("--dry-run", action="store_true", help="Parse only, no writes")
    p_ml.set_defaults(func=_cmd_migrate_legacy)

    p_bk = sub.add_parser("backup", help="Create a sqlite3 backup snapshot of arena.db")
    p_bk.add_argument("--db-path", type=str, default=None, help="Source DB path")
    p_bk.add_argument("--out-dir", type=str, default=None, help="Backup output directory")
    p_bk.add_argument("--retention", type=int, default=None, help="Number of backups to keep")
    p_bk.set_defaults(func=_cmd_backup)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    func = getattr(args, "func", None)
    if func is not None:
        return func(args)

    return _not_implemented(args.command)


if __name__ == "__main__":
    sys.exit(main())
