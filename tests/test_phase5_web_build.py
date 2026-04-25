"""Phase 5-A: build_site 통합 테스트."""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

from arena.db.migrations import run_migrations
from arena.db.repositories import (
	insert_factor_snapshots_bulk,
	insert_trades,
	upsert_agent,
	upsert_benchmark,
	upsert_daily_equity,
)


# ── 픽스처 ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def seeded_db(tmp_path) -> Path:
	"""마이그레이션 + 소량 시드 데이터가 포함된 SQLite DB 파일 경로 반환."""
	db_file = tmp_path / "arena_test.db"
	conn = sqlite3.connect(str(db_file))
	conn.row_factory = sqlite3.Row
	run_migrations(conn)

	upsert_agent(conn, "aggressive", "aggressive")
	upsert_agent(conn, "etf_only", "etf_only")

	upsert_daily_equity(conn, "2026-04-24", "aggressive", 90000.0, 10000.0, 100000.0, 1)
	upsert_daily_equity(conn, "2026-04-25", "aggressive", 88000.0, 14000.0, 102000.0, 1)
	upsert_daily_equity(conn, "2026-04-24", "etf_only", 70000.0, 30000.0, 100000.0, 3)
	upsert_daily_equity(conn, "2026-04-25", "etf_only", 68000.0, 35000.0, 103000.0, 3)

	upsert_benchmark(conn, "2026-04-24", "SPY", 500.0)

	# 포지션이 있어야 trades 삽입 가능하지만 insert_trades는 직접 SQL로 삽입
	conn.execute(
		"""
		INSERT OR IGNORE INTO positions (agent, ticker, qty, entry_price, entry_date)
		VALUES (?, ?, ?, ?, ?)
		""",
		("etf_only", "XLK", 100, 200.0, "2026-04-24"),
	)

	# 거래 내역 직접 삽입 (insert_trades는 Order 객체 필요)
	conn.execute(
		"""
		INSERT INTO trades (date, agent, ticker, side, qty, price, reason)
		VALUES (?, ?, ?, ?, ?, ?, ?)
		""",
		("2026-04-25", "aggressive", "AAPL", "BUY", 10, 150.0, None),
	)

	insert_factor_snapshots_bulk(
		conn,
		"2026-04-25",
		[("XLK", '{"quality_pct": 0.85, "hint_tag": ""}')],
	)

	conn.commit()
	conn.close()
	return db_file


@pytest.fixture()
def empty_db(tmp_path) -> Path:
	"""마이그레이션만 완료된 빈 DB 파일 경로 반환."""
	db_file = tmp_path / "arena_empty.db"
	conn = sqlite3.connect(str(db_file))
	conn.row_factory = sqlite3.Row
	run_migrations(conn)
	conn.commit()
	conn.close()
	return db_file


# ── test1: index.html 생성 확인 ─────────────────────────────────────────────

def test_build_site_creates_index_html(seeded_db, tmp_path):
	"""build_site 호출 후 index.html이 생성된다."""
	from arena.web.builder import build_site

	out_dir = tmp_path / "site"
	result = build_site(db_path=seeded_db, output_dir=out_dir)

	assert result.exists(), "index.html이 생성되어야 한다"
	assert result.name == "index.html"
	assert result.parent == out_dir


# ── test2: chart-1 ~ chart-9 div id 존재 확인 ────────────────────────────────

def test_build_site_contains_all_chart_divs(seeded_db, tmp_path):
	"""index.html에 chart-1 ~ chart-9 div id가 모두 존재한다."""
	from arena.web.builder import build_site

	out_dir = tmp_path / "site"
	result = build_site(db_path=seeded_db, output_dir=out_dir)
	html = result.read_text(encoding="utf-8")

	for n in range(1, 10):
		assert f'id="chart-{n}"' in html, f"chart-{n} div가 없다"


# ── test3: <script> 내 DATA JSON 파싱 가능, 9개 키 존재 ──────────────────────

def test_build_site_data_json_parseable(seeded_db, tmp_path):
	"""DATA JSON이 파싱 가능하고 chart1~chart9 + generated_at 키가 있다."""
	from arena.web.builder import build_site

	out_dir = tmp_path / "site"
	result = build_site(db_path=seeded_db, output_dir=out_dir)
	html = result.read_text(encoding="utf-8")

	# DATA = {...}; 패턴에서 JSON 추출
	match = re.search(r'const DATA\s*=\s*(\{.*?\});\s*\n', html, re.DOTALL)
	assert match, "DATA JSON을 찾을 수 없다"

	data = json.loads(match.group(1))
	for n in range(1, 10):
		assert f"chart{n}" in data, f"chart{n} 키가 없다"
	assert "generated_at" in data


# ── test4: 빈 DB로 build_site 호출 → 에러 없이 완료 ──────────────────────────

def test_build_site_empty_db_no_error(empty_db, tmp_path):
	"""빈 DB로 build_site를 호출해도 예외 없이 index.html이 생성된다."""
	from arena.web.builder import build_site

	out_dir = tmp_path / "site_empty"
	result = build_site(db_path=empty_db, output_dir=out_dir)

	assert result.exists()
	html = result.read_text(encoding="utf-8")
	assert "chart-1" in html


# ── test5: chart9 키 및 필수 하위 키 존재 확인 ───────────────────────────────

def test_chart9_keys(seeded_db, tmp_path):
	"""build_site 후 DATA JSON의 chart9에 today/rankings/spy_return_pct/note 키가 있다."""
	from arena.web.builder import build_site

	out_dir = tmp_path / "site_chart9"
	result = build_site(db_path=seeded_db, output_dir=out_dir)
	html = result.read_text(encoding="utf-8")

	match = re.search(r'const DATA\s*=\s*(\{.*?\});\s*\n', html, re.DOTALL)
	assert match, "DATA JSON을 찾을 수 없다"

	data = json.loads(match.group(1))
	c9 = data.get("chart9")
	assert c9 is not None, "chart9 키가 없다"
	for key in ("today", "rankings", "spy_return_pct", "note"):
		assert key in c9, f"chart9.{key} 키가 없다"


# ── test6: _drawdowns 빈 리스트 입력 → 빈 리스트 반환 ───────────────────────

def test_drawdowns_empty():
	"""_drawdowns([]) 호출 시 빈 리스트를 반환한다."""
	from arena.web.builder import _drawdowns

	assert _drawdowns([]) == []


# ── test7: build_site 후 static/style.css 파일 존재 확인 ────────────────────

def test_static_css_copied(seeded_db, tmp_path):
	"""build_site 후 output_dir/static/style.css 파일이 존재한다."""
	from arena.web.builder import build_site

	out_dir = tmp_path / "site_css"
	build_site(db_path=seeded_db, output_dir=out_dir)

	css_path = out_dir / "static" / "style.css"
	assert css_path.exists(), "static/style.css 파일이 복사되어야 한다"
