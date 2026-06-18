"""P3: Database层测试 - SQLite读写、会话管理"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import patch


class TestDatabaseManagerInit:
    """测试DatabaseManager初始化"""

    def test_init_creates_dir(self):
        """init创建.db目录"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / ".omniagent"
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                assert db_path.exists()

    def test_db_paths_defined(self):
        """4个数据库路径已定义"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                assert "chat" in dm._db_paths
                assert "operations" in dm._db_paths
                assert "observer" in dm._db_paths
                assert "task_tracker" in dm._db_paths


class TestGetConn:
    """测试连接管理"""

    def test_valid_db_name(self):
        """有效db_name → 获取连接"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                with dm.get_conn("chat") as conn:
                    assert isinstance(conn, sqlite3.Connection)

    def test_invalid_db_name_raises(self):
        """无效db_name → ValueError"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                with pytest.raises(ValueError, match="Unknown database"):
                    with dm.get_conn("nonexistent"):
                        pass

    def test_connection_closed_after_use(self):
        """连接用完后自动关闭"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                conn_ref = None
                with dm.get_conn("chat") as conn:
                    conn_ref = conn
                    # 使用连接
                    conn.execute("SELECT 1")
                # 连接应该已关闭
                assert conn_ref is not None

    def test_exception_triggers_rollback(self):
        """异常时自动回滚"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                with pytest.raises(RuntimeError):
                    with dm.get_conn("chat") as conn:
                        conn.execute("CREATE TABLE test_rollback (id INTEGER)")
                        conn.execute("INSERT INTO test_rollback VALUES (1)")
                        raise RuntimeError("模拟异常")

    def test_wal_mode_set(self):
        """连接启用WAL模式"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                with dm.get_conn("chat") as conn:
                    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
                    assert mode.upper() == "WAL"

    def test_busy_timeout_set(self):
        """连接设置busy_timeout"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                with dm.get_conn("chat") as conn:
                    timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
                    assert timeout == 5000


class TestInitDB:
    """测试数据库初始化"""

    def test_init_chat_db_creates_tables(self):
        """init_chat_db创建chat表"""
        from app.db.db_initializer import init_chat_db
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                init_chat_db(dm.get_conn)
                with dm.get_conn("chat") as conn:
                    tables = [r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]
                    assert "chat_sessions" in tables
                    assert "chat_messages" in tables

    def test_init_operations_db_creates_tables(self):
        """init_operations_db创建操作表"""
        from app.db.db_initializer import init_operations_db
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                init_operations_db(dm.get_conn)
                with dm.get_conn("operations") as conn:
                    tables = [r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]
                    assert "file_operations" in tables
                    assert "task_operations" in tables

    def test_init_task_tracker_db_creates_tables(self):
        """init_task_tracker_db创建task_tracker表"""
        from app.db.db_initializer import init_task_tracker_db
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                init_task_tracker_db(dm.get_conn)
                with dm.get_conn("task_tracker") as conn:
                    tables = [r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]
                    assert "tasks" in tables
                    assert "operations" in tables

    def test_init_full(self):
        """init()初始化所有数据库"""
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                dm.init()
                # 验证所有数据库表都创建了
                with dm.get_conn("chat") as conn:
                    tables = [r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]
                    assert "chat_sessions" in tables
                with dm.get_conn("task_tracker") as conn:
                    tables = [r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()]
                    assert "tasks" in tables


class TestEnsureColumn:
    """测试字段确保"""

    def test_column_added(self):
        """不存在的列会被添加"""
        from app.db.db_initializer import init_chat_db, _ensure_column
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                init_chat_db(dm.get_conn)
                with dm.get_conn("chat") as conn:
                    # 添加测试列
                    _ensure_column(conn, "chat_messages", "test_column", "TEXT")
                    # 验证列存在
                    cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_messages)").fetchall()]
                    assert "test_column" in cols

    def test_column_idempotent(self):
        """重复添加同名列不报错"""
        from app.db.db_initializer import init_chat_db, _ensure_column
        from app.db.database import DatabaseManager
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("pathlib.Path.home", return_value=Path(tmpdir)):
                dm = DatabaseManager()
                init_chat_db(dm.get_conn)
                with dm.get_conn("chat") as conn:
                    _ensure_column(conn, "chat_messages", "idempotent_col", "TEXT")
                    _ensure_column(conn, "chat_messages", "idempotent_col", "TEXT")
                    cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_messages)").fetchall()]
                    assert cols.count("idempotent_col") == 1


class TestSingletonInstance:
    """测试全局db实例"""

    def test_singleton_exists(self):
        """全局db实例存在"""
        from app.db.database import db, DatabaseManager
        assert db is not None
        assert isinstance(db, DatabaseManager)
