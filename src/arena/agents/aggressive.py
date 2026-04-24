"""Aggressive 에이전트 stub.

# TODO(Phase 1): 고변동성/고베타 모멘텀 전략 구현.
"""
from __future__ import annotations


class AggressiveAgent:
    name = "aggressive"

    def decide(self, ctx: object) -> tuple[list, list]:
        raise NotImplementedError("Phase 1")
