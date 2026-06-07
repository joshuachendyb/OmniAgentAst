"""
测试聊天数据库模块
验证 db/database.py 和 db/models/chat_models.py 的正确性

Author: 小沈 - 2026-05-22
"""
import sqlite3
import pytest
from pathlib import Path
from app.db import db
from app.db.database import DatabaseManager
from app.db.models.chat_models import (
    Session,
    Message,
    SessionCreate,
    SessionResponse,
    SessionListResponse,
    BatchTitleResponse,
    MessageResponse,
)


def test_chat_db_path_exists():
    """测试聊天数据库文件路径"""
    chat_path = db._db_paths["chat"]
    assert chat_path.name == "chat_history.db"
    assert ".omniagent" in str(chat_path)


def test_get_connection():
    """测试获取数据库连接"""
    with db.get_conn("chat") as conn:
        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory == sqlite3.Row
        
        # 验证WAL模式
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"


def test_init_database():
    """测试数据库初始化"""
    db.init()
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        
        # 检查 chat_sessions 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'")
        assert cursor.fetchone() is not None
        
        # 检查 chat_messages 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'")
        assert cursor.fetchone() is not None
        
        # 检查 chat_session_title_history 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_session_title_history'")
        assert cursor.fetchone() is not None


def test_session_model():
    """测试Session模型"""
    session = Session(
        id="test-session-id",
        title="Test Session",
        created_at="2026-05-22T00:00:00Z",
        updated_at="2026-05-22T00:00:00Z",
        message_count=5
    )
    assert session.id == "test-session-id"
    assert session.title == "Test Session"
    assert session.message_count == 5


def test_message_model():
    """测试Message模型"""
    message = Message(
        id=1,
        session_id="test-session-id",
        role="user",
        content="Hello",
        timestamp="2026-05-22T00:00:00Z"
    )
    assert message.id == 1
    assert message.session_id == "test-session-id"
    assert message.role == "user"
    assert message.content == "Hello"


def test_session_create_model():
    """测试SessionCreate模型"""
    # 不传参数
    session_create1 = SessionCreate()
    assert session_create1.title is None
    assert session_create1.is_valid is False
    
    # 传参数
    session_create2 = SessionCreate(title="New Session", is_valid=True)
    assert session_create2.title == "New Session"
    assert session_create2.is_valid is True


def test_session_response_model():
    """测试SessionResponse模型"""
    response = SessionResponse(
        session_id="test-session-id",
        title="Test Session",
        created_at="2026-05-22T00:00:00Z",
        updated_at="2026-05-22T00:00:00Z",
        message_count=5,
        is_valid=True
    )
    assert response.session_id == "test-session-id"
    assert response.is_valid is True


def test_message_response_model():
    """测试MessageResponse模型"""
    response = MessageResponse(
        id=1,
        session_id="test-session-id",
        role="assistant",
        content="Response",
        timestamp=1716336000000,  # 毫秒时间戳
        execution_steps=[{"step": 1}],
        display_name="gpt-4"
    )
    assert response.id == 1
    assert response.timestamp == 1716336000000
    assert response.execution_steps == [{"step": 1}]
    assert response.display_name == "gpt-4"
