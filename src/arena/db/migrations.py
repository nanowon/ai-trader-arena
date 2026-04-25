"""DB 마이그레이션 — schema_version 기반 멱등 적용."""
from __future__ import annotations

import sqlite3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
	version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS agents (
	name          TEXT PRIMARY KEY,
	strategy_type TEXT,
	created_at    TEXT
);

CREATE TABLE IF NOT EXISTS positions (
	agent            TEXT REFERENCES agents(name),
	ticker           TEXT,
	qty              REAL,
	entry_price      REAL,
	entry_date       TEXT,
	entry_target_price REAL,
	entry_stop_price   REAL,
	entry_hint_tag     TEXT,
	PRIMARY KEY (agent, ticker)
);

CREATE TABLE IF NOT EXISTS trades (
	id           INTEGER PRIMARY KEY AUTOINCREMENT,
	date         TEXT,
	agent        TEXT REFERENCES agents(name),
	ticker       TEXT,
	side         TEXT CHECK(side IN ('BUY', 'SELL')),
	qty          REAL,
	price        REAL,
	reason       TEXT,
	hint_tag     TEXT,
	target_price REAL,
	stop_price   REAL,
	quality_pct  REAL
);

CREATE INDEX IF NOT EXISTS idx_trades_agent_date  ON trades (agent, date);
CREATE INDEX IF NOT EXISTS idx_trades_ticker_date ON trades (ticker, date);

CREATE TABLE IF NOT EXISTS factor_snapshots (
	date        TEXT,
	ticker      TEXT,
	factor_json TEXT,
	PRIMARY KEY (date, ticker)
);

CREATE TABLE IF NOT EXISTS daily_equity (
	date          TEXT,
	agent         TEXT REFERENCES agents(name),
	cash          REAL,
	equity_value  REAL,
	total_value   REAL,
	num_positions INTEGER,
	PRIMARY KEY (date, agent)
);

CREATE TABLE IF NOT EXISTS benchmarks (
	date   TEXT,
	ticker TEXT,
	close  REAL,
	PRIMARY KEY (date, ticker)
);
"""

_VERSION_1_SQL = SCHEMA_SQL

_VERSION_2_SQL = """
CREATE TABLE IF NOT EXISTS experiments (
	exp_id              TEXT PRIMARY KEY,
	project             TEXT NOT NULL,
	title               TEXT,
	registered_at       TEXT NOT NULL,
	completed_at        TEXT,
	git_sha             TEXT,
	hypothesis          TEXT,
	config_json         TEXT,
	sharpe              REAL,
	sharpe_ci_low       REAL,
	sharpe_ci_high      REAL,
	p_value             REAL,
	mdd                 REAL,
	ann_return          REAL,
	win_rate            REAL,
	turnover            REAL,
	status              TEXT CHECK(status IN ('registered', 'running', 'pass', 'fail', 'abandoned')),
	reviewer_verdict    TEXT,
	notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_experiments_project_status ON experiments (project, status);
CREATE INDEX IF NOT EXISTS idx_experiments_registered_at ON experiments (registered_at);
"""


def run_migrations(conn: sqlite3.Connection) -> None:
	"""schema_version을 읽고 필요한 마이그레이션을 멱등으로 적용한다."""
	conn.execute(
		"CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)"
	)
	conn.commit()

	row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
	current_version: int = row[0] if row and row[0] is not None else 0

	if current_version < 1:
		conn.executescript(_VERSION_1_SQL)
		conn.execute(
			"INSERT OR REPLACE INTO schema_version (version) VALUES (1)"
		)
		conn.commit()

	if current_version < 2:
		conn.executescript(_VERSION_2_SQL)
		conn.execute(
			"INSERT OR REPLACE INTO schema_version (version) VALUES (2)"
		)
		conn.commit()
