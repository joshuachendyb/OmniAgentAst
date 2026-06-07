"""
测试sessions.py和execution.py的数据库引用更新
验证迁移后的代码能够正常工作

Author: 小沈 - 2026-05-22
"""
import pytest
import sqlite3
from app.api.v1.sessions import router
from app.api.v1.execution import router as execution_router
from app.db import db


def test_sessions_router_exists():
    """测试sessions路由存在"""
    assert router is not None
    assert router.prefix == ""


def test_db_get_connection():
    """测试db.get_conn('chat')正常工作"""
    with db.get_conn("chat") as conn:
        assert conn is not None
        assert isinstance(conn, sqlite3.Connection)


def test_execution_router_exists():
    """测试execution路由存在"""
    assert execution_router is not None


def test_db_chat_tables_exist():
    """测试chat数据库表已创建"""
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'")
        assert cursor.fetchone() is not None
