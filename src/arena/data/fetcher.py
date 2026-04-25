"""ai-stock-engine raw URL fetcher.

`data/tracking/picks_YYYY-MM-DD.parquet` 를 GitHub raw URL로 받아 pandas
DataFrame으로 파싱한다. 최근 영업일부터 최대 FETCH_MAX_LOOKBACK_DAYS 후퇴
하며 가장 최근에 존재하는 스냅샷을 반환.
"""
from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

import pandas as pd
import requests

from arena import config
from arena.engine import calendar as cal

log = logging.getLogger(__name__)


@dataclass
class FetchResult:
    df: pd.DataFrame
    snapshot_date: str  # ISO date
    source_url: str


class FetcherError(RuntimeError):
    pass


def _build_url(d: date) -> str:
    return config.STAGE2_PICKS_URL_TEMPLATE.format(date=d.isoformat())


def _http_get(url: str, timeout: int) -> tuple[int, bytes]:
    headers: dict[str, str] = {}
    gh_token = os.environ.get("GH_TOKEN", "").strip()
    if gh_token:
        try:
            # HTTP 헤더는 latin-1 범위만 허용. 비ASCII 문자가 섞이면 encode 실패
            gh_token.encode("latin-1")
        except UnicodeEncodeError:
            log.error(
                "GH_TOKEN에 비ASCII 문자가 포함되어 있습니다. "
                "토큰을 다시 확인하세요 (한글/특수문자 포함 금지). "
                "Authorization 헤더 없이 요청을 시도합니다."
            )
            gh_token = ""
        if gh_token:
            headers["Authorization"] = f"token {gh_token}"
    resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    return resp.status_code, resp.content


def fetch_picks(
    today: date | None = None,
    max_lookback_days: int | None = None,
) -> FetchResult:
    """stage2 picks parquet을 원격에서 내려받는다.

    Args:
        today: 기준일 (None이면 UTC 오늘)
        max_lookback_days: 최대 후퇴 일수 (None이면 config 값)

    Raises:
        FetcherError: lookback 범위 내 다운로드 가능한 스냅샷이 없을 때
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    if max_lookback_days is None:
        max_lookback_days = config.FETCH_MAX_LOOKBACK_DAYS

    probe = cal.most_recent_trading_day(today)
    last_err: str | None = None

    for _ in range(max_lookback_days + 1):
        url = _build_url(probe)
        try:
            status, content = _http_get(url, timeout=config.FETCH_TIMEOUT_SEC)
        except Exception as e:  # noqa: BLE001
            last_err = f"{url}: {e}"
            log.warning(f"fetch_picks: request failed {last_err}")
            probe = cal.previous_trading_day(probe)
            continue

        if status == 200 and content:
            try:
                df = pd.read_parquet(io.BytesIO(content))
            except Exception as e:  # noqa: BLE001
                raise FetcherError(f"parquet parse failed for {url}: {e}") from e
            _validate_picks_columns(df)
            log.info(f"fetch_picks: ok {url} rows={len(df)}")
            return FetchResult(df=df, snapshot_date=probe.isoformat(), source_url=url)

        if status == 404:
            log.info(f"fetch_picks: 404 for {url}, stepping back")
        else:
            log.warning(f"fetch_picks: status={status} for {url}")
            last_err = f"{url}: status={status}"

        probe = cal.previous_trading_day(probe)

    raise FetcherError(
        f"No picks snapshot found within {max_lookback_days} trading days back from {today}."
        f" Last error: {last_err or 'all probes returned 404'}"
    )


REQUIRED_COLUMNS: tuple[str, ...] = ("ticker", "category", "quality_pct")


def _validate_picks_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise FetcherError(f"picks parquet missing columns: {missing}")


def filter_core(df: pd.DataFrame) -> pd.DataFrame:
    """category == 'CORE' 서브셋."""
    if df is None or df.empty:
        return df
    return df[df["category"] == "CORE"].copy()
