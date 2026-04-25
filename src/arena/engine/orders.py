"""주문 집행 — state 뮤테이션.

sells 먼저(현금 확보) → buys 순. 현금 부족 시 buy skip + warning.
수수료/슬리피지 0.
"""
from __future__ import annotations

import logging

from arena.engine.rules import BuyOrder, SellOrder
from arena.engine.portfolio import Position, PortfolioState

log = logging.getLogger(__name__)


def execute_orders(
    state: PortfolioState,
    sells: list[SellOrder],
    buys: list[BuyOrder],
    today_iso: str,
) -> dict:
    executed_sells: list[SellOrder] = []
    executed_buys: list[BuyOrder] = []
    skipped_buys: list[BuyOrder] = []

    remaining: list[Position] = []
    sell_map = {s.ticker: s for s in sells}
    for p in state.positions:
        sell = sell_map.get(p.ticker)
        if sell is None:
            remaining.append(p)
            continue
        proceeds = sell.qty * sell.price
        state.cash = float(state.cash) + float(proceeds)
        executed_sells.append(sell)
        log.info(
            f"[{state.agent}] SELL {sell.ticker} x{sell.qty} @ {sell.price:.2f} "
            f"({sell.reason}) — cash += {proceeds:.2f}"
        )
    state.positions = remaining

    held = {p.ticker for p in state.positions}
    for b in buys:
        if b.ticker in held:
            log.warning(f"[{state.agent}] BUY skipped {b.ticker}: already held")
            skipped_buys.append(b)
            continue
        cost = b.qty * b.price
        if cost > float(state.cash) + 1e-6:
            log.warning(
                f"[{state.agent}] BUY skipped {b.ticker} x{b.qty} @ {b.price:.2f}: "
                f"cost {cost:.2f} > cash {state.cash:.2f}"
            )
            skipped_buys.append(b)
            continue
        state.cash = float(state.cash) - float(cost)
        state.positions.append(Position(
            ticker=b.ticker,
            qty=int(b.qty),
            entry_price=float(b.price),
            entry_date=today_iso,
            entry_target_price=b.target_price,
            entry_stop_price=b.stop_price,
            entry_hint_tag=b.hint_tag or "",
        ))
        held.add(b.ticker)
        executed_buys.append(b)
        log.info(
            f"[{state.agent}] BUY {b.ticker} x{b.qty} @ {b.price:.2f} — "
            f"cash -= {cost:.2f}"
        )

    state.last_updated = today_iso
    return {
        "executed_sells": executed_sells,
        "executed_buys": executed_buys,
        "skipped_buys": skipped_buys,
    }
