"""템플릿 기반 코멘터리.

seeded random으로 (date, agent, trigger, ticker) 조합에 대해 고정 문구 선택.
"""
from __future__ import annotations

import random

TEMPLATES: dict[tuple[str, str], list[str]] = {
    ("aggressive", "buy"): [
        "{ticker} 풀매수. Q5 아니면 거르는 게 낫다.",
        "{ticker} 들어간다. 반토막 나도 간다.",
        "{ticker}. 크게 먹을 거다.",
    ],
    ("aggressive", "sell_target"): [
        "{ticker} 목표가 +{return_pct:.1%}. 익절.",
        "{ticker} 먹튀 완료. {return_pct:.1%}.",
        "{ticker} 목표 도달. 다음 판 간다.",
    ],
    ("aggressive", "sell_stop"): [
        "{ticker} -30% 손절. 쿨하게 잘랐다.",
        "{ticker} 컷. 감정 개입 없음.",
        "{ticker} 털었다. {return_pct:.1%}.",
    ],
    ("aggressive", "sell_volatility"): [
        "{ticker} 변동성 정리.",
        "{ticker} 리스크 오프.",
        "{ticker} 빠진다.",
    ],
    ("aggressive", "hold"): [
        "포지션 {num_positions}개. 가만히 간다.",
        "{num_positions}개 들고 있음. 쫄리지 않음.",
        "보유 유지. 룰대로.",
    ],
    ("aggressive", "volatility_warning"): [
        "변동성 경고? 공격형엔 기회다.",
        "흔들리는 놈이 큰 거 준다.",
        "변동성은 기본 옵션.",
    ],
    ("aggressive", "empty_day"): [
        "오늘은 관망. CORE Q5 기다린다.",
        "거래 없음. 기회 올 때까지.",
        "No trade. 다음 판 준비.",
    ],

    ("balanced", "buy"): [
        "{ticker} 매수: 진입 ${price:.2f}, 목표 ${target_price:.2f}, 스탑 ${stop_price:.2f}.",
        "{ticker} 신규 편입. quality_pct {quality_pct:.0%}, 포지션 수 {num_positions}.",
        "{ticker} 진입가 ${price:.2f}. 목표·스탑 파이프라인 준수.",
    ],
    ("balanced", "sell_target"): [
        "{ticker} 목표가 ${target_price:.2f} 도달. 수익률 {return_pct:+.2%}.",
        "{ticker} 청산. 진입 ${entry_price:.2f} → 종가 ${price:.2f} ({return_pct:+.2%}).",
        "{ticker} 익절. 수익률 {return_pct:+.2%}, 현금 비중 재조정.",
    ],
    ("balanced", "sell_stop"): [
        "{ticker} 스탑 ${stop_price:.2f} 이탈. 손실 {return_pct:+.2%}.",
        "{ticker} 손절. 진입 ${entry_price:.2f} → ${price:.2f} ({return_pct:+.2%}).",
        "{ticker} 스탑 히트. 룰대로 집행.",
    ],
    ("balanced", "sell_volatility"): [
        "{ticker} 변동성 기준 청산 ({return_pct:+.2%}).",
        "{ticker} 리스크 관리용 청산.",
        "{ticker} 고변동 태그로 정리.",
    ],
    ("balanced", "hold"): [
        "보유 {num_positions}종목, 현금 ${cash:.0f}, 총자산 ${total_value:.0f}.",
        "포지션 {num_positions}개 유지. 총자산 ${total_value:.0f}.",
        "No change. {num_positions}개 포지션, 현금 ${cash:.0f}.",
    ],
    ("balanced", "volatility_warning"): [
        "{ticker} 변동성 태그 감지: {hint_tag}. 사이징 유의.",
        "{ticker} 고변동 힌트. 룰상 편입은 허용.",
        "{ticker} 변동성 경고 — 리뷰 필요.",
    ],
    ("balanced", "empty_day"): [
        "CORE 편입 후보 없음. 현금 ${cash:.0f} 유지.",
        "No trade today. 현금 비중 100%.",
        "매수/매도 모두 0건. 총자산 ${total_value:.0f}.",
    ],

    ("conservative", "buy"): [
        "{ticker} 소량 편입. 변동성 제외 종목으로만.",
        "{ticker} 진입. 분산 우선, 포지션 {num_positions}번째.",
        "{ticker} 보수적 사이징으로 편입.",
    ],
    ("conservative", "sell_target"): [
        "{ticker} 목표 도달 {return_pct:+.2%}. 차익 실현.",
        "{ticker} 계획대로 익절. 수익률 {return_pct:+.2%}.",
        "{ticker} 목표가 터치. 리스크 회수.",
    ],
    ("conservative", "sell_stop"): [
        "{ticker} 스탑 발동. 손실 제한 {return_pct:+.2%}.",
        "{ticker} 룰상 손절. 추가 하락 전 방어.",
        "{ticker} 스탑 히트 — 감정 배제.",
    ],
    ("conservative", "sell_volatility"): [
        "{ticker} 고변동 태그로 선제 청산.",
        "{ticker} 변동성 상승 — 보수 원칙상 회수.",
        "{ticker} 안정형 기준 미달로 정리.",
    ],
    ("conservative", "hold"): [
        "안정 유지. {num_positions}개 포지션, 현금 쿠션 ${cash:.0f}.",
        "리밸런싱 불필요. 방어적 자세 유지.",
        "보유 {num_positions}개, 원칙대로 hold.",
    ],
    ("conservative", "volatility_warning"): [
        "{ticker} 변동성 경고. 보수형은 신규 편입 보류.",
        "{ticker} 고변동 태그 — 편입 제외.",
        "{ticker} 리스크 상향. 안전 우선.",
    ],
    ("conservative", "empty_day"): [
        "관망. 현금 ${cash:.0f} 확보 상태 유지.",
        "편입 조건 미달 — 대기.",
        "거래 없음. 원금 보존 우선.",
    ],
}


def _seed_for(date_iso: str, agent: str, trigger: str, ticker: str) -> int:
    return hash((date_iso, agent, trigger, ticker)) & 0xFFFFFFFF


_DEFAULTS = {
    "ticker": "", "price": 0.0, "entry_price": 0.0, "target_price": 0.0,
    "stop_price": 0.0, "return_pct": 0.0, "quality_pct": 0.0, "hint_tag": "",
    "num_positions": 0, "cash": 0.0, "total_value": 0.0, "date_iso": "",
}


def generate_commentary(agent: str, trigger: str, context: dict) -> str:
    templates = TEMPLATES.get((agent, trigger))
    if not templates:
        return ""

    date_iso = str(context.get("date_iso", ""))
    ticker = str(context.get("ticker", ""))
    rng = random.Random(_seed_for(date_iso, agent, trigger, ticker))
    tpl = rng.choice(templates)

    try:
        return tpl.format(**{**_DEFAULTS, **context})
    except Exception:
        return tpl
