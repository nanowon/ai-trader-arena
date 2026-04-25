"""Phase 1 port smoke tests.

- 룰 순수 함수 (decide_sells / decide_buys)
- 에이전트 Protocol 구현 확인
- 주문 집행 state 뮤테이션
- fetcher URL 빌드
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from arena import config
from arena.agents import (
    AggressiveAgent, BalancedAgent, ConservativeAgent, AgentContext,
    build_default_agents,
)
from arena.engine import rules, orders
from arena.engine.calendar import is_market_open, previous_trading_day
from arena.engine.portfolio import PortfolioState, Position, evaluate
from arena.data.fetcher import _build_url


def _make_state(cash: float = 100_000.0, positions: list[Position] | None = None) -> PortfolioState:
    return PortfolioState(
        agent="test", cash=cash, last_updated="", positions=list(positions or []),
    )


def test_decide_sells_stop_loss_pct():
    pos = Position("AAA", 10, entry_price=100.0, entry_date="2026-04-01")
    state = _make_state(positions=[pos])
    cfg = {"stop_loss_pct": -0.30}
    sells = rules.decide_sells(state, {"AAA": 69.0}, cfg, ())
    assert len(sells) == 1 and sells[0].reason == "stop"


def test_decide_sells_target_wins_over_nothing():
    pos = Position("BBB", 5, 100.0, "2026-04-01", entry_target_price=120.0)
    state = _make_state(positions=[pos])
    sells = rules.decide_sells(state, {"BBB": 125.0}, {}, ())
    assert sells[0].reason == "target"


def test_decide_buys_respects_tier_and_budget():
    state = _make_state(cash=100_000.0)
    core = pd.DataFrame([
        {"ticker": "AAA", "quality_pct": 0.9, "hint_tag": "",
         "entry_price": 50.0, "target_price": 60.0, "stop_price": 40.0},
        {"ticker": "BBB", "quality_pct": 0.5, "hint_tag": "",
         "entry_price": 50.0, "target_price": 60.0, "stop_price": 40.0},
    ])
    cfg = config.AGENT_CONFIGS["aggressive"]  # Q5 only, 30% budget, max 4
    buys = rules.decide_buys(
        state, core, cfg, config.HIGH_VOL_HINT_KEYWORDS,
        config.TIER_THRESHOLDS, total_value=100_000.0, today_iso="2026-04-24",
    )
    # BBB는 Q3(0.5) → Q5만 허용되는 aggressive에선 제외
    assert len(buys) == 1 and buys[0].ticker == "AAA"
    # 30% of 100k = 30k, entry 50 → 600 qty
    assert buys[0].qty == 600


def test_decide_buys_skip_high_vol():
    state = _make_state(cash=100_000.0)
    core = pd.DataFrame([{
        "ticker": "XXX", "quality_pct": 0.95, "hint_tag": "고변동 모멘텀",
        "entry_price": 50.0, "target_price": 60.0, "stop_price": 40.0,
    }])
    cfg = config.AGENT_CONFIGS["conservative"]
    buys = rules.decide_buys(
        state, core, cfg, config.HIGH_VOL_HINT_KEYWORDS,
        config.TIER_THRESHOLDS, total_value=100_000.0, today_iso="2026-04-24",
    )
    assert buys == []


def test_execute_orders_mutates_state():
    state = _make_state(cash=10_000.0)
    buy = rules.BuyOrder(
        ticker="AAA", qty=10, price=100.0,
        target_price=120.0, stop_price=80.0, hint_tag="", quality_pct=0.9,
    )
    r = orders.execute_orders(state, sells=[], buys=[buy], today_iso="2026-04-24")
    assert state.cash == pytest.approx(9_000.0)
    assert len(state.positions) == 1
    assert r["executed_buys"][0].ticker == "AAA"


def test_execute_orders_skip_when_insufficient_cash():
    state = _make_state(cash=50.0)
    buy = rules.BuyOrder("AAA", 10, 100.0, None, None, "", 0.9)
    r = orders.execute_orders(state, [], [buy], "2026-04-24")
    assert r["executed_buys"] == []
    assert len(r["skipped_buys"]) == 1


def test_agents_conform_to_protocol():
    agents = build_default_agents()
    assert {a.name for a in agents} == {"aggressive", "balanced", "conservative", "etf_only"}
    for a in agents:
        assert hasattr(a, "decide_sells") and hasattr(a, "decide_buys")


def test_agent_decide_returns_orders_on_ctx():
    agent = AggressiveAgent()
    state = _make_state(cash=100_000.0)
    core = pd.DataFrame([{
        "ticker": "AAA", "quality_pct": 0.9, "hint_tag": "",
        "entry_price": 50.0, "target_price": 60.0, "stop_price": 40.0,
    }])
    ctx = AgentContext(
        as_of="2026-04-24", state=state, core_df=core,
        current_closes={"AAA": 51.0}, total_value=100_000.0,
        tier_thresholds=config.TIER_THRESHOLDS,
        high_vol_keywords=config.HIGH_VOL_HINT_KEYWORDS,
    )
    assert agent.decide_sells(ctx) == []
    buys = agent.decide_buys(ctx)
    assert len(buys) == 1 and buys[0].ticker == "AAA"


def test_calendar_weekend_closed():
    assert is_market_open(date(2026, 4, 25)) is False  # Saturday
    assert is_market_open(date(2026, 4, 24)) is True   # Friday


def test_calendar_previous_trading_day():
    # 2026-04-06 (Monday) 이전 개장일 → 4-02 (Thursday: 4-03 Good Friday holiday)
    assert previous_trading_day(date(2026, 4, 6)) == date(2026, 4, 2)


def test_fetcher_url_build():
    url = _build_url(date(2026, 4, 23))
    assert url.endswith("/data/tracking/picks_2026-04-23.parquet")


def test_evaluate_fallback_to_entry_price():
    pos = Position("ZZZ", 2, 50.0, "2026-04-01")
    state = _make_state(cash=0.0, positions=[pos])
    ev = evaluate(state, {})  # no closes
    assert ev["equity_value"] == pytest.approx(100.0)
