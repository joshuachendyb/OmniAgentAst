"""P8-03: 大消息量性能 — mock测试

测试场景: 批量插入50条消息在查询,响应时间合理
-- 小欧 2026-07-03
"""
import pytest
import time
import sqlite3
import uuid
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
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            execution_steps TEXT,
            display_name TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);
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
        conn = sqlite3.connect(db_path)
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


def test_bulk_insert_and_query_performance(chat_db):
    session_id = str(uuid.uuid4())

    # Create session
    with sqlite3.connect(chat_db) as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, created_at, updated_at, version) VALUES (?, ?, ?, ?, ?)",
            (session_id, "批量测试", "2026-07-03T00:00:00Z", "2026-07-03T00:00:00Z", 1),
        )
        conn.commit()

    # Bulk insert 50 messages
    insert_start = time.time()
    with sqlite3.connect(chat_db) as conn:
        for i in range(50):
            conn.execute(
                "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
                (
                    session_id,
                    "user" if i % 2 == 0 else "assistant",
                    f"这是第{i+1}条测试消息,用于验证大消息量下的性能表现.消息内容包含一些填充文本以认保有足够的长度来模拟真实场景.",
                    "2026-07-03T00:00:00Z",
                ),
            )
        conn.commit()
    insert_elapsed = time.time() - insert_start

    # Query all messages
    query_start = time.time()
    with sqlite3.connect(chat_db) as conn:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id=? ORDER BY timestamp ASC",
            (session_id,),
        ).fetchall()
    query_elapsed = time.time() - query_start

    msg_count = len(rows)
    assert msg_count == 50, f"应有50条消息, got {msg_count}"
    assert query_elapsed < 5, f"查询响应应<5s, got {query_elapsed:.2f}s"
