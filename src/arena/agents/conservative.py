"""Conservative 에이전트 stub.

# TODO(Phase 1): 저변동성/배당 중심 전략 구현.
"""
from __future__ import annotations


class ConservativeAgent:
    name = "conservative"

    def decide(self, ctx: object) -> tuple[list, list]:
        raise NotImplementedError("Phase 1")
