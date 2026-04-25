"""pytest 공통 픽스처.

DB side-effect를 방지하기 위해 ARENA_DB_PATH를 임시 디렉터리로 리다이렉트한다.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """모든 테스트에서 arena.db가 tmp_path를 사용하도록 monkeypatch한다."""
    db_file = str(tmp_path / "test_arena.db")
    monkeypatch.setenv("ARENA_DB_PATH", db_file)
    # 이미 import된 config.DB_PATH도 패치
    import arena.config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", tmp_path / "test_arena.db")
