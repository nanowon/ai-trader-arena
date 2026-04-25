"""Legacy 데이터 마이그레이션 CLI.

JSON 포지션 파일과 history.parquet를 arena.db로 이관.
멱등 설계: 이미 이관된 데이터는 skip.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# parquet 컬럼명 정규화 매핑
COL_MAP: dict[str, str] = {
	"benchmark_close": "spy_close",
	"spy": "spy_close",
	"bench_close": "spy_close",
	"benchmark": "spy_close",
}


def migrate_positions_json(conn: sqlite3.Connection, league_dir: Path) -> dict:
	"""league_dir의 *.json 파일을 positions/agents/daily_equity 테이블로 이관."""
	migrated = []
	skipped = []
	errors = []

	for json_path in league_dir.glob("*.json"):
		if json_path.name == ".gitkeep":
			continue
		# legacy로 rename된 파일 skip
		if json_path.suffix == ".legacy":
			continue

		try:
			raw = json.loads(json_path.read_text(encoding="utf-8"))
		except Exception as exc:
			errors.append({"file": str(json_path), "error": str(exc)})
			continue

		agent_name = raw.get("agent") or raw.get("name", "")
		if not agent_name:
			errors.append({"file": str(json_path), "error": "no agent name"})
			continue

		# 멱등 체크
		row = conn.execute(
			"SELECT COUNT(*) FROM positions WHERE agent = ?", (agent_name,)
		).fetchone()
		if row[0] > 0:
			skipped.append(str(json_path))
			continue

		strategy_type = raw.get("strategy_type", "unknown")
		cash = float(raw.get("cash", 0.0))
		positions_raw: list[dict] = raw.get("positions", [])

		# agents 테이블 upsert
		conn.execute(
			"""
			INSERT INTO agents (name, strategy_type, created_at)
			VALUES (?, ?, ?)
			ON CONFLICT(name) DO UPDATE SET strategy_type=excluded.strategy_type
			""",
			(agent_name, strategy_type, "2000-01-01T00:00:00+00:00"),
		)

		# positions 이관
		conn.execute("DELETE FROM positions WHERE agent = ?", (agent_name,))
		for p in positions_raw:
			ticker = p.get("ticker", "")
			qty = float(p.get("qty") or p.get("shares") or 0)
			entry_price = float(p.get("entry_price") or p.get("price") or 0.0)
			entry_date = p.get("entry_date", "2000-01-01")
			entry_target_price = p.get("entry_target_price")
			entry_stop_price = p.get("entry_stop_price")
			entry_hint_tag = p.get("entry_hint_tag")
			conn.execute(
				"""
				INSERT INTO positions
					(agent, ticker, qty, entry_price, entry_date,
					 entry_target_price, entry_stop_price, entry_hint_tag)
				VALUES (?, ?, ?, ?, ?, ?, ?, ?)
				""",
				(agent_name, ticker, qty, entry_price, entry_date,
				 entry_target_price, entry_stop_price, entry_hint_tag),
			)

		# daily_equity 부트스트랩 (cash 1행)
		try:
			mtime_date = json_path.stat().st_mtime
			from datetime import datetime, timezone
			boot_date = datetime.fromtimestamp(mtime_date, tz=timezone.utc).strftime("%Y-%m-%d")
		except Exception:
			boot_date = "2000-01-01"

		conn.execute(
			"""
			INSERT INTO daily_equity
				(date, agent, cash, equity_value, total_value, num_positions)
			VALUES (?, ?, ?, ?, ?, ?)
			ON CONFLICT(date, agent) DO UPDATE SET
				cash=excluded.cash,
				equity_value=excluded.equity_value,
				total_value=excluded.total_value,
				num_positions=excluded.num_positions
			""",
			(boot_date, agent_name, cash, 0.0, cash, len(positions_raw)),
		)

		conn.commit()

		# 성공 시 rename
		json_path.rename(json_path.with_suffix(".json.legacy"))
		migrated.append(str(json_path))

	return {"migrated": migrated, "skipped": skipped, "errors": errors}


def migrate_history_parquet(conn: sqlite3.Connection, history_path: Path) -> dict:
	"""history.parquet를 daily_equity / benchmarks 테이블로 이관."""
	if not history_path.exists():
		return {"skipped": True, "reason": "file not found"}

	# 멱등 체크: legacy rename 파일이 있으면 이미 이관됨
	legacy_path = history_path.with_suffix(".parquet.legacy")
	if legacy_path.exists():
		return {"skipped": True, "reason": "already migrated (legacy file exists)"}

	try:
		import pandas as pd
	except ImportError:
		return {"skipped": True, "reason": "pandas not installed"}

	df = pd.read_parquet(history_path)
	# 컬럼명 소문자 정규화 + 매핑 적용
	df.columns = [COL_MAP.get(c.lower(), c.lower()) for c in df.columns]

	rows_equity = 0
	rows_bench = 0
	for _, row_data in df.iterrows():
		date_val = str(row_data.get("date", ""))
		agent_val = str(row_data.get("agent", ""))
		cash_val = float(row_data.get("cash", 0.0))
		equity_val = float(row_data.get("equity_value", 0.0))
		total_val = float(row_data.get("total_value", cash_val))
		num_pos = int(row_data.get("num_positions", 0))
		spy_close = row_data.get("spy_close")

		if date_val and agent_val:
			conn.execute(
				"""
				INSERT INTO daily_equity
					(date, agent, cash, equity_value, total_value, num_positions)
				VALUES (?, ?, ?, ?, ?, ?)
				ON CONFLICT(date, agent) DO UPDATE SET
					cash=excluded.cash,
					equity_value=excluded.equity_value,
					total_value=excluded.total_value,
					num_positions=excluded.num_positions
				""",
				(date_val, agent_val, cash_val, equity_val, total_val, num_pos),
			)
			rows_equity += 1

		if date_val and spy_close is not None:
			try:
				spy_val = float(spy_close)
				conn.execute(
					"""
					INSERT INTO benchmarks (date, ticker, close)
					VALUES (?, ?, ?)
					ON CONFLICT(date, ticker) DO UPDATE SET close=excluded.close
					""",
					(date_val, "SPY", spy_val),
				)
				rows_bench += 1
			except (TypeError, ValueError):
				pass

	conn.commit()

	legacy_path = history_path.with_suffix(".parquet.legacy")
	history_path.rename(legacy_path)

	return {"rows_equity": rows_equity, "rows_bench": rows_bench, "legacy": str(legacy_path)}


def main(argv: list[str] | None = None) -> int:
	from arena.config import DB_PATH, LEAGUE_DIR
	from arena.db.migrations import run_migrations

	parser = argparse.ArgumentParser(
		prog="migrate-legacy",
		description="Migrate legacy JSON/parquet data into arena.db",
	)
	parser.add_argument("--db-path", type=str, default=None, help="DB path (default: config.DB_PATH)")
	parser.add_argument("--league-dir", type=str, default=None, help="League dir with *.json files (default: config.LEAGUE_DIR)")
	parser.add_argument("--dry-run", action="store_true", help="Parse only, no writes")
	args = parser.parse_args(argv)

	db_path = Path(args.db_path) if args.db_path else DB_PATH
	league_dir = Path(args.league_dir) if args.league_dir else LEAGUE_DIR
	history_path = league_dir / "history.parquet"

	conn = sqlite3.connect(str(db_path))
	conn.row_factory = sqlite3.Row
	conn.execute("PRAGMA journal_mode=WAL")
	conn.execute("PRAGMA foreign_keys=ON")
	conn.execute("PRAGMA synchronous=NORMAL")

	try:
		run_migrations(conn)

		if args.dry_run:
			result = {"dry_run": True, "db_path": str(db_path), "league_dir": str(league_dir)}
			print(json.dumps(result, ensure_ascii=False, indent=2))
			return 0

		json_result = migrate_positions_json(conn, league_dir)
		parquet_result = migrate_history_parquet(conn, history_path)

		result = {
			"json": json_result,
			"parquet": parquet_result,
		}
		print(json.dumps(result, ensure_ascii=False, indent=2))
	finally:
		conn.close()

	return 0


if __name__ == "__main__":
	sys.exit(main())
