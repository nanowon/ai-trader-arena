"""에이전트 전략 프로토콜 및 주문 데이터 모델.

Phase 1에서 4 에이전트 (aggressive / balanced / conservative / etf_only) 가
이 Protocol을 구현합니다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class BuyOrder:
    ticker: str
    shares: int
    limit_price: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class SellOrder:
    ticker: str
    shares: int
    limit_price: float | None = None
    reason: str = ""


@dataclass(frozen=True)
class AgentContext:
    """에이전트가 의사결정에 쓰는 입력 스냅샷."""

    as_of: str
    cash: float
    positions: dict[str, int]
    universe: list[str]


class AgentStrategy(Protocol):
    """에이전트가 구현해야 할 인터페이스."""

    name: str

    def decide(
        self, ctx: AgentContext
    ) -> tuple[list[BuyOrder], list[SellOrder]]:
        """현재 컨텍스트로부터 매수/매도 주문을 산출."""
        ...
