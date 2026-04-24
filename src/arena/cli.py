"""arena CLI entrypoint (Phase 0 skeleton).

하위 명령만 정의되어 있으며 실제 로직은 이후 Phase에서 구현됩니다.
"""
from __future__ import annotations

import argparse
import logging
import sys

logger = logging.getLogger("arena.cli")

_PHASE0_MSG = "Not implemented in Phase 0"


def _not_implemented(name: str) -> int:
    logger.info("[%s] %s", name, _PHASE0_MSG)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="arena",
        description="AI Trader Arena CLI",
    )
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser("init-db", help="Initialize the arena SQLite database")
    sub.add_parser("migrate", help="Run DB migrations / legacy imports")
    sub.add_parser("run-daily", help="Run the daily orchestrator (market close cycle)")
    sub.add_parser("build-web", help="Build the static dashboard site")
    sub.add_parser("notify", help="Send Discord / email notifications")
    sub.add_parser("backfill", help="Backfill historical prices / snapshots")

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return _not_implemented(args.command)


if __name__ == "__main__":
    sys.exit(main())
