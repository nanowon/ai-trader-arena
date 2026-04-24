"""ETF-Only 에이전트 stub.

# TODO(Phase 1): 섹터 ETF 패시브 로테이션 전략 구현.
"""
from __future__ import annotations


class ETFOnlyAgent:
    name = "etf_only"

    def decide(self, ctx: object) -> tuple[list, list]:
        raise NotImplementedError("Phase 1")
