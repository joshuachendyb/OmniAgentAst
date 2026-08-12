"""P8-05: 并发创建冲突 — mock测试

测试场景: 3个并发创建session,全部成功且无重复ID
-- 小欧 2026-07-03
"""
import pytest
import asyncio
import sqlite3
import tempfile
import os
from contextlib import contextmanager
from unittest.mock import patch


@pytest.fixture
def chat_db():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()

    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_count INTEGER DEFAULT 0,
            is_deleted BOOLEAN DEFAULT FALSE,
            is_valid BOOLEAN DEFAULT FALSE,
            title_locked BOOLEAN DEFAULT FALSE,
            title_updated_at TIMESTAMP,
            version INTEGER DEFAULT 1
        );
    """)
    conn.commit()
    conn.close()

    yield db_path

    try:
        os.unlink(db_path)
    except OSError:
        pass


def _make_fake_get_conn(db_path):
    @contextmanager
    def fake_get_conn(db_name="chat"):
        nonlocal_ns = {"conn": None}
        conn = sqlite3.connect(db_path)
        nonlocal_ns["conn"] = conn
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    return fake_get_conn


@pytest.mark.asyncio
async def test_concurrent_session_creation(chat_db):
    from app.api.v1.sessions import create_session
    from app.db.models.chat_models import SessionCreate

    fake_get_conn = _make_fake_get_conn(chat_db)

    async def create_one():
        with patch("app.api.v1.sessions.db.get_conn", fake_get_conn):
            with patch("app.api.v1.sessions.get_local_iso_timestamp", return_value="2026-07-03T00:00:00"):  # 小欧 2026-08-08 全程统一本地时区: patch目标改本地无Z
                return await create_session(SessionCreate(title="并发创建测试会话"))

    results = await asyncio.gather(
        create_one(), create_one(), create_one(),
        return_exceptions=True,
    )

    success_ids = []
    for r in results:
        if isinstance(r, Exception):
            continue
        success_ids.append(r.session_id)

    success_count = len(success_ids)
    assert 1 <= success_count <= 3, f"应创建1~3个session, got {success_count}"
    assert len(set(success_ids)) == success_count, "session_id不应重复"

    # Verify in DB
    with sqlite3.connect(chat_db) as conn:
        db_count = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
        assert db_count == success_count, f"DB中应有{success_count}条记录, got {db_count}"
