"""Arena 전역 설정 및 상수."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- 자본/벤치마크 ---
INITIAL_CAPITAL: float = 100_000.0
BENCHMARK_TICKER: str = "SPY"
LEAGUE_START_DATE: str = "2026-04-24"

# --- 섹터 ETF 유니버스 ---
SECTOR_ETFS: list[str] = [
    "XLK", "XLF", "XLV", "XLE", "XLI",
    "XLY", "XLP", "XLU", "XLRE", "XLB", "XLC",
]

# --- 경로 ---
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"
LEAGUE_DIR: Path = DATA_DIR / "league"
BACKUP_DIR: Path = DATA_DIR / "backups"
DB_PATH: Path = Path(os.environ.get("ARENA_DB_PATH", DATA_DIR / "arena.db"))

BACKUP_RETENTION: int = 7

for _d in (DATA_DIR, LEAGUE_DIR, BACKUP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

HISTORY_PATH: Path = LEAGUE_DIR / "history.parquet"

# --- 외부 소스 ---
RAW_URL_BASE: str = os.environ.get(
    "STOCK_ENGINE_RAW_URL",
    "https://raw.githubusercontent.com/nanowon/ai-stock-selector/main",
)
STAGE2_PICKS_URL_TEMPLATE: str = RAW_URL_BASE.rstrip("/") + "/data/tracking/picks_{date}.parquet"
FETCH_TIMEOUT_SEC: int = 30
FETCH_MAX_LOOKBACK_DAYS: int = 7  # 최근 영업일부터 7일까지 후퇴해 가며 fetch 시도

# --- 알림 ---
DISCORD_WEBHOOK_URL: str | None = os.environ.get("DISCORD_WEBHOOK_URL") or None
WEB_PUBLIC_URL: str = os.getenv("ARENA_WEB_URL", "https://nanowon.github.io/ai-trader-arena")
SMTP_HOST: str = os.getenv("SMTP_HOST", "")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")
EMAIL_FROM: str = os.getenv("ARENA_EMAIL_FROM", "")
EMAIL_TO: str = os.getenv("ARENA_EMAIL_TO", "")

# --- 리그 룰 상수 ---
TIER_THRESHOLDS: dict[str, float] = {"Q5": 0.80, "Q4": 0.60, "Q3": 0.40}
HIGH_VOL_HINT_KEYWORDS: tuple[str, ...] = ("고변동", "테마성")

AGENT_CONFIGS: dict[str, dict] = {
    "aggressive": {
        "allowed_tiers": ["Q5"],
        "position_pct_max": 0.30,
        "stop_loss_pct": -0.30,
        "use_pipeline_stop": False,
        "skip_high_vol": False,
        "max_positions": 4,
    },
    "balanced": {
        "allowed_tiers": ["Q3", "Q4", "Q5"],
        "position_pct_max": 0.15,
        "stop_loss_pct": None,
        "use_pipeline_stop": True,
        "skip_high_vol": False,
        "max_positions": 8,
    },
    "conservative": {
        "allowed_tiers": ["Q4", "Q5"],
        "position_pct_max": 0.10,
        "stop_loss_pct": None,
        "use_pipeline_stop": True,
        "skip_high_vol": True,
        "max_positions": 12,
    },
}
