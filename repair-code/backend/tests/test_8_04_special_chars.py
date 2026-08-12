"""P8-04: 特殊字符处理 — mock测试

测试场景: 特殊字符能正常保存和读取
-- 小欧 2026-07-03
"""
import pytest
import sqlite3
import uuid
import tempfile
import os
import json


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


def test_special_chars_in_session_and_message(chat_db):
    session_id = str(uuid.uuid4())
    special_title = "<script>alert(1)</script><b>bold</b>'\"&<>"

    # Insert session with special chars
    with sqlite3.connect(chat_db) as conn:
        conn.execute(
            "INSERT INTO chat_sessions (id, title, created_at, updated_at, version) VALUES (?, ?, ?, ?, ?)",
            (session_id, special_title, "2026-07-03T00:00:00Z", "2026-07-03T00:00:00Z", 1),
        )
        conn.commit()

    # Verify title stored correctly
    with sqlite3.connect(chat_db) as conn:
        row = conn.execute("SELECT title FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
        assert row is not None
        stored_title = row[0]
        assert stored_title == special_title, f"title应原样存储, got {stored_title!r}"

    # Insert message with special chars
    special_content = "特殊字符测试: <script>alert('xss')</script> & \" ' < >"
    with sqlite3.connect(chat_db) as conn:
        conn.execute(
            "INSERT INTO chat_messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, "user", special_content, "2026-07-03T00:01:00Z"),
        )
        conn.commit()

    # Verify message stored correctly
    with sqlite3.connect(chat_db) as conn:
        row = conn.execute(
            "SELECT content FROM chat_messages WHERE session_id=? ORDER BY id DESC",
            (session_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == special_content, f"消息应原样存储, got {row[0]!r}"
        assert "<script>" in row[0]
