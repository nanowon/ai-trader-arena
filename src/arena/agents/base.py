"""에이전트 전략 Protocol + 컨텍스트/주문 데이터 모델.

Phase 1: aggressive/balanced/conservative 3종이 이 Protocol을 구현한다.
Phase 4: etf_only 에이전트 추가 예정.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TYPE_CHECKING

import pandas as pd

from arena.engine.rules import BuyOrder, SellOrder

if TYPE_CHECKING:
    from arena.engine.portfolio import PortfolioState


__all__ = ["BuyOrder", "SellOrder", "AgentContext", "AgentStrategy"]


@dataclass
class AgentContext:
    """에이전트 decide_* 에 주입되는 입력 스냅샷.

    decide_sells는 매도 실행 전 state, decide_buys는 매도 실행 후 state 를
    바라본다 (orchestrator가 순서대로 호출).
    """

    as_of: str  # ISO date
    state: "PortfolioState"
    core_df: pd.DataFrame
    current_closes: dict[str, float]
    total_value: float
    tier_thresholds: dict[str, float]
    high_vol_keywords: tuple[str, ...] = field(default_factory=tuple)
    sector_rs: pd.DataFrame | None = None


class AgentStrategy(Protocol):
    name: str

    def decide_sells(self, ctx: AgentContext) -> list[SellOrder]:
        ...

    def decide_buys(self, ctx: AgentContext) -> list[BuyOrder]:
        ...
