"""P8-01: 并发更新竞争 — mock测试

测试场景: 2个并发session title更新,最终值为预期之一
-- 小欧 2026-07-03
"""
import pytest
import asyncio
import sqlite3
import uuid
import tempfile
import os


@pytest.fixture
def chat_db():
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
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


@pytest.mark.asyncio
async def test_concurrent_session_title_update(chat_db):
    session_id = str(uuid.uuid4())

    # Insert a session
    with sqlite3.connect(chat_db) as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, created_at, updated_at, version) VALUES (?, ?, ?, ?, ?)",
            (session_id, "初始标题", "2026-07-03T00:00:00Z", "2026-07-03T00:00:00Z", 1),
        )
        conn.commit()

    # Concurrent updates
    async def update_title(name):
        def _do():
            with sqlite3.connect(chat_db, timeout=10) as conn:
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute(
                    "UPDATE chat_sessions SET title=?, updated_at=? WHERE id=? AND version=1",
                    (name, "2026-07-03T00:01:00Z", session_id),
                )
                conn.commit()
                return conn.total_changes
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _do)

    results = await asyncio.gather(
        update_title("并发更新测试-A"),
        update_title("并发更新测试-B"),
        return_exceptions=True,
    )

    success_count = sum(1 for r in results if not isinstance(r, Exception))
    assert success_count >= 1, f"至少1个更新应成功, got {results}"

    with sqlite3.connect(chat_db) as conn:
        row = conn.execute("SELECT title FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
        final_title = row[0] if row else ""
        assert final_title in ("并发更新测试-A", "并发更新测试-B"), f"最终title应为预期值之一, got {final_title}"
