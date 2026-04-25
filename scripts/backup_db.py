"""Arena DB 백업 CLI.

sqlite3 .backup() API로 data/arena.db 스냅샷 생성.
보관 정책: BACKUP_RETENTION 개수 초과 시 오래된 것부터 삭제.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
	from arena.config import BACKUP_DIR, BACKUP_RETENTION, DB_PATH

	parser = argparse.ArgumentParser(
		prog="backup-db",
		description="Create a sqlite3 backup snapshot of arena.db",
	)
	parser.add_argument("--db-path", type=str, default=None, help="Source DB path (default: config.DB_PATH)")
	parser.add_argument("--out-dir", type=str, default=None, help="Backup output directory (default: config.BACKUP_DIR)")
	parser.add_argument("--retention", type=int, default=None, help="Number of backups to keep (default: config.BACKUP_RETENTION)")
	args = parser.parse_args(argv)

	db_path = Path(args.db_path) if args.db_path else DB_PATH
	out_dir = Path(args.out_dir) if args.out_dir else BACKUP_DIR
	retention = args.retention if args.retention is not None else BACKUP_RETENTION

	if not db_path.exists():
		print(f"backup_db: DB not found: {db_path}", file=sys.stderr)
		sys.exit(1)

	out_dir.mkdir(parents=True, exist_ok=True)

	today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
	backup_path = out_dir / f"arena_{today_str}.db"

	src_conn = sqlite3.connect(str(db_path))
	try:
		dst_conn = sqlite3.connect(str(backup_path))
		try:
			src_conn.backup(dst_conn)
		finally:
			dst_conn.close()
	finally:
		src_conn.close()

	# 보관 정책 적용 — 오래된 것부터 삭제
	existing = sorted(out_dir.glob("arena_*.db"))
	deleted = []
	while len(existing) > retention:
		oldest = existing.pop(0)
		oldest.unlink()
		deleted.append(str(oldest))

	result = {
		"backup_path": str(backup_path),
		"deleted": deleted,
		"retained": len(existing),
	}
	print(json.dumps(result, ensure_ascii=False, indent=2))
	return 0


if __name__ == "__main__":
	sys.exit(main())
