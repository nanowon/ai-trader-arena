"""NYSE 개장일 판정.

pandas_market_calendars 의존 없이 2024~2027 관측일을 하드코딩. 주말 제외.
2027 이후 유지보수 필요.
"""
from __future__ import annotations

from datetime import date, timedelta

# TODO(2027-12): 2028 이후 holiday 추가 또는 pandas_market_calendars 도입.
NYSE_HOLIDAYS: set[date] = {
    date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 3, 29),
    date(2024, 5, 27), date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2),
    date(2024, 11, 28), date(2024, 12, 25),
    date(2025, 1, 1), date(2025, 1, 9), date(2025, 1, 20), date(2025, 2, 17),
    date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4),
    date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25),
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
    date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6),
    date(2027, 11, 25), date(2027, 12, 24),
}


def is_market_open(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    if d in NYSE_HOLIDAYS:
        return False
    return True


def previous_trading_day(d: date) -> date:
    probe = d - timedelta(days=1)
    for _ in range(60):
        if is_market_open(probe):
            return probe
        probe = probe - timedelta(days=1)
    raise RuntimeError(
        f"previous_trading_day: 60일 내 개장일을 찾지 못함 (d={d}). "
        "NYSE_HOLIDAYS 업데이트 필요."
    )


def most_recent_trading_day(d: date) -> date:
    """d 자체가 개장일이면 d, 아니면 이전 첫 개장일."""
    if is_market_open(d):
        return d
    return previous_trading_day(d)
