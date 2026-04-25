"""Email 요약 HTML 섹션 빌더 및 SMTP 발송."""
from __future__ import annotations

import html
import logging
import smtplib
from email.message import EmailMessage

from arena import config

log = logging.getLogger(__name__)


def _fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.2f}%"


def build_email_section(result: dict) -> str:
    """result dict로부터 HTML 요약 섹션을 빌드한다.

    에이전트 성과 테이블 + 코멘터리 + 웹 링크를 포함한 HTML 문자열을 반환.
    html.escape로 XSS 방어.
    """
    date_str = html.escape(result.get("date", "unknown"))
    agents: dict = result.get("agents") or {}
    commentary: dict = result.get("commentary") or {}
    weekly_review = result.get("weekly_review")
    web_url = html.escape(config.WEB_PUBLIC_URL)

    parts: list[str] = []
    parts.append(f"<h2>AI Trader Arena — {date_str}</h2>")

    # 에이전트 성과 테이블
    if agents:
        parts.append("<h3>에이전트 성과</h3>")
        parts.append(
            "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>"
        )
        parts.append(
            "<tr><th>에이전트</th><th>총자산</th><th>현금</th><th>포지션 수</th></tr>"
        )
        for name, ev in agents.items():
            total = ev.get("total_value", 0.0)
            cash = ev.get("cash", 0.0)
            num_pos = ev.get("num_positions", 0)
            parts.append(
                f"<tr>"
                f"<td>{html.escape(str(name))}</td>"
                f"<td>{total:,.0f}</td>"
                f"<td>{cash:,.0f}</td>"
                f"<td>{num_pos}</td>"
                f"</tr>"
            )
        parts.append("</table>")
        parts.append("<br>")

    # 코멘터리
    if commentary:
        parts.append("<h3>코멘터리</h3>")
        parts.append("<ul>")
        for name, cmts in commentary.items():
            first = cmts[0] if cmts else "특이사항 없음"
            parts.append(
                f"<li><strong>{html.escape(str(name))}</strong>: {html.escape(str(first))}</li>"
            )
        parts.append("</ul>")

    # 주간 리뷰
    if weekly_review and weekly_review.get("rankings"):
        parts.append("<h3>주간 순위</h3>")
        parts.append(
            "<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse;'>"
        )
        parts.append("<tr><th>순위</th><th>에이전트</th><th>주간 수익률</th></tr>")
        for i, r in enumerate(weekly_review["rankings"], 1):
            parts.append(
                f"<tr>"
                f"<td>{i}</td>"
                f"<td>{html.escape(str(r['agent']))}</td>"
                f"<td>{_fmt_pct(r['return_pct'])}</td>"
                f"</tr>"
            )
        parts.append("</table>")
        parts.append("<br>")

    # 웹 링크
    parts.append(f"<p><a href='{web_url}'>Arena 대시보드 보기</a></p>")

    return "\n".join(parts)


def send_email(
    html_body: str,
    subject: str = "AI Trader Arena Daily",
    **kwargs,
) -> bool:
    """SMTP를 통해 HTML 이메일을 발송한다.

    SMTP_HOST / SMTP_USER / SMTP_PASS / EMAIL_TO 중 하나라도 없으면 skip + warning.
    포트 465이면 SMTP_SSL, 그 외에는 SMTP + starttls.
    실패 시 예외를 전파하지 않고 warning + False 반환.
    """
    smtp_host = config.SMTP_HOST
    smtp_port = config.SMTP_PORT
    smtp_user = config.SMTP_USER
    smtp_pass = config.SMTP_PASS
    email_from = config.EMAIL_FROM or smtp_user
    email_to = config.EMAIL_TO

    if not all([smtp_host, smtp_user, smtp_pass, email_to]):
        log.warning(
            "email: SMTP 자격증명이 불완전합니다. "
            "SMTP_HOST / SMTP_USER / SMTP_PASS / ARENA_EMAIL_TO env를 확인하세요."
        )
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = email_to
    msg.set_content("HTML 이메일을 지원하는 클라이언트로 확인하세요.")
    msg.add_alternative(html_body, subtype="html")

    try:
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log.warning("email: 발송 실패: %s", e)
        return False
