"""Arena 전역 설정 및 상수."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- 자본/벤치마크 ---
INITIAL_CAPITAL: int = 100_000
BENCHMARK_TICKER: str = "SPY"

# --- 섹터 ETF 유니버스 ---
SECTOR_ETFS: list[str] = [
    "XLK", "XLF", "XLV", "XLE", "XLI",
    "XLY", "XLP", "XLU", "XLRE", "XLB", "XLC",
]

# --- 경로 ---
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DB_PATH: Path = Path(os.environ.get("ARENA_DB_PATH", PROJECT_ROOT / "data" / "arena.db"))

# --- 외부 소스 ---
RAW_URL_BASE: str = os.environ.get(
    "STOCK_ENGINE_RAW_URL",
    "https://raw.githubusercontent.com/nanowon/ai-stock-selector/main",
)

# --- 알림 ---
DISCORD_WEBHOOK_URL: str | None = os.environ.get("DISCORD_WEBHOOK_URL") or None
