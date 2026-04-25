"""일요일 주간 회고."""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta

import pandas as pd

from arena.db.repositories import load_equity_history


def build(conn: sqlite3.Connection, today: str | date) -> dict:
	if isinstance(today, str):
		today_date = date.fromisoformat(today)
		today_iso = today
	else:
		today_date = today
		today_iso = today.isoformat()

	result: dict = {
		"today": today_iso,
		"rankings": [],
		"spy_return_pct": None,
		"note": "",
	}

	start = today_date - timedelta(days=7)
	rows = load_equity_history(conn, start.isoformat(), today_iso)

	if not rows:
		result["note"] = "히스토리 없음"
		return result

	df = pd.DataFrame(rows)
	df["date"] = pd.to_datetime(df["date"]).dt.date

	window = df[(df["date"] >= start) & (df["date"] <= today_date)].copy()
	if window.empty:
		result["note"] = "최근 7일 히스토리 없음"
		return result

	rankings: list[dict] = []
	for agent, sub in window.groupby("agent"):
		sub_sorted = sub.sort_values("date")
		first = sub_sorted.iloc[0]
		last = sub_sorted.iloc[-1]
		if float(first["total_value"]) > 0:
			ret = float(last["total_value"]) / float(first["total_value"]) - 1.0
		else:
			ret = 0.0
		rankings.append({"agent": agent, "return_pct": ret})

	rankings.sort(key=lambda r: r["return_pct"], reverse=True)
	result["rankings"] = rankings

	spy_window = window.dropna(subset=["spy_close"]).drop_duplicates(subset=["date"], keep="first")
	spy_window = spy_window.sort_values("date")
	if len(spy_window) >= 2:
		first_spy = float(spy_window.iloc[0]["spy_close"])
		last_spy = float(spy_window.iloc[-1]["spy_close"])
		if first_spy > 0:
			result["spy_return_pct"] = last_spy / first_spy - 1.0

	return result


def render_markdown(review: dict) -> str:
	parts = ["## 이번 주 리그 회고", ""]
	if review.get("note"):
		parts.append(f"_{review['note']}_")
		return "\n".join(parts) + "\n"

	rankings = review.get("rankings", [])
	if not rankings:
		parts.append("_데이터 부족_")
		return "\n".join(parts) + "\n"

	parts.append(f"기준일: {review.get('today', '')}")
	parts.append("")
	parts.append("| 순위 | 에이전트 | 주간 수익률 |")
	parts.append("|---:|---|---:|")
	for i, r in enumerate(rankings, 1):
		parts.append(f"| {i} | {r['agent']} | {r['return_pct']*100:+.2f}% |")
	spy = review.get("spy_return_pct")
	if spy is not None:
		parts.append(f"| - | SPY (baseline) | {spy*100:+.2f}% |")
	return "\n".join(parts) + "\n"
