"""Balanced 에이전트 stub.

# TODO(Phase 1): 모멘텀+퀄리티+밸류 팩터 균형 전략 구현.
"""
from __future__ import annotations


class BalancedAgent:
    name = "balanced"

    def decide(self, ctx: object) -> tuple[list, list]:
        raise NotImplementedError("Phase 1")
