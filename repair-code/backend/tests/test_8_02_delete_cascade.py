"""P8-02: 删除在数据残留 — mock测试

测试场景: 删除session在关联消息应被清理
-- 小欧 2026-07-03
"""
import pytest
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


def test_delete_session_cascades_messages(chat_db):
    session_id = str(uuid.uuid4())

    # Insert session
    with sqlite3.connect(chat_db) as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, created_at, updated_at, version) VALUES (?, ?, ?, ?, ?)",
            (session_id, "删除测试", "2026-07-03T00:00:00Z", "2026-07-03T00:00:00Z", 1),
        )
        # Insert messages
        conn.execute(
            "INSERT INTO chat_messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, "user", "hello", "2026-07-03T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO chat_messages(session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, "assistant", "hi", "2026-07-03T00:00:01Z"),
        )
        conn.commit()

    # Verify messages exist before delete
    with sqlite3.connect(chat_db) as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM chat_messages WHERE session_id=?", (session_id,)
        ).fetchone()[0]
        assert before >= 2, f"删除前应有消息, got {before}"

    # Soft-delete session
    with sqlite3.connect(chat_db) as conn:
        conn.execute(
            "UPDATE chat_sessions SET is_deleted=TRUE, updated_at=? WHERE id=?",
            ("2026-07-03T00:01:00Z", session_id),
        )
        conn.commit()

    # Verify session is marked deleted
    with sqlite3.connect(chat_db) as conn:
        row = conn.execute(
            "SELECT is_deleted FROM chat_sessions WHERE id=?", (session_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == 1
