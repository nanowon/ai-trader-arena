"""Phase 3: factor_snapshots 저장 테스트.

(a) BUY 발생 시 factor_snapshots에 row 생성, factor_json이 valid JSON이고 quality_pct 키 포함
(b) SELL ticker가 core_df에 없을 때 skip (예외 없음)
(c) 같은 날 재실행 시 멱등 (INSERT OR IGNORE, row 중복 없음)
(d) core_df가 비었을 때 no-op
"""
from __future__ import annotations

import json
import sqlite3

import pandas as pd
import pytest

from arena.db.migrations import run_migrations
from arena.db.repositories import insert_factor_snapshots_bulk
from arena.engine.orchestrator import _build_factor_rows


@pytest.fixture()
def mem_conn():
	"""in-memory SQLite 연결 (마이그레이션 완료)."""
	conn = sqlite3.connect(":memory:")
	conn.row_factory = sqlite3.Row
	run_migrations(conn)
	yield conn
	conn.close()


def _make_core_df(tickers: list[str], quality_pct: float = 0.9) -> pd.DataFrame:
	return pd.DataFrame([
		{
			"ticker": t,
			"quality_pct": quality_pct,
			"hint_tag": "",
			"entry_price": 50.0,
			"target_price": 60.0,
			"stop_price": 40.0,
		}
		for t in tickers
	])


# ── (a) BUY 발생 시 row 생성 ─────────────────────────────────────────────────

def test_factor_snapshot_row_created_on_buy(mem_conn):
	date_str = "2026-04-24"
	core_df = _make_core_df(["AAA", "BBB"])
	traded = {"AAA"}

	rows = _build_factor_rows(core_df, traded)
	assert len(rows) == 1
	ticker, factor_json_str = rows[0]
	assert ticker == "AAA"

	parsed = json.loads(factor_json_str)
	assert "quality_pct" in parsed
	assert parsed["quality_pct"] == pytest.approx(0.9)

	insert_factor_snapshots_bulk(mem_conn, date_str, rows)
	mem_conn.commit()

	db_rows = mem_conn.execute(
		"SELECT * FROM factor_snapshots WHERE date=? AND ticker=?",
		(date_str, "AAA"),
	).fetchall()
	assert len(db_rows) == 1
	stored = json.loads(db_rows[0]["factor_json"])
	assert "quality_pct" in stored


# ── (b) SELL ticker가 core_df에 없을 때 skip ─────────────────────────────────

def test_factor_snapshot_skips_ticker_not_in_core_df():
	core_df = _make_core_df(["AAA"])
	traded = {"ZZZ"}  # ZZZ는 core_df에 없음

	rows = _build_factor_rows(core_df, traded)
	# ZZZ 없으므로 빈 리스트 반환, 예외 없음
	assert rows == []


# ── (c) 같은 날 재실행 시 멱등 ────────────────────────────────────────────────

def test_factor_snapshot_idempotent_on_rerun(mem_conn):
	date_str = "2026-04-24"
	core_df = _make_core_df(["AAA"])
	traded = {"AAA"}

	rows = _build_factor_rows(core_df, traded)

	# 첫 번째 삽입
	insert_factor_snapshots_bulk(mem_conn, date_str, rows)
	mem_conn.commit()

	# 두 번째 삽입 (재실행 시뮬레이션)
	insert_factor_snapshots_bulk(mem_conn, date_str, rows)
	mem_conn.commit()

	count = mem_conn.execute(
		"SELECT COUNT(*) FROM factor_snapshots WHERE date=? AND ticker=?",
		(date_str, "AAA"),
	).fetchone()[0]
	assert count == 1  # 중복 없음


# ── (d) core_df가 비었을 때 no-op ─────────────────────────────────────────────

def test_factor_snapshot_noop_when_core_df_empty(mem_conn):
	date_str = "2026-04-24"
	empty_df = pd.DataFrame()
	traded = {"AAA"}

	rows = _build_factor_rows(empty_df, traded)
	assert rows == []

	# 빈 rows로 bulk insert → 예외 없음
	insert_factor_snapshots_bulk(mem_conn, date_str, rows)
	mem_conn.commit()

	count = mem_conn.execute(
		"SELECT COUNT(*) FROM factor_snapshots",
	).fetchone()[0]
	assert count == 0
