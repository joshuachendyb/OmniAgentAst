"""
测试数据库配置模块
验证 db/database.py 的正确性

Author: 小沈 - 2026-05-22
"""
from pathlib import Path
from app.db import db


def test_db_dir_path():
    """测试数据库目录路径"""
    assert db._db_dir == Path.home() / ".omniagent"
    assert ".omniagent" in str(db._db_dir)


def test_chat_db_path():
    """测试聊天数据库路径"""
    assert db._db_paths["chat"] == db._db_dir / "chat_history.db"
    assert "chat_history.db" in str(db._db_paths["chat"])


def test_operations_db_path():
    """测试操作数据库路径"""
    assert db._db_paths["operations"] == db._db_dir / "operations.db"
    assert "operations.db" in str(db._db_paths["operations"])


def test_observer_db_path():
    """测试观察者数据库路径"""
    assert db._db_paths["observer"] == db._db_dir / "tool_observer.db"
    assert "tool_observer.db" in str(db._db_paths["observer"])


def test_ensure_db_dir():
    """测试确保数据库目录存在"""
    assert db._db_dir.exists()
