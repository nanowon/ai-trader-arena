"""Conservative: Q4~Q5 CORE, 고변동 태그 제외, 종목당 10%."""
from __future__ import annotations

from arena import config
from arena.agents.base import AgentContext, BuyOrder, SellOrder
from arena.engine import rules


class ConservativeAgent:
    name = "conservative"

    def __init__(self, cfg: dict | None = None) -> None:
        self.cfg = cfg or config.AGENT_CONFIGS[self.name]

    def decide_sells(self, ctx: AgentContext) -> list[SellOrder]:
        return rules.decide_sells(
            state=ctx.state,
            current_closes=ctx.current_closes,
            agent_cfg=self.cfg,
            high_vol_keywords=ctx.high_vol_keywords,
        )

    def decide_buys(self, ctx: AgentContext) -> list[BuyOrder]:
        return rules.decide_buys(
            state=ctx.state,
            core_df=ctx.core_df,
            agent_cfg=self.cfg,
            high_vol_keywords=ctx.high_vol_keywords,
            tier_thresholds=ctx.tier_thresholds,
            total_value=ctx.total_value,
            today_iso=ctx.as_of,
        )
