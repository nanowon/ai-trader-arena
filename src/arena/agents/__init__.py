"""에이전트 전략 패키지."""
from __future__ import annotations

from arena.agents.aggressive import AggressiveAgent
from arena.agents.balanced import BalancedAgent
from arena.agents.base import AgentContext, AgentStrategy, BuyOrder, SellOrder
from arena.agents.conservative import ConservativeAgent
from arena.agents.etf_only import ETFOnlyAgent

__all__ = [
    "AgentContext",
    "AgentStrategy",
    "BuyOrder",
    "SellOrder",
    "AggressiveAgent",
    "BalancedAgent",
    "ConservativeAgent",
    "ETFOnlyAgent",
    "build_default_agents",
]


def build_default_agents() -> list[AgentStrategy]:
    """Phase 1 기본 3 에이전트 + Phase 4 ETFOnlyAgent."""
    return [AggressiveAgent(), BalancedAgent(), ConservativeAgent(), ETFOnlyAgent()]
