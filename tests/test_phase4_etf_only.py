"""Phase 4: ETFOnlyAgent + compute_sector_rs 테스트."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from arena.agents.base import AgentContext
from arena.agents.etf_only import ETFOnlyAgent
from arena.data.sector_rs import compute_sector_rs
from arena.engine.portfolio import PortfolioState, Position


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _make_state(cash: float = 100_000.0, positions: list | None = None) -> PortfolioState:
    return PortfolioState(
        agent="etf_only",
        cash=cash,
        last_updated="",
        positions=list(positions or []),
    )


def _make_ctx(
    as_of: str,
    state: PortfolioState,
    sector_rs: pd.DataFrame | None,
    current_closes: dict | None = None,
) -> AgentContext:
    return AgentContext(
        as_of=as_of,
        state=state,
        core_df=pd.DataFrame(),
        current_closes=current_closes or {},
        total_value=state.cash,
        tier_thresholds={},
        sector_rs=sector_rs,
    )


def _make_fake_prices(tickers: list[str], start: float = 100.0, end: float = 110.0, rows: int = 62) -> pd.DataFrame:
    """tickers 각각에 대해 start → end 선형 가격 DataFrame 반환."""
    import numpy as np
    idx = pd.date_range("2025-01-01", periods=rows, freq="B")
    data = {}
    for i, t in enumerate(tickers):
        # 티커마다 약간 다른 수익률 부여
        factor = 1.0 + i * 0.01
        prices = np.linspace(start, end * factor, rows)
        data[t] = prices
    return pd.DataFrame(data, index=idx)


def _make_sector_rs(top_tickers: list[str], all_tickers: list[str] | None = None) -> pd.DataFrame:
    """top_tickers가 rank 1~N을 차지하는 가짜 sector_rs DataFrame."""
    if all_tickers is None:
        all_tickers = top_tickers
    rows = []
    for i, t in enumerate(all_tickers, start=1):
        rows.append({
            "ticker": t,
            "ret_60d": 0.10 - i * 0.01,
            "spy_ret_60d": 0.05,
            "rs_score": 0.05 - i * 0.01,
            "rank": i,
        })
    return pd.DataFrame(rows)


# ── test1: compute_sector_rs RS 계산 및 rank 검증 ────────────────────────────

def test_compute_sector_rs_basic(monkeypatch):
    """_download monkeypatch → RS 계산 및 rank 검증."""
    tickers = ["XLK", "XLF", "XLV", "SPY"]

    # XLK가 가장 높은 수익률 → rank 1 기대
    import numpy as np
    rows = 62
    idx = pd.date_range("2025-01-01", periods=rows, freq="B")
    prices = pd.DataFrame({
        "XLK": np.linspace(100, 130, rows),   # +30%
        "XLF": np.linspace(100, 115, rows),   # +15%
        "XLV": np.linspace(100, 108, rows),   # +8%
        "SPY": np.linspace(100, 110, rows),   # +10% (benchmark)
    }, index=idx)
    # MultiIndex 없는 단순 DataFrame 반환
    mc = pd.MultiIndex.from_tuples(
        [("Close", t) for t in ["XLK", "XLF", "XLV", "SPY"]],
    )
    multi_df = prices.copy()
    multi_df.columns = mc

    import arena.data.sector_rs as sr_mod
    monkeypatch.setattr(sr_mod, "_download", lambda tickers, period, **kw: multi_df)

    result = compute_sector_rs(
        as_of=date(2025, 4, 21),
        etfs=["XLK", "XLF", "XLV"],
        benchmark="SPY",
        lookback_days=60,
    )

    assert result is not None
    assert set(result.columns) == {"ticker", "ret_60d", "spy_ret_60d", "rs_score", "rank"}
    assert len(result) == 3

    # XLK rs_score = 0.30 - 0.10 = 0.20 (가장 높음) → rank 1
    top = result.loc[result["rank"] == 1, "ticker"].iloc[0]
    assert top == "XLK"

    # rank는 1-based, 중복 없음
    assert sorted(result["rank"].tolist()) == [1, 2, 3]


# ── test2: 월요일 첫 진입, Top-3 전부 미보유 → buy 3건 ────────────────────────

def test_etf_only_monday_first_entry():
    """월요일, Top-3 전부 미보유 → 3건 매수."""
    agent = ETFOnlyAgent()
    state = _make_state(cash=90_000.0)

    sector_rs = _make_sector_rs(["XLK", "XLF", "XLV"])
    closes = {"XLK": 100.0, "XLF": 50.0, "XLV": 80.0}

    # 2026-04-27은 월요일
    ctx = _make_ctx("2026-04-27", state, sector_rs, closes)

    sells = agent.decide_sells(ctx)
    assert sells == []

    buys = agent.decide_buys(ctx)
    assert len(buys) == 3
    bought_tickers = {b.ticker for b in buys}
    assert bought_tickers == {"XLK", "XLF", "XLV"}
    for b in buys:
        assert b.hint_tag == "sector_rotation"
        assert b.qty > 0


# ── test3: 비-월요일 → sells=[], buys=[] ─────────────────────────────────────

def test_etf_only_non_monday_no_action():
    """화요일 → 매도/매수 없음."""
    agent = ETFOnlyAgent()
    state = _make_state(cash=100_000.0)
    sector_rs = _make_sector_rs(["XLK", "XLF", "XLV"])

    # 2026-04-28은 화요일
    ctx = _make_ctx("2026-04-28", state, sector_rs, {"XLK": 100.0})

    assert agent.decide_sells(ctx) == []
    assert agent.decide_buys(ctx) == []


# ── test4: 월요일이지만 sector_rs=None → 무행동 ──────────────────────────────

def test_etf_only_monday_no_sector_rs():
    """월요일이지만 sector_rs=None → 무행동."""
    agent = ETFOnlyAgent()
    state = _make_state(cash=100_000.0)

    ctx = _make_ctx("2026-04-27", state, sector_rs=None, current_closes={"XLK": 100.0})

    assert agent.decide_sells(ctx) == []
    assert agent.decide_buys(ctx) == []


# ── test5: 월요일 rotation — 보유 1개 Top-3 탈락 → 매도 + 신규 1개 매수 ──────

def test_etf_only_rotation_partial():
    """월요일, XLE 보유(Top-3 탈락) → 매도, XLV 신규 매수."""
    agent = ETFOnlyAgent()

    # XLE 50주 보유, 현금 10_000
    pos_xle = Position("XLE", 50, entry_price=80.0, entry_date="2026-04-20")
    state = _make_state(cash=10_000.0, positions=[pos_xle])

    # Top-3: XLK(1), XLF(2), XLV(3) — XLE는 4위
    all_tickers = ["XLK", "XLF", "XLV", "XLE"]
    sector_rs = _make_sector_rs(all_tickers, all_tickers)

    closes = {"XLE": 82.0, "XLK": 100.0, "XLF": 50.0, "XLV": 80.0}
    ctx = _make_ctx("2026-04-27", state, sector_rs, closes)

    sells = agent.decide_sells(ctx)
    assert len(sells) == 1
    assert sells[0].ticker == "XLE"
    assert sells[0].reason == "rotation"
    assert sells[0].price == pytest.approx(82.0)

    # decide_buys: XLK, XLF, XLV 중 미보유만 (XLE는 여전히 state에 있으나 Top-3 아님)
    # 현금 10_000 / 3종목 중 미보유 3개
    buys = agent.decide_buys(ctx)
    buy_tickers = {b.ticker for b in buys}
    # XLK, XLF, XLV 모두 미보유이므로 3건 시도 (현금 충분한 것만)
    assert buy_tickers.issubset({"XLK", "XLF", "XLV"})
    assert len(buys) >= 1
