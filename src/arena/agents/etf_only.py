"""ETF-Only 에이전트: 섹터 ETF 패시브 로테이션 전략."""
from __future__ import annotations

import math
from datetime import date

from arena import config
from arena.agents.base import AgentContext, BuyOrder, SellOrder

TOP_N = 3
INITIAL_CAPITAL = config.INITIAL_CAPITAL


class ETFOnlyAgent:
    name = "etf_only"

    def decide_sells(self, ctx: AgentContext) -> list[SellOrder]:
        as_of = date.fromisoformat(ctx.as_of) if isinstance(ctx.as_of, str) else ctx.as_of

        # 월요일(0)에만 로테이션 실행
        if as_of.weekday() != 0:
            return []

        if ctx.sector_rs is None:
            return []

        top_set = set(
            ctx.sector_rs.loc[ctx.sector_rs["rank"] <= TOP_N, "ticker"].tolist()
        )

        sells: list[SellOrder] = []
        for pos in ctx.state.positions:
            if pos.ticker not in top_set:
                price = ctx.current_closes.get(pos.ticker, pos.entry_price)
                sells.append(SellOrder(
                    ticker=pos.ticker,
                    qty=pos.qty,
                    price=float(price),
                    reason="rotation",
                ))
        return sells

    def decide_buys(self, ctx: AgentContext) -> list[BuyOrder]:
        as_of = date.fromisoformat(ctx.as_of) if isinstance(ctx.as_of, str) else ctx.as_of

        # 월요일(0)에만 로테이션 실행
        if as_of.weekday() != 0:
            return []

        if ctx.sector_rs is None:
            return []

        top_set = set(
            ctx.sector_rs.loc[ctx.sector_rs["rank"] <= TOP_N, "ticker"].tolist()
        )

        held = {pos.ticker for pos in ctx.state.positions}
        to_buy = [t for t in top_set if t not in held]

        if not to_buy:
            return []

        available_cash = float(ctx.state.cash)
        per_ticker_budget = available_cash / len(to_buy)

        buys: list[BuyOrder] = []
        for ticker in to_buy:
            price = ctx.current_closes.get(ticker)
            if price is None or price <= 0:
                continue
            shares = math.floor(per_ticker_budget / price)
            if shares == 0:
                continue
            buys.append(BuyOrder(
                ticker=ticker,
                qty=shares,
                price=float(price),
                target_price=None,
                stop_price=None,
                hint_tag="sector_rotation",
                quality_pct=0.0,
            ))
        return buys
