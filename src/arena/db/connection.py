"""DB 연결 관리.

WAL 모드, foreign_keys ON, synchronous=NORMAL.
컨텍스트매니저 connect()로 commit/rollback 자동 처리.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from arena import config


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
	"""sqlite3.Connection을 열고 PRAGMA를 설정해 반환한다."""
	path = db_path if db_path is not None else config.DB_PATH
	path = Path(path)
	path.parent.mkdir(parents=True, exist_ok=True)
	conn = sqlite3.connect(str(path))
	conn.row_factory = sqlite3.Row
	conn.execute("PRAGMA journal_mode=WAL")
	conn.execute("PRAGMA foreign_keys=ON")
	conn.execute("PRAGMA synchronous=NORMAL")
	return conn


@contextmanager
def connect(db_path: Path | None = None) -> Generator[sqlite3.Connection, None, None]:
	"""with 블록에서 commit/rollback을 자동 처리하는 컨텍스트매니저."""
	conn = get_connection(db_path)
	try:
		yield conn
		conn.commit()
	except Exception:
		conn.rollback()
		raise
	finally:
		conn.close()
