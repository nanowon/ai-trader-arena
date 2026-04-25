"""Discord webhook 일일 요약 알림."""
from __future__ import annotations

import logging
import re

import requests

from arena import config

log = logging.getLogger(__name__)

_DISCORD_ESCAPE_RE = re.compile(r"([@#`*_~|\\])")


def _escape(text: str) -> str:
    """Discord 민감 문자 이스케이프."""
    return _DISCORD_ESCAPE_RE.sub(r"\\\1", str(text))


def _fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def build_discord_payload(result: dict) -> dict:
    """result dict로부터 Discord content 문자열을 빌드한다.

    반환: {"content": "..."}
    """
    date_str = result.get("date", "unknown")
    agents: dict = result.get("agents") or {}
    commentary: dict = result.get("commentary") or {}
    weekly_review = result.get("weekly_review")

    lines: list[str] = []

    # 헤더
    lines.append(f"\U0001f916 **AI Trader Arena** — {_escape(date_str)}")
    lines.append("")

    # 에이전트 성과 테이블
    if agents:
        col_w = [12, 14, 12]
        header = f"{'에이전트':<{col_w[0]}} {'총자산':>{col_w[1]}} {'현금':>{col_w[2]}}"
        sep = "-" * (sum(col_w) + 2)
        rows_txt: list[str] = [header, sep]
        for name, ev in agents.items():
            total = ev.get("total_value", 0.0)
            cash = ev.get("cash", 0.0)
            name_col = _escape(name).ljust(col_w[0])
            total_col = f"{total:,.0f}".rjust(col_w[1])
            cash_col = f"{cash:,.0f}".rjust(col_w[2])
            rows_txt.append(f"{name_col} {total_col} {cash_col}")
        lines.append("```")
        lines.extend(rows_txt)
        lines.append("```")
        lines.append("")

    # 코멘터리 (에이전트별 1줄)
    if commentary:
        lines.append("**코멘터리**")
        for name, cmts in commentary.items():
            first = cmts[0] if cmts else "특이사항 없음"
            lines.append(f"• **{_escape(name)}**: {_escape(first)}")
        lines.append("")

    # 주간 리뷰
    if weekly_review and weekly_review.get("rankings"):
        lines.append("**\U0001f3c6 주간 순위**")
        for i, r in enumerate(weekly_review["rankings"], 1):
            lines.append(
                f"{i}. {_escape(r['agent'])} — {_fmt_pct(r['return_pct'])}"
            )
        lines.append("")

    # 웹 링크
    lines.append(f"\U0001f517 {config.WEB_PUBLIC_URL}")

    content = "\n".join(lines)

    # 3800자 초과 시 코멘터리 섹션 먼저 truncate
    if len(content) > 3800:
        # 코멘터리 없이 재빌드
        lines2: list[str] = []
        lines2.append(f"\U0001f916 **AI Trader Arena** — {_escape(date_str)}")
        lines2.append("")
        if agents:
            lines2.append("```")
            lines2.extend(rows_txt)
            lines2.append("```")
            lines2.append("")
        if weekly_review and weekly_review.get("rankings"):
            lines2.append("**\U0001f3c6 주간 순위**")
            for i, r in enumerate(weekly_review["rankings"], 1):
                lines2.append(f"{i}. {_escape(r['agent'])} — {_fmt_pct(r['return_pct'])}")
            lines2.append("")
        lines2.append(f"\U0001f517 {config.WEB_PUBLIC_URL}")
        content = "\n".join(lines2)

    # 여전히 초과하면 강제 절단
    if len(content) > 3800:
        content = content[:3797] + "..."

    return {"content": content}


def send_daily_summary(result: dict, webhook_url: str | None = None) -> bool:
    """Discord webhook으로 일일 요약을 전송한다.

    webhook_url이 없으면 config.DISCORD_WEBHOOK_URL을 사용.
    둘 다 없으면 warning 후 False 반환.
    실패 시 예외를 전파하지 않고 warning + False 반환.
    """
    url = webhook_url or config.DISCORD_WEBHOOK_URL
    if not url:
        log.warning("discord: webhook URL이 설정되지 않았습니다. DISCORD_WEBHOOK_URL env를 확인하세요.")
        return False

    payload = build_discord_payload(result)
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("discord: 전송 실패: %s", e)
        return False
