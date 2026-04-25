"""picks parquet 스키마 검증.

ai-stock-engine이 산출하는 stage2 picks parquet의 컬럼 변경을
arena가 silent하게 받지 않도록 사전 검증한다. 누락 시 즉시 명시적 실패.

orchestrator의 fetch_picks 직후, filter_core 직전에 호출 권장.
"""
from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd

log = logging.getLogger(__name__)


# 필수 컬럼 — 누락 시 SchemaError
REQUIRED_COLUMNS: tuple[str, ...] = (
    "ticker",
    "category",
    "quality_pct",
)

# 권장 컬럼 — 누락 시 warning만
RECOMMENDED_COLUMNS: tuple[str, ...] = (
    "timing_pct",
    "combined_z",
    "sector",
    "snapshot_date",
)

# arena가 자체적으로 채우는 컬럼 (없어도 되는 컬럼)
INJECTED_COLUMNS: tuple[str, ...] = (
    "entry_price",      # current_closes에서 주입
    "hint_tag",         # sector에서 파생
)


class SchemaError(RuntimeError):
    """picks parquet 스키마 검증 실패."""


def validate_picks_schema(
    df: pd.DataFrame,
    required: Iterable[str] = REQUIRED_COLUMNS,
    recommended: Iterable[str] = RECOMMENDED_COLUMNS,
) -> None:
    """picks DataFrame의 스키마를 검증한다.

    Args:
        df: fetch_picks가 반환한 DataFrame
        required: 누락 시 SchemaError를 던질 컬럼 목록
        recommended: 누락 시 warning을 로깅할 컬럼 목록

    Raises:
        SchemaError: 필수 컬럼이 누락된 경우
    """
    if df is None:
        raise SchemaError("picks DataFrame is None")

    columns = set(df.columns)

    missing_required = [c for c in required if c not in columns]
    if missing_required:
        raise SchemaError(
            f"picks parquet missing required columns: {missing_required}. "
            f"available: {sorted(columns)}"
        )

    missing_recommended = [c for c in recommended if c not in columns]
    if missing_recommended:
        log.warning(
            "picks parquet missing recommended columns: %s",
            missing_recommended,
        )
