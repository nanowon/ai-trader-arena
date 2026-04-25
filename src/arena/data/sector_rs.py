"""섹터 ETF 상대 강도(RS) 계산 모듈."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

log = logging.getLogger(__name__)


def _download(tickers: list[str], period: str, **kw) -> pd.DataFrame:
    """yfinance 다운로드 래퍼. 테스트에서 monkeypatch 대상."""
    import yfinance as yf
    return yf.download(tickers, period=period, **kw)


def compute_sector_rs(
    as_of: date,
    etfs: list[str],
    benchmark: str = "SPY",
    lookback_days: int = 60,
) -> pd.DataFrame | None:
    """섹터 ETF RS 스코어 계산.

    Args:
        as_of: 기준일
        etfs: 섹터 ETF 목록
        benchmark: 벤치마크 티커 (기본 SPY)
        lookback_days: 수익률 계산에 사용할 최근 거래일 수

    Returns:
        columns: ticker, ret_60d, spy_ret_60d, rs_score, rank
        실패 시 None
    """
    all_tickers = list(etfs) + ([benchmark] if benchmark not in etfs else [])

    try:
        # 90 달력일치 다운로드
        raw = _download(all_tickers, period="3mo", auto_adjust=True, progress=False)
    except Exception as e:
        log.warning("sector_rs: download failed: %s", e)
        return None

    # Close 컬럼 추출
    if isinstance(raw.columns, pd.MultiIndex):
        if "Close" in raw.columns.get_level_values(0):
            prices = raw["Close"]
        else:
            log.warning("sector_rs: 'Close' not found in MultiIndex columns")
            return None
    else:
        prices = raw

    if prices is None or prices.empty:
        log.warning("sector_rs: empty price data")
        return None

    prices = prices.ffill()

    # 최근 lookback_days 거래일 슬라이싱
    prices = prices.tail(lookback_days + 1)
    if len(prices) < 2:
        log.warning("sector_rs: insufficient rows after slicing (%d)", len(prices))
        return None

    # 수익률 = (마지막 종가 / 첫 종가) - 1
    ret_series = prices.iloc[-1] / prices.iloc[0] - 1.0

    if benchmark not in ret_series.index:
        log.warning("sector_rs: benchmark %s not in price data", benchmark)
        return None

    spy_ret = float(ret_series[benchmark])

    rows = []
    for ticker in etfs:
        if ticker not in ret_series.index:
            continue
        etf_ret = float(ret_series[ticker])
        rs_score = etf_ret - spy_ret
        rows.append({
            "ticker": ticker,
            "ret_60d": etf_ret,
            "spy_ret_60d": spy_ret,
            "rs_score": rs_score,
        })

    if not rows:
        log.warning("sector_rs: no valid ETF rows computed")
        return None

    df = pd.DataFrame(rows)
    df["rank"] = df["rs_score"].rank(ascending=False, method="first").astype(int)
    df = df.sort_values("rank").reset_index(drop=True)

    return df
