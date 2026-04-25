"""정적 사이트 빌더 — Plotly + Jinja2 기반 대시보드 HTML 생성."""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
# docs/site 기본 출력 경로 (PROJECT_ROOT/docs/site)
_DEFAULT_DOCS_SITE_DIR = Path(__file__).resolve().parents[3] / "docs" / "site"


def _daily_returns(history: list[dict]) -> list[dict]:
	"""일별 에쿼티 이력에서 에이전트별 일간 수익률(%) 계산."""
	from collections import defaultdict
	by_agent: dict[str, list[dict]] = defaultdict(list)
	for row in history:
		by_agent[row["agent"]].append(row)
	result = []
	for agent, rows in by_agent.items():
		rows_sorted = sorted(rows, key=lambda r: r["date"])
		for i in range(1, len(rows_sorted)):
			prev_val = rows_sorted[i - 1]["total_value"]
			curr_val = rows_sorted[i]["total_value"]
			if prev_val and prev_val != 0:
				ret_pct = (curr_val - prev_val) / prev_val * 100.0
			else:
				ret_pct = 0.0
			result.append({
				"date": rows_sorted[i]["date"],
				"agent": agent,
				"daily_return": ret_pct,
			})
	return result


def _drawdowns(history: list[dict]) -> list[dict]:
	"""일별 에쿼티 이력에서 에이전트별 드로우다운(%) 계산."""
	if not history:
		return []
	from collections import defaultdict
	by_agent: dict[str, list[dict]] = defaultdict(list)
	for row in history:
		by_agent[row["agent"]].append(row)
	result = []
	for agent, rows in by_agent.items():
		rows_sorted = sorted(rows, key=lambda r: r["date"])
		peak = None
		for row in rows_sorted:
			val = row["total_value"] or 0.0
			if peak is None or val > peak:
				peak = val
			dd = (val - peak) / peak * 100.0 if peak else 0.0
			result.append({
				"date": row["date"],
				"agent": agent,
				"drawdown": dd,
			})
	return result


def _collect_data(conn: sqlite3.Connection) -> dict:
	"""9개 차트용 데이터 수집."""
	from arena.db.repositories import (
		load_all_positions,
		load_equity_history,
		load_latest_equity_per_agent,
		load_latest_factor_snapshots,
		load_recent_trades,
	)
	from arena.engine import weekly_review

	today = datetime.now(timezone.utc).date().isoformat()
	history = load_equity_history(conn, start_date="2000-01-01", end_date=today)
	positions = load_all_positions(conn)

	return {
		"chart1": history,
		"chart2": load_latest_equity_per_agent(conn),
		"chart3": _daily_returns(history),
		"chart4": _drawdowns(history),
		"chart5": positions,
		"chart6": load_recent_trades(conn, limit=50),
		"chart7": load_latest_factor_snapshots(conn, limit=20),
		"chart8": [p for p in positions if p.get("agent") == "etf_only"],
		"chart9": weekly_review.build(conn, today),
		"generated_at": datetime.now(timezone.utc).isoformat(),
	}


def _render(data: dict, template_dir: Path) -> str:
	"""Jinja2 템플릿으로 HTML 렌더링."""
	try:
		from jinja2 import Environment, FileSystemLoader
	except ImportError as exc:
		raise RuntimeError("jinja2 패키지가 필요합니다: pip install jinja2") from exc

	env = Environment(
		loader=FileSystemLoader(str(template_dir)),
		autoescape=True,
	)
	template = env.get_template("index.html")
	return template.render(data=data)


def build_site(
	db_path: Path | None = None,
	output_dir: Path | None = None,
) -> Path:
	"""대시보드 정적 사이트를 빌드한다.

	Returns:
		생성된 index.html 경로
	"""
	from arena import config

	if db_path is None:
		db_path = config.DB_PATH
	if output_dir is None:
		# config에 DOCS_SITE_DIR이 있으면 사용, 없으면 기본값
		output_dir = getattr(config, "DOCS_SITE_DIR", _DEFAULT_DOCS_SITE_DIR)

	output_dir = Path(output_dir)
	output_dir.mkdir(parents=True, exist_ok=True)

	conn = sqlite3.connect(str(db_path))
	conn.row_factory = sqlite3.Row
	try:
		from arena.db.migrations import run_migrations
		run_migrations(conn)
		data = _collect_data(conn)
	finally:
		conn.close()

	html = _render(data, _TEMPLATE_DIR)
	out_file = output_dir / "index.html"
	out_file.write_text(html, encoding="utf-8")

	(output_dir / "static").mkdir(parents=True, exist_ok=True)
	shutil.copy2(STATIC_DIR / "style.css", output_dir / "static" / "style.css")

	return out_file
