"""Legacy 데이터 마이그레이션 CLI (Phase 2에서 구현).

# TODO(Phase 2): ai-stock-engine raw CSV -> arena.db 로 이관.
"""
from __future__ import annotations

import sys


def main() -> int:
    raise NotImplementedError("Phase 2")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except NotImplementedError as exc:
        print(f"migrate_legacy: {exc}", file=sys.stderr)
        sys.exit(1)
