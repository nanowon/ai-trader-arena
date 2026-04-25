"""매매 룰 (순수 함수).

매도 우선순위: 손절 → 목표가 → 고변동(conservative만). CORE 탈락만으로는 매도 안 함.

매수:
  - CORE 후보 중 allowed_tiers 한정
  - skip_high_vol=True면 hint_tag에 고변동 키워드 있는 종목 제외
  - quality_pct 내림차순, 미보유, 현금 충분
  - position_pct_max * total_value 상한 예산, 정수주만
  - max_positions 상한
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class SellOrder:
    ticker: str
    qty: int
    price: float
    reason: str  # 'stop' | 'target' | 'volatility'


@dataclass(frozen=True)
class BuyOrder:
    ticker: str
    qty: int
    price: float
    target_price: float | None
    stop_price: float | None
    hint_tag: str
    quality_pct: float


def _tier_for(quality_pct: float, thresholds: dict) -> str | None:
    if quality_pct is None or pd.isna(quality_pct):
        return None
    q = float(quality_pct)
    if q >= thresholds.get("Q5", 0.80):
        return "Q5"
    if q >= thresholds.get("Q4", 0.60):
        return "Q4"
    if q >= thresholds.get("Q3", 0.40):
        return "Q3"
    return None


def _is_high_vol(hint_tag: str, keywords: Iterable[str]) -> bool:
    if not isinstance(hint_tag, str) or not hint_tag:
        return False
    return any(k in hint_tag for k in keywords)


def decide_sells(
    state,
    current_closes: dict[str, float],
    agent_cfg: dict,
    high_vol_keywords: Iterable[str] = (),
) -> list[SellOrder]:
    orders: list[SellOrder] = []
    use_pipeline_stop = bool(agent_cfg.get("use_pipeline_stop", False))
    stop_loss_pct = agent_cfg.get("stop_loss_pct")
    skip_high_vol = bool(agent_cfg.get("skip_high_vol", False))

    for p in state.positions:
        px = current_closes.get(p.ticker)
        if px is None or not (isinstance(px, (int, float)) and px > 0):
            continue

        reason: str | None = None

        if use_pipeline_stop and p.entry_stop_price is not None:
            if px <= float(p.entry_stop_price):
                reason = "stop"
        if reason is None and stop_loss_pct is not None:
            ret = (px - p.entry_price) / p.entry_price if p.entry_price > 0 else 0.0
            if ret <= float(stop_loss_pct):
                reason = "stop"

        if reason is None and p.entry_target_price is not None:
            if px >= float(p.entry_target_price):
                reason = "target"

        if reason is None and skip_high_vol and _is_high_vol(p.entry_hint_tag or "", high_vol_keywords):
            reason = "volatility"

        if reason is not None:
            orders.append(SellOrder(ticker=p.ticker, qty=p.qty, price=float(px), reason=reason))

    return orders


def decide_buys(
    state,
    core_df: pd.DataFrame,
    agent_cfg: dict,
    high_vol_keywords: Iterable[str],
    tier_thresholds: dict,
    total_value: float,
    today_iso: str,
    post_sell_cash: float | None = None,
) -> list[BuyOrder]:
    if core_df is None or core_df.empty:
        return []

    allowed_tiers = set(agent_cfg.get("allowed_tiers", []))
    if not allowed_tiers:
        return []

    max_positions = int(agent_cfg.get("max_positions", 0))
    pos_pct_max = float(agent_cfg.get("position_pct_max", 0.0))
    skip_high_vol = bool(agent_cfg.get("skip_high_vol", False))

    held = {p.ticker for p in state.positions}

    candidates = core_df.copy()
    candidates = candidates.sort_values("quality_pct", ascending=False, kind="stable")

    available_cash = float(post_sell_cash if post_sell_cash is not None else state.cash)
    budget_per = pos_pct_max * float(total_value)

    planned: list[BuyOrder] = []
    num_positions_after_sells = len(held)

    for _, row in candidates.iterrows():
        if len(planned) + num_positions_after_sells >= max_positions:
            break

        ticker = str(row.get("ticker", ""))
        if not ticker or ticker in held:
            continue

        tier = _tier_for(row.get("quality_pct"), tier_thresholds)
        if tier not in allowed_tiers:
            continue

        hint_tag = str(row.get("hint_tag", "") or "")
        if skip_high_vol and _is_high_vol(hint_tag, high_vol_keywords):
            continue

        entry_price = row.get("entry_price")
        if entry_price is None or pd.isna(entry_price) or float(entry_price) <= 0:
            continue
        entry_price = float(entry_price)

        qty = int(budget_per // entry_price)
        if qty <= 0:
            continue
        cost = qty * entry_price
        if cost > available_cash:
            qty = int(available_cash // entry_price)
            if qty <= 0:
                continue
            cost = qty * entry_price

        target = row.get("target_price")
        stop = row.get("stop_price")
        target_v = float(target) if target is not None and not pd.isna(target) else None
        stop_v = float(stop) if stop is not None and not pd.isna(stop) else None

        q_raw = row.get("quality_pct")
        q_val = float(q_raw) if q_raw is not None and not pd.isna(q_raw) else 0.0

        planned.append(BuyOrder(
            ticker=ticker,
            qty=qty,
            price=entry_price,
            target_price=target_v,
            stop_price=stop_v,
            hint_tag=hint_tag,
            quality_pct=q_val,
        ))
        available_cash -= cost

    return planned
