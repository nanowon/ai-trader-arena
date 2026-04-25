"""Phase 6-A notify 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def minimal_result() -> dict:
    """최소 result dict fixture."""
    return {
        "date": "2026-04-25",
        "agents": {
            "aggressive": {
                "equity_value": 5000.0,
                "total_value": 105000.0,
                "cash": 100000.0,
                "num_positions": 2,
            },
            "balanced": {
                "equity_value": 3000.0,
                "total_value": 103000.0,
                "cash": 100000.0,
                "num_positions": 1,
            },
        },
        "commentary": {
            "aggressive": ["XLK 매수: 강세 모멘텀 포착"],
            "balanced": ["XLF 매수: 섹터 RS 상위권"],
        },
        "weekly_review": {
            "today": "2026-04-25",
            "rankings": [
                {"agent": "aggressive", "return_pct": 0.05},
                {"agent": "balanced", "return_pct": 0.03},
            ],
            "spy_return_pct": 0.02,
            "note": "",
        },
    }


@pytest.fixture
def many_trades_result(minimal_result) -> dict:
    """매매 내역이 많은 결과 (코멘터리 다수)."""
    long_commentary = [f"trade line {i}" * 20 for i in range(30)]
    result = dict(minimal_result)
    result["commentary"] = {
        "aggressive": long_commentary,
        "balanced": long_commentary,
        "conservative": long_commentary,
    }
    return result


# --- test1: build_discord_payload 기본 동작 ---

def test_build_discord_payload_contains_content(minimal_result):
    from arena.notify.discord import build_discord_payload

    payload = build_discord_payload(minimal_result)

    assert "content" in payload
    content = payload["content"]
    assert "AI Trader Arena" in content
    assert "2026-04-25" in content
    assert len(content) <= 3800


# --- test2: build_discord_payload 3800자 초과 시 truncate ---

def test_build_discord_payload_truncates_long_content(many_trades_result):
    from arena.notify.discord import build_discord_payload

    payload = build_discord_payload(many_trades_result)

    assert "content" in payload
    assert len(payload["content"]) <= 3800


# --- test3: send_daily_summary webhook 없을 때 False 반환 ---

def test_send_daily_summary_no_webhook_returns_false(minimal_result, monkeypatch):
    import arena.config as cfg
    monkeypatch.setattr(cfg, "DISCORD_WEBHOOK_URL", None)

    from arena.notify.discord import send_daily_summary

    result = send_daily_summary(minimal_result, webhook_url=None)

    assert result is False


# --- test4: send_daily_summary requests.post mock → True 반환 ---

def test_send_daily_summary_success(minimal_result, monkeypatch):
    import arena.config as cfg
    monkeypatch.setattr(cfg, "DISCORD_WEBHOOK_URL", "https://discord.example.com/webhook/test")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None

    with patch("arena.notify.discord.requests.post", return_value=mock_resp) as mock_post:
        from arena.notify.discord import send_daily_summary
        result = send_daily_summary(minimal_result)

    assert result is True
    mock_post.assert_called_once()


# --- test5: build_email_section HTML 반환 + XSS 방어 ---

def test_build_email_section_html_and_xss(minimal_result):
    from arena.notify.email_section import build_email_section

    # XSS 공격 문자열 주입
    xss_result = dict(minimal_result)
    xss_result["date"] = "<script>alert('xss')</script>"

    html_body = build_email_section(xss_result)

    assert isinstance(html_body, str)
    assert "<table" in html_body
    # XSS 방어: < > 이스케이프
    assert "<script>" not in html_body
    assert "&lt;script&gt;" in html_body


# --- test6: send_email SMTP 자격증명 없을 때 False 반환 ---

def test_send_email_no_credentials_returns_false(monkeypatch):
    import arena.config as cfg
    monkeypatch.setattr(cfg, "SMTP_HOST", "")
    monkeypatch.setattr(cfg, "SMTP_USER", "")
    monkeypatch.setattr(cfg, "SMTP_PASS", "")
    monkeypatch.setattr(cfg, "EMAIL_TO", "")

    from arena.notify.email_section import send_email

    result = send_email("<p>test</p>")

    assert result is False
