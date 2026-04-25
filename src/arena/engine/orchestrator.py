"""일일 리그 오케스트레이션.

실행 순서:
  1. 개장일 체크 → 비개장이면 skip
  2. raw URL에서 stage2 picks parquet 다운로드 → CORE 필터
  3. 각 에이전트 반복:
     - state 로드
     - sells 결정 → 집행
     - total_value 기반 buys 결정 → 집행
     - state 저장 (DB)
     - evaluate + commentary
  4. benchmarks upsert (SPY 종가)
  5. 일요일이면 weekly_review 빌드

최상위 try/except로 예외를 logging + skip 처리 (파이프라인 불변).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from arena import config
from arena.agents import build_default_agents
from arena.agents.base import AgentContext, AgentStrategy
from arena.data.fetcher import FetcherError, fetch_picks, filter_core
from arena.data.sector_rs import compute_sector_rs
from arena.db.connection import get_connection
from arena.db.migrations import run_migrations
from arena.db.repositories import (
	insert_factor_snapshots_bulk,
	insert_trades,
	upsert_agent,
	upsert_benchmark,
)
from arena.engine import calendar as cal
from arena.engine import commentary as comm
from arena.engine import orders as orders_mod
from arena.engine import portfolio as pf
from arena.engine import weekly_review

log = logging.getLogger(__name__)


def _build_factor_rows(
	core_df: "pd.DataFrame",
	traded_tickers: set[str],
) -> list[tuple[str, str]]:
	"""traded_tickers 중 core_df에 있는 ticker의 factor row를 JSON 문자열로 변환한다.

	NaN/NaT는 None으로 정규화 후 json.dumps.
	core_df에 없는 ticker는 warning 후 skip.

	Returns:
		[(ticker, factor_json_str), ...]
	"""
	import math

	if core_df is None or core_df.empty:
		return []

	# ticker를 인덱스로 세팅 (복사본, 원본 불변)
	if "ticker" in core_df.columns:
		indexed = core_df.set_index("ticker")
	else:
		indexed = core_df

	rows: list[tuple[str, str]] = []
	for ticker in traded_tickers:
		if ticker not in indexed.index:
			log.warning("factor_snapshots: ticker %s not in core_df, skip", ticker)
			continue
		row_series = indexed.loc[ticker]
		raw: dict = row_series.to_dict() if hasattr(row_series, "to_dict") else dict(row_series)
		# NaN/NaT → None 정규화
		normalized = {
			k: (None if (isinstance(v, float) and math.isnan(v)) else v)
			for k, v in raw.items()
		}
		factor_json_str = json.dumps(normalized, ensure_ascii=False, default=str)
		rows.append((ticker, factor_json_str))
	return rows


def _fetch_spy_close() -> float | None:
	try:
		closes = pf.fetch_current_closes(["SPY"])
		return closes.get("SPY")
	except Exception as e:  # noqa: BLE001
		log.warning(f"orchestrator: SPY fetch failed: {e}")
		return None


def _build_commentary(
	agent_name: str,
	exec_result: dict,
	eval_result: dict,
	today_iso: str,
) -> list[str]:
	lines: list[str] = []
	for s in exec_result.get("executed_sells", []):
		trig = {
			"stop": "sell_stop",
			"target": "sell_target",
			"volatility": "sell_volatility",
		}.get(s.reason, "sell_stop")
		ctx = {
			"ticker": s.ticker, "price": s.price, "date_iso": today_iso,
			"num_positions": eval_result["num_positions"],
			"cash": eval_result["cash"], "total_value": eval_result["total_value"],
			"return_pct": 0.0, "entry_price": 0.0,
			"target_price": 0.0, "stop_price": 0.0,
		}
		txt = comm.generate_commentary(agent_name, trig, ctx)
		if txt:
			lines.append(txt)

	for b in exec_result.get("executed_buys", []):
		ctx = {
			"ticker": b.ticker, "price": b.price,
			"target_price": b.target_price or 0.0,
			"stop_price": b.stop_price or 0.0,
			"quality_pct": b.quality_pct, "hint_tag": b.hint_tag or "",
			"num_positions": eval_result["num_positions"],
			"cash": eval_result["cash"], "total_value": eval_result["total_value"],
			"date_iso": today_iso,
		}
		txt = comm.generate_commentary(agent_name, "buy", ctx)
		if txt:
			lines.append(txt)

	if not exec_result.get("executed_sells") and not exec_result.get("executed_buys"):
		trig = "empty_day" if eval_result["num_positions"] == 0 else "hold"
		ctx = {
			"ticker": "",
			"num_positions": eval_result["num_positions"],
			"cash": eval_result["cash"], "total_value": eval_result["total_value"],
			"date_iso": today_iso,
		}
		txt = comm.generate_commentary(agent_name, trig, ctx)
		if txt:
			lines.append(txt)

	return lines


def run_daily(
	today: date | None = None,
	agents: list[AgentStrategy] | None = None,
	output_path: Path | None = None,
) -> dict:
	"""일일 실행. 결과 dict 반환.

	Args:
		today: 기준일 (None이면 UTC 오늘)
		agents: 기본 3종을 사용하려면 None
		output_path: 결과 JSON을 쓸 경로 (None이면 쓰지 않음)
	"""
	try:
		result = _run_inner(today, agents)
	except Exception as e:  # noqa: BLE001
		log.exception(f"orchestrator: unhandled error, skipping: {e}")
		result = {"skipped": "error", "message": str(e)}

	if output_path is not None:
		try:
			output_path.parent.mkdir(parents=True, exist_ok=True)
			output_path.write_text(
				json.dumps(_serialize(result), ensure_ascii=False, indent=2),
				encoding="utf-8",
			)
		except Exception as e:  # noqa: BLE001
			log.warning(f"orchestrator: output write failed: {e}")

	return result


def _serialize(obj):
	"""dataclass / 기타 객체를 JSON 직렬화 가능하게."""
	from dataclasses import asdict, is_dataclass
	if is_dataclass(obj):
		return asdict(obj)
	if isinstance(obj, dict):
		return {k: _serialize(v) for k, v in obj.items()}
	if isinstance(obj, (list, tuple)):
		return [_serialize(v) for v in obj]
	return obj


def _run_inner(today: date | None, agents: list[AgentStrategy] | None) -> dict:
	if today is None:
		today = datetime.now(timezone.utc).date()

	if not cal.is_market_open(today):
		log.info(f"orchestrator: market closed on {today}, skipping")
		return {"skipped": "market_closed", "date": today.isoformat()}

	today_iso = today.isoformat()

	try:
		fetch_res = fetch_picks(today=today)
	except FetcherError as e:
		log.warning(f"orchestrator: picks fetch failed: {e}")
		return {"skipped": "no_picks", "date": today_iso, "message": str(e)}

	core_df = filter_core(fetch_res.df)
	if core_df is None or core_df.empty:
		log.info(f"orchestrator: empty CORE from {fetch_res.source_url}")

	agents = agents if agents is not None else build_default_agents()

	# DB 연결 — 실패 시 즉시 반환
	try:
		_db_conn = get_connection()
		run_migrations(_db_conn)
	except Exception as e:  # noqa: BLE001
		log.warning(f"orchestrator: DB init failed: {e}")
		return {"skipped": "db_init_failed"}

	result: dict = {
		"date": today_iso,
		"snapshot_date": fetch_res.snapshot_date,
		"source_url": fetch_res.source_url,
		"agents": {},
		"commentary": {},
		"weekly_review": None,
	}

	spy_close = _fetch_spy_close()

	# 한 번만 fetch: 모든 에이전트의 보유 + core 티커 전체
	all_states = {a.name: pf.load_state(a.name, conn=_db_conn) for a in agents}
	fetch_tickers: set[str] = set()
	for s in all_states.values():
		fetch_tickers.update(p.ticker for p in s.positions)
	if core_df is not None and not core_df.empty:
		fetch_tickers.update(core_df["ticker"].dropna().astype(str).tolist())

	current_closes = (
		pf.fetch_current_closes(sorted(fetch_tickers)) if fetch_tickers else {}
	)

	agent_exec_results: dict[str, dict] = {}

	# 월요일에만 섹터 RS 계산 (etf_only 에이전트에 주입)
	today_dt = today  # today는 이미 date 객체
	sector_rs_df = None
	if today_dt.weekday() == 0:  # 월요일
		try:
			sector_rs_df = compute_sector_rs(today_dt, list(config.SECTOR_ETFS))
		except Exception as e:
			log.warning("sector_rs compute failed: %s", e)

	try:
		for agent in agents:
			state = all_states[agent.name]

			ctx_pre = AgentContext(
				as_of=today_iso,
				state=state,
				core_df=core_df if core_df is not None else pd.DataFrame(),
				current_closes=current_closes,
				total_value=0.0,
				tier_thresholds=config.TIER_THRESHOLDS,
				high_vol_keywords=config.HIGH_VOL_HINT_KEYWORDS,
				sector_rs=sector_rs_df,
			)

			sells = agent.decide_sells(ctx_pre)
			pre_eval = pf.evaluate(state, current_closes)
			total_value = pre_eval["total_value"]

			sells_result = orders_mod.execute_orders(
				state=state, sells=sells, buys=[], today_iso=today_iso,
			)

			ctx_post = AgentContext(
				as_of=today_iso,
				state=state,
				core_df=core_df if core_df is not None else pd.DataFrame(),
				current_closes=current_closes,
				total_value=total_value,
				tier_thresholds=config.TIER_THRESHOLDS,
				high_vol_keywords=config.HIGH_VOL_HINT_KEYWORDS,
				sector_rs=sector_rs_df,
			)
			buys = agent.decide_buys(ctx_post)

			buys_result = orders_mod.execute_orders(
				state=state, sells=[], buys=buys, today_iso=today_iso,
			)

			exec_result = {
				"executed_sells": sells_result["executed_sells"],
				"executed_buys": buys_result["executed_buys"],
				"skipped_buys": buys_result["skipped_buys"],
			}
			agent_exec_results[agent.name] = exec_result

			final_eval = pf.evaluate(state, current_closes)

			try:
				upsert_agent(_db_conn, agent.name, type(agent).__name__)
				insert_trades(
					_db_conn,
					today_iso,
					agent.name,
					exec_result["executed_sells"],
					exec_result["executed_buys"],
				)
				pf.save_state(
					state,
					conn=_db_conn,
					today_iso=today_iso,
					equity_value=final_eval["equity_value"],
					total_value=final_eval["total_value"],
					num_positions=final_eval["num_positions"],
				)
			except Exception as e:  # noqa: BLE001
				log.warning(f"orchestrator: DB write for {agent.name} failed: {e}")

			result["agents"][agent.name] = final_eval
			result["commentary"][agent.name] = _build_commentary(
				agent.name, exec_result, final_eval, today_iso
			)

		if spy_close is not None:
			try:
				upsert_benchmark(_db_conn, today_iso, "SPY", spy_close)
			except Exception as e:  # noqa: BLE001
				log.warning(f"orchestrator: benchmark upsert failed: {e}")

		# factor_snapshots record (before commit)
		try:
			traded: set[str] = set()
			for exec_result in agent_exec_results.values():
				for order in exec_result.get("executed_buys", []):
					traded.add(order.ticker)
				for order in exec_result.get("executed_sells", []):
					traded.add(order.ticker)
			snapshot_date = fetch_res.snapshot_date if fetch_res.snapshot_date else today_iso
			if traded and core_df is not None and not core_df.empty:
				rows = _build_factor_rows(core_df, traded)
				insert_factor_snapshots_bulk(_db_conn, snapshot_date, rows)
		except Exception as e:  # noqa: BLE001
			log.warning("factor_snapshots write failed: %s", e)

		_db_conn.commit()

		if today.weekday() == 6:  # Sunday
			try:
				result["weekly_review"] = weekly_review.build(_db_conn, today_iso)
			except Exception as e:  # noqa: BLE001
				log.warning(f"orchestrator: weekly_review build failed: {e}")

	except Exception as e:  # noqa: BLE001
		log.warning(f"orchestrator: agent loop failed: {e}")
		try:
			_db_conn.rollback()
		except Exception:  # noqa: BLE001
			pass
	finally:
		try:
			_db_conn.close()
		except Exception:  # noqa: BLE001
			pass

	return result
