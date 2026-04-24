"""Arena DB 백업 CLI (Phase 2에서 구현).

# TODO(Phase 2): sqlite3 .backup API 로 data/arena.db 스냅샷 생성.
"""
from __future__ import annotations

import sys


def main() -> int:
    raise NotImplementedError("Phase 2")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except NotImplementedError as exc:
        print(f"backup_db: {exc}", file=sys.stderr)
        sys.exit(1)
