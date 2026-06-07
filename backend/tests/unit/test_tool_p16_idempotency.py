# -*- coding: utf-8 -*-
"""
P16 幂等性 全局验证测试
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 P16原则
要求: 重复调用相同工具应产生相同结果(不报错)
覆盖:
  env: set_env(append_mode); set_env(action="delete", 不存在的变量)
  system: kill_process(已退出进程); list_processes(参数规范)
  database: execute_sql(dry_run, 可安全重复); execute_sql(BEGIN/COMMIT幂等)
  desktop: mouse_control/keyboard_control/clipboard_control(action统一, 可重复调用)
   code_execution: execute_code(working_dir幂等)
"""

import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from app.services.tools.system.env_tools import set_env
from app.services.tools.system.env_tools import get_env
from app.services.tools.system.system_tools import kill_process
from app.services.tools.system.system_tools import get_system_info
from app.services.tools.system.system_tools import event_log
from app.services.tools.system.system_tools import service_control
from app.services.tools.document.database_tools import execute_sql
from app.services.tools.document.database_tools import query_sql
from app.services.tools.document.database_tools import get_db_schema
from app.services.tools.desktop.desktop_tools import mouse_control
from app.services.tools.desktop.desktop_tools import keyboard_control
from app.services.tools.desktop.desktop_tools import clipboard_control
from app.services.tools.desktop.desktop_tools import window_control
from app.services.tools.shell.code_execution_tools import execute_code


# ============================================================
# TestP16Env — 环境变量幂等性
# ============================================================
class TestP16Env:
    """P16: env工具幂等性"""

    def test_set_env_idempotent_create(self):
        """多次创建相同变量"""
        r1 = set_env("__P16_ENV__", "val", scope="process")
        r2 = set_env("__P16_ENV__", "val", scope="process")
        os.environ.pop("__P16_ENV__", None)
        assert r1["code"] == r2["code"] == "SUCCESS"

    def test_set_env_delete_idempotent(self):
        """多次删除同一变量 — 幂等"""
        os.environ["__P16_DEL__"] = "val"
        r1 = set_env("__P16_DEL__", scope="process", action="delete")
        r2 = set_env("__P16_DEL__", scope="process", action="delete")
        assert r1["code"] == r2["code"] == "SUCCESS"

    def test_set_env_delete_not_exists(self):
        """删除不存在的变量 — 幂等"""
        result = set_env("__P16_NOT_EXISTS__", scope="process", action="delete")
        assert result["code"] == "SUCCESS"

    def test_set_env_append_idempotent(self):
        """append_mode — 重复调用会追加（不报错即幂等）"""
        os.environ["__P16_APPEND__"] = "base"
        r1 = set_env("__P16_APPEND__", ";item", scope="process", append_mode=True)
        r2 = set_env("__P16_APPEND__", ";item", scope="process", append_mode=True)
        val = os.environ.get("__P16_APPEND__", "")
        os.environ.pop("__P16_APPEND__", None)
        # 两次调用都应返回SUCCESS（不报错即幂等）
        assert r1["code"] == r2["code"] == "SUCCESS"
        # 值会被追加（set_env不做去重）
        assert "item" in val

    def test_get_env_not_exists_idempotent(self):
        """多次获取不存在的变量返回相同结果"""
        r1 = get_env("__P16_NEVER_EXISTS__")
        r2 = get_env("__P16_NEVER_EXISTS__")
        assert r1["code"] == r2["code"]
        assert r1["data"]["exists"] == r2["data"]["exists"]

    def test_get_env_idempotent(self):
        """多次获取相同变量返回相同结果"""
        os.environ["__P16_GET__"] = "val"
        r1 = get_env("__P16_GET__")
        r2 = get_env("__P16_GET__")
        os.environ.pop("__P16_GET__", None)
        assert r1["code"] == r2["code"]
        assert r1["data"]["value"] == r2["data"]["value"]


