"""picks 데이터 진단 스크립트.

사용법:
    python scripts/diagnose_picks.py
    python scripts/diagnose_picks.py --date 2026-04-24
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from arena.data.fetcher import fetch_picks, filter_core


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="ISO date (default: today)")
    args = parser.parse_args()

    target_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
    )

    print(f"=== picks 진단: {target_date} ===\n")

    gh_token = os.environ.get("GH_TOKEN", "").strip()
    if not gh_token:
        print("⚠  GH_TOKEN 환경변수가 없습니다. private repo라면 토큰이 필요합니다.\n")
    else:
        try:
            gh_token.encode("latin-1")
            print(f"✅ GH_TOKEN 감지됨 (길이={len(gh_token)}, 앞4자: {gh_token[:4]}****)\n")
        except UnicodeEncodeError:
            bad_positions = [i for i, c in enumerate(gh_token) if ord(c) > 255]
            print(
                f"❌ GH_TOKEN에 비ASCII 문자가 있습니다! "
                f"위치: {bad_positions}, 문자: {[gh_token[i] for i in bad_positions]}\n"
                f"   → 토큰을 다시 복사해서 $env:GH_TOKEN에 설정하세요.\n"
            )
            return

    try:
        r = fetch_picks(target_date)
    except Exception as e:
        print(f"❌ fetch_picks 실패: {e}")
        return

    df = r.df
    print(f"✅ 스냅샷 날짜 : {r.snapshot_date}")
    print(f"✅ 전체 종목 수 : {len(df)}")
    print(f"✅ 컬럼 목록    : {list(df.columns)}\n")

    print("── category 분포 ──")
    print(df["category"].value_counts().to_string())
    print()

    core = filter_core(df)
    print(f"── CORE 종목 수: {len(core)} ──")

    if core.empty:
        print("❌ CORE 종목이 없습니다. → 매수 후보 없음 (거래 0건 원인)")
        return

    print("\n── quality_pct 분포 (CORE) ──")
    print(core["quality_pct"].describe().to_string())
    print()

    thresholds = {"Q5": 0.80, "Q4": 0.60, "Q3": 0.40}
    for tier, thr in sorted(thresholds.items(), key=lambda x: -x[1]):
        cnt = (core["quality_pct"] >= thr).sum()
        print(f"  {tier} (≥{thr:.0%}): {cnt}개")
    below_q3 = (core["quality_pct"] < 0.40).sum()
    print(f"  Q3 미달 (<40%): {below_q3}개\n")

    print("── entry_price 분포 (CORE) ──")
    if "entry_price" not in core.columns:
        print("❌ entry_price 컬럼 없음 → 모든 매수 스킵됨")
        return

    ep = core["entry_price"]
    print(f"  NaN: {ep.isna().sum()}개  |  0 이하: {(ep.fillna(0) <= 0).sum()}개  |  유효: {(ep > 0).sum()}개")
    print()
    print(ep.describe().to_string())
    print()

    # 에이전트별 매수 가능 종목 시뮬레이션
    agent_cfgs = {
        "aggressive":  {"allowed_tiers": {"Q5"},        "max_positions": 4},
        "balanced":    {"allowed_tiers": {"Q3","Q4","Q5"}, "max_positions": 8},
        "conservative":{"allowed_tiers": {"Q4","Q5"},   "max_positions": 12},
    }
    print("── 에이전트별 매수 가능 후보 수 ──")
    for name, cfg in agent_cfgs.items():
        cands = core[ep > 0].copy()
        counts = []
        for tier, thr in [("Q5",0.80),("Q4",0.60),("Q3",0.40)]:
            if tier in cfg["allowed_tiers"]:
                cnt = (cands["quality_pct"] >= thr).sum()
                counts.append(f"{tier}: {cnt}")
        total = sum(
            (cands["quality_pct"] >= thr).sum()
            for tier, thr in [("Q5",0.80),("Q4",0.60),("Q3",0.40)]
            if tier in cfg["allowed_tiers"]
        )
        print(f"  {name:15s}: {total}개  ({', '.join(counts)})")

    print()
    if len(core[ep > 0]) == 0:
        print("❌ entry_price > 0 인 CORE 종목이 없습니다. → 거래 0건 원인")
    else:
        print("✅ 후보 종목 존재. 첫 5개 확인:")
        preview_cols = ["ticker", "category", "quality_pct", "entry_price"]
        available = [c for c in preview_cols if c in core.columns]
        print(core[core["entry_price"] > 0][available].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
