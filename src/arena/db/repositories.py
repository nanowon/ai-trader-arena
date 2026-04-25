"""도메인별 레포지토리 — agents / positions / trades / daily_equity / benchmarks / factor_snapshots."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone


def upsert_agent(conn: sqlite3.Connection, name: str, strategy_type: str) -> None:
	conn.execute(
		"""
		INSERT INTO agents (name, strategy_type, created_at)
		VALUES (?, ?, ?)
		ON CONFLICT(name) DO UPDATE SET strategy_type=excluded.strategy_type
		""",
		(name, strategy_type, datetime.now(timezone.utc).isoformat()),
	)


def replace_positions(conn: sqlite3.Connection, agent: str, positions: list) -> None:
	"""에이전트의 포지션 전체를 DELETE 후 INSERT로 교체한다."""
	conn.execute("DELETE FROM positions WHERE agent = ?", (agent,))
	conn.executemany(
		"""
		INSERT INTO positions
			(agent, ticker, qty, entry_price, entry_date,
			 entry_target_price, entry_stop_price, entry_hint_tag)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
		""",
		[
			(
				agent,
				p.ticker,
				p.qty,
				p.entry_price,
				p.entry_date,
				p.entry_target_price,
				p.entry_stop_price,
				p.entry_hint_tag,
			)
			for p in positions
		],
	)


def insert_trades(
	conn: sqlite3.Connection,
	date: str,
	agent: str,
	executed_sells: list,
	executed_buys: list,
) -> None:
	"""같은 날 재실행에 멱등하도록 먼저 삭제 후 삽입한다."""
	conn.execute(
		"DELETE FROM trades WHERE date = ? AND agent = ?",
		(date, agent),
	)

	rows = []
	for s in executed_sells:
		rows.append((
			date, agent, s.ticker, "SELL",
			s.qty, s.price,
			getattr(s, "reason", None),
			None,   # hint_tag — SellOrder에 없음
			None,   # target_price
			None,   # stop_price
			None,   # quality_pct
		))
	for b in executed_buys:
		rows.append((
			date, agent, b.ticker, "BUY",
			b.qty, b.price,
			None,   # reason
			getattr(b, "hint_tag", None),
			getattr(b, "target_price", None),
			getattr(b, "stop_price", None),
			getattr(b, "quality_pct", None),
		))

	if rows:
		conn.executemany(
			"""
			INSERT INTO trades
				(date, agent, ticker, side, qty, price,
				 reason, hint_tag, target_price, stop_price, quality_pct)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
			""",
			rows,
		)


def upsert_daily_equity(
	conn: sqlite3.Connection,
	date: str,
	agent: str,
	cash: float,
	equity_value: float,
	total_value: float,
	num_positions: int,
) -> None:
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
		(date, agent, cash, equity_value, total_value, num_positions),
	)


def upsert_benchmark(
	conn: sqlite3.Connection,
	date: str,
	ticker: str,
	close: float,
) -> None:
	conn.execute(
		"""
		INSERT INTO benchmarks (date, ticker, close)
		VALUES (?, ?, ?)
		ON CONFLICT(date, ticker) DO UPDATE SET close=excluded.close
		""",
		(date, ticker, close),
	)


def insert_factor_snapshot(
	conn: sqlite3.Connection,
	date: str,
	ticker: str,
	factor_json: str,
) -> None:
	"""Phase 3용 factor_snapshots 단건 삽입 — 충돌 시 무시."""
	conn.execute(
		"""
		INSERT OR IGNORE INTO factor_snapshots (date, ticker, factor_json)
		VALUES (?, ?, ?)
		""",
		(date, ticker, factor_json),
	)


def insert_factor_snapshots_bulk(
	conn: sqlite3.Connection,
	date: str,
	items: list[tuple[str, str]],
) -> None:
	"""Phase 3용 factor_snapshots 벌크 삽입 — 충돌 시 무시.

	Args:
		items: [(ticker, factor_json_str), ...]
	"""
	conn.executemany(
		"INSERT OR IGNORE INTO factor_snapshots(date, ticker, factor_json) VALUES (?,?,?)",
		[(date, ticker, factor_json) for ticker, factor_json in items],
	)


def load_positions(conn: sqlite3.Connection, agent_name: str) -> list[dict]:
	"""positions 테이블에서 agent의 현재 포지션 로드. 없으면 빈 리스트."""
	rows = conn.execute(
		"""
		SELECT ticker, qty, entry_price, entry_date,
		       entry_target_price, entry_stop_price, entry_hint_tag
		FROM positions
		WHERE agent = ?
		""",
		(agent_name,),
	).fetchall()
	return [dict(r) for r in rows]


def load_last_cash(
	conn: sqlite3.Connection,
	agent_name: str,
	initial_capital: float,
) -> float:
	"""daily_equity에서 agent의 최신 cash 조회. 없으면 initial_capital 반환."""
	row = conn.execute(
		"""
		SELECT cash FROM daily_equity
		WHERE agent = ?
		ORDER BY date DESC
		LIMIT 1
		""",
		(agent_name,),
	).fetchone()
	return float(row["cash"]) if row is not None else initial_capital


def load_equity_history(
	conn: sqlite3.Connection,
	start_date: str,
	end_date: str,
) -> list[dict]:
	"""weekly_review용 일별 에쿼티 + SPY 종가 조회."""
	rows = conn.execute(
		"""
		SELECT de.date, de.agent, de.cash, de.equity_value,
		       de.total_value, de.num_positions,
		       b.close AS spy_close
		FROM daily_equity de
		LEFT JOIN benchmarks b
			ON de.date = b.date AND b.ticker = 'SPY'
		WHERE de.date BETWEEN ? AND ?
		ORDER BY de.date, de.agent
		""",
		(start_date, end_date),
	).fetchall()
	return [dict(r) for r in rows]


def load_latest_equity_per_agent(conn: sqlite3.Connection) -> list[dict]:
	"""daily_equity에서 가장 최근 날짜의 에이전트별 스냅샷 조회."""
	rows = conn.execute(
		"""
		SELECT date, agent, cash, equity_value, total_value, num_positions
		FROM daily_equity
		WHERE date = (SELECT MAX(date) FROM daily_equity)
		ORDER BY agent
		"""
	).fetchall()
	return [dict(r) for r in rows]


def load_recent_trades(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
	"""trades 테이블에서 최근 거래 내역 조회."""
	rows = conn.execute(
		"""
		SELECT id, date, agent, ticker, side, qty, price, reason,
		       hint_tag, target_price, stop_price, quality_pct
		FROM trades
		ORDER BY date DESC, id DESC
		LIMIT ?
		""",
		(limit,),
	).fetchall()
	return [dict(r) for r in rows]


def load_latest_factor_snapshots(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
	"""factor_snapshots에서 가장 최근 날짜 데이터 조회. factor_json을 dict로 파싱."""
	rows = conn.execute(
		"""
		SELECT date, ticker, factor_json
		FROM factor_snapshots
		WHERE date = (SELECT MAX(date) FROM factor_snapshots)
		LIMIT ?
		""",
		(limit,),
	).fetchall()
	result = []
	for r in rows:
		row_dict = dict(r)
		try:
			parsed = json.loads(row_dict["factor_json"])
		except (json.JSONDecodeError, TypeError):
			parsed = {}
		row_dict.update(parsed)
		del row_dict["factor_json"]
		result.append(row_dict)
	return result


def load_all_positions(conn: sqlite3.Connection) -> list[dict]:
	"""positions 테이블의 전체 포지션 조회. est_value(qty*entry_price) 추가."""
	rows = conn.execute(
		"""
		SELECT agent, ticker, qty, entry_price, entry_date
		FROM positions
		ORDER BY agent, ticker
		"""
	).fetchall()
	result = []
	for r in rows:
		row_dict = dict(r)
		qty = row_dict.get("qty") or 0.0
		entry_price = row_dict.get("entry_price") or 0.0
		row_dict["est_value"] = qty * entry_price  # 현재가 미반영
		result.append(row_dict)
	return result
