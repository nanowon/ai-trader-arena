"""포트폴리오 상태(DB) + 평가액 계산."""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, asdict, field

import pandas as pd

from arena import config
from arena.db.connection import get_connection
from arena.db.repositories import (
	load_positions,
	load_last_cash,
	replace_positions,
	upsert_daily_equity,
)

log = logging.getLogger(__name__)


@dataclass
class Position:
	ticker: str
	qty: int
	entry_price: float
	entry_date: str
	entry_target_price: float | None = None
	entry_stop_price: float | None = None
	entry_hint_tag: str = ""


@dataclass
class PortfolioState:
	agent: str
	cash: float
	last_updated: str
	positions: list[Position] = field(default_factory=list)

	def to_dict(self) -> dict:
		return {
			"agent": self.agent,
			"cash": float(self.cash),
			"last_updated": self.last_updated,
			"positions": [asdict(p) for p in self.positions],
		}

	@classmethod
	def from_dict(cls, d: dict) -> "PortfolioState":
		return cls(
			agent=d["agent"],
			cash=float(d.get("cash", 0.0)),
			last_updated=d.get("last_updated", ""),
			positions=[Position(**p) for p in d.get("positions", [])],
		)


def load_state(
	agent_name: str,
	conn: sqlite3.Connection | None = None,
	initial_capital: float | None = None,
) -> PortfolioState:
	"""DB에서 positions + cash 로드. conn 없으면 로컬 연결 사용."""
	if initial_capital is None:
		initial_capital = float(config.INITIAL_CAPITAL)

	_close_conn = False
	if conn is None:
		try:
			conn = get_connection()
			_close_conn = True
		except Exception as e:  # noqa: BLE001
			log.warning(f"load_state({agent_name}): DB connection failed: {e}. Returning fresh state.")
			return PortfolioState(
				agent=agent_name,
				cash=initial_capital,
				last_updated="",
				positions=[],
			)

	try:
		from arena.db.migrations import run_migrations
		run_migrations(conn)

		pos_rows = load_positions(conn, agent_name)
		positions = [
			Position(
				ticker=r["ticker"],
				qty=r["qty"],
				entry_price=float(r["entry_price"]),
				entry_date=r["entry_date"],
				entry_target_price=r["entry_target_price"],
				entry_stop_price=r["entry_stop_price"],
				entry_hint_tag=r["entry_hint_tag"] or "",
			)
			for r in pos_rows
		]
		cash = load_last_cash(conn, agent_name, initial_capital)
		return PortfolioState(
			agent=agent_name,
			cash=cash,
			last_updated="",
			positions=positions,
		)
	except Exception as e:  # noqa: BLE001
		log.warning(f"load_state({agent_name}) failed: {e}. Returning fresh state.")
		return PortfolioState(
			agent=agent_name,
			cash=initial_capital,
			last_updated="",
			positions=[],
		)
	finally:
		if _close_conn:
			try:
				conn.close()
			except Exception:  # noqa: BLE001
				pass


def save_state(
	state: PortfolioState,
	conn: sqlite3.Connection,
	today_iso: str,
	equity_value: float,
	total_value: float,
	num_positions: int,
) -> None:
	"""DB에 포지션 교체 + 일별 에쿼티 upsert."""
	replace_positions(conn, state.agent, state.positions)
	upsert_daily_equity(
		conn,
		today_iso,
		state.agent,
		state.cash,
		equity_value,
		total_value,
		num_positions,
	)


def evaluate(state: PortfolioState, current_closes: dict[str, float]) -> dict:
	equity_value = 0.0
	for p in state.positions:
		px = current_closes.get(p.ticker)
		if px is None or not (isinstance(px, (int, float)) and px > 0):
			log.warning(
				f"evaluate: missing close for {p.ticker} (agent={state.agent}); "
				f"falling back to entry_price {p.entry_price:.2f}"
			)
			px = p.entry_price
		equity_value += p.qty * float(px)

	total_value = float(state.cash) + float(equity_value)
	return {
		"equity_value": float(equity_value),
		"total_value": float(total_value),
		"cash": float(state.cash),
		"num_positions": len(state.positions),
	}


def fetch_current_closes(tickers: list[str]) -> dict[str, float]:
	"""yfinance 2일치 다운로드 후 각 ticker의 최신 종가. 실패 시 {}."""
	tickers = [t for t in dict.fromkeys(tickers) if t]
	if not tickers:
		return {}

	try:
		import yfinance as yf
	except Exception as e:  # noqa: BLE001
		log.warning(f"fetch_current_closes: yfinance import failed: {e}")
		return {}

	try:
		raw = yf.download(tickers, period="2d", auto_adjust=True, progress=False)
	except Exception as e:  # noqa: BLE001
		log.warning(f"fetch_current_closes: yfinance download failed: {e}")
		return {}

	if raw is None or raw.empty:
		log.warning("fetch_current_closes: empty frame")
		return {}

	if isinstance(raw.columns, pd.MultiIndex):
		if "Close" not in raw.columns.get_level_values(0):
			return {}
		closes = raw["Close"]
	else:
		if "Close" not in raw.columns:
			return {}
		only = tickers[0]
		closes = raw[["Close"]].rename(columns={"Close": only})

	out: dict[str, float] = {}
	last = closes.ffill().iloc[-1]
	for t in tickers:
		if t in last.index:
			v = last[t]
			if pd.notna(v) and float(v) > 0:
				out[t] = float(v)
	return out