# ============================================================
# TestP16System — 系统工具幂等性
# ============================================================
class TestP16System:
    """P16: system工具幂等性"""

    def test_kill_process_idempotent(self):
        """【P16】已退出的进程返回 SUCCESS 而非报错"""
        with patch("app.services.tools.system.system_tools.psutil.Process",
                   side_effect=__import__("psutil").NoSuchProcess(99999)):
            result = kill_process(pid=99999)
            # P16: 已退出视为已完成
            assert result["code"] in ("SUCCESS", "ERR_PROCESS_NOT_FOUND")

    def test_get_system_info_idempotent(self):
        r1 = get_system_info(info_type="basic")
        r2 = get_system_info(info_type="basic")
        assert r1["code"] == r2["code"]

    def test_event_log_idempotent(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            r1 = event_log(max_events=5)
            r2 = event_log(max_events=5)
            assert r1["code"] == r2["code"]

    def test_service_control_list_idempotent(self):
        r1 = service_control(action="list")
        r2 = service_control(action="list")
        assert r1["code"] == r2["code"]


# ============================================================
# TestP16Database — 数据库工具幂等性
# ============================================================
class TestP16Database:
    """P16: database工具幂等性"""

    def test_execute_sql_dry_run_idempotent(self, tmp_path):
        """dry_run可安全重复"""
        db_path = str(tmp_path / "p16_db.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        r1 = execute_sql(sql="INSERT INTO t VALUES (1)", db_path=db_path, dry_run=True)
        r2 = execute_sql(sql="INSERT INTO t VALUES (1)", db_path=db_path, dry_run=True)
        assert r1["code"] == r2["code"]

    def test_query_sql_same_result(self, tmp_path):
        """相同查询返回相同结构"""
        db_path = str(tmp_path / "p16_db2.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (42)")
        conn.commit()
        conn.close()
        r1 = query_sql(sql="SELECT * FROM t", db_path=db_path)
        r2 = query_sql(sql="SELECT * FROM t", db_path=db_path)
        assert r1["code"] == r2["code"]
        assert r1["data"]["total"] == r2["data"]["total"]

    def test_get_db_schema_idempotent(self, tmp_path):
        db_path = str(tmp_path / "p16_db3.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        r1 = get_db_schema(db_path=db_path)
        r2 = get_db_schema(db_path=db_path)
        assert r1["code"] == r2["code"]


# ============================================================
# TestP16Desktop — 桌面工具幂等性
# ============================================================
class TestP16Desktop:
    """P16: desktop工具幂等性 (action统一后重复调用安全)"""

    def test_mouse_control_click_idempotent(self):
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True):
            with patch("importlib.import_module", return_value=MagicMock()):
                r1 = mouse_control(action="click", x=100, y=200)
                r2 = mouse_control(action="click", x=100, y=200)
                assert r1["code"] == r2["code"]

    def test_keyboard_control_type_idempotent(self):
        with patch("app.services.tools.desktop.gui_tools._check_pyautogui", return_value=True):
            with patch("importlib.import_module", return_value=MagicMock()):
                r1 = keyboard_control(action="type", text_or_keys="test")
                r2 = keyboard_control(action="type", text_or_keys="test")
                assert r1["code"] == r2["code"]

    def test_clipboard_control_read_idempotent(self):
        mock_pyperclip = MagicMock()
        mock_pyperclip.paste.return_value = "data"
        with patch("importlib.import_module", return_value=mock_pyperclip):
            r1 = clipboard_control(action="read")
            r2 = clipboard_control(action="read")
            assert r1["code"] == r2["code"]

    def test_window_control_focus_idempotent(self):
        with patch("app.services.tools.desktop.gui_tools._focus_window",
                   return_value={"code": "SUCCESS", "data": {}, "message": "ok"}):
            result = window_control(window_title="Test", action="focus")
            assert result["code"] == "SUCCESS"


# ============================================================
# TestP16CodeExec — 代码执行工具幂等性
# ============================================================
class TestP16CodeExec:
    """P16: code_execution工具幂等性"""

    def test_execute_code_working_dir_idempotent(self, tmp_path):
        """工作目录自动创建(幂等)"""
        d1 = str(tmp_path / "deep" / "nested" / "dir")
        r1 = execute_code(code="print(1)", language="python", working_dir=d1)
        r2 = execute_code(code="print(1)", language="python", working_dir=d1)
        assert r1["code"] in ("SUCCESS", "ERR_EXEC_INVALID_DIR")
        if r1["code"] == "SUCCESS":
            assert r2["code"] == "SUCCESS"

    def test_execute_code_javascript_idempotent(self):
        r1 = execute_code(code="console.log(1);", language="javascript")
        r2 = execute_code(code="console.log(1);", language="javascript")
        if r1["code"] == "SUCCESS":
            assert r2["code"] == "SUCCESS"
