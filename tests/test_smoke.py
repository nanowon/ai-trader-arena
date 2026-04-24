"""Phase 0 smoke tests — 기본 import 및 CLI 파서 로드 검증."""
from __future__ import annotations


def test_arena_imports():
    import arena
    assert arena.__version__ == "0.1.0"


def test_cli_help_runs():
    from arena.cli import _build_parser, main  # noqa: F401
    parser = _build_parser()
    # argparse parser 가 정상 구성되는지 확인
    assert parser.prog == "arena"
