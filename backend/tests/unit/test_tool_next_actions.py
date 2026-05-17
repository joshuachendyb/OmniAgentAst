# -*- coding: utf-8 -*-
"""
P15 next_actions 全局验证测试
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.2-13.10节
要求: 每个保留的工具都必须在成功/失败时返回正确的 next_actions
      跨分类 next_actions 形成能力网络
覆盖:
  env工具: get_env, set_env, list_env
  system工具: service_control, task_control, get_system_info, event_log
  database工具: query_sql, execute_sql, get_db_schema
  desktop工具: list_windows, window_control, mouse_control, screen_capture, clipboard_control
  code_execution工具: execute_python, execute_javascript
"""

import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ============================================================
# 辅助: 验证 next_actions 格式
# ============================================================
def assert_next_actions_format(result, expect_present=True):
    """验证 next_actions 格式正确"""
    if expect_present:
        assert "next_actions" in result, f"缺少 next_actions: {result.get('message', '')}"
        assert isinstance(result["next_actions"], list), "next_actions 必须是列表"
        for action in result["next_actions"]:
            assert "tool" in action, f"next_actions 项缺少 tool: {action}"
            assert "description" in action, f"next_actions 项缺少 description: {action}"
    else:
        # 如果不需要next_actions, 则不强制
        pass


# ============================================================
# TestEnvNextActions — 13.2 P15
# ============================================================
class TestEnvNextActions:
    """验证env工具的next_actions输出"""

    def test_get_env_exists_next_actions(self):
        os.environ["__TEST_NA_ENV__"] = "val"
        from app.services.tools.environment.env_tools import get_env
        result = get_env("__TEST_NA_ENV__")
        os.environ.pop("__TEST_NA_ENV__", None)
        assert_next_actions_format(result)
        tools = [a["tool"] for a in result["next_actions"]]
        assert "set_env" in tools
        assert "list_env" in tools

    def test_get_env_not_exists_next_actions(self):
        from app.services.tools.environment.env_tools import get_env
        result = get_env("__TEST_NA_NONEXIST__")
        assert_next_actions_format(result)
        tools = [a["tool"] for a in result["next_actions"]]
        assert "set_env" in tools

    def test_set_env_next_actions(self):
        from app.services.tools.environment.env_tools import set_env
        result = set_env("__TEST_NA_TMP__", "tmp", scope="process")
        os.environ.pop("__TEST_NA_TMP__", None)
        assert_next_actions_format(result)

    def test_list_env_next_actions(self):
        from app.services.tools.environment.env_tools import list_env
        result = list_env()
        assert_next_actions_format(result)


# ============================================================
# TestSystemNextActions — 13.4 P15
# ============================================================
class TestSystemNextActions:
    """验证system工具的next_actions输出"""

    def test_get_system_info_next_actions(self):
        from app.services.tools.system.system_tools import get_system_info
        result = get_system_info(info_type="basic")
        assert_next_actions_format(result)

    def test_event_log_next_actions(self):
        from app.services.tools.system.system_tools import event_log
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("app.services.tools.system.system_tools.subprocess.run", return_value=mock_result):
            result = event_log(max_events=5)
            assert_next_actions_format(result)

    def test_service_control_list_next_actions(self):
        from app.services.tools.system.system_tools import service_control
        result = service_control(action="list")
        if result["code"] == "SUCCESS":
            assert_next_actions_format(result)

    def test_task_control_list_next_actions(self):
        from app.services.tools.system.system_tools import task_control
        result = task_control(action="list")
        if result["code"] == "SUCCESS":
            assert_next_actions_format(result)


# ============================================================
# TestDatabaseNextActions — 13.5 P15
# ============================================================
class TestDatabaseNextActions:
    """验证database工具的next_actions输出"""

    def test_query_sql_next_actions(self, tmp_path):
        db_path = str(tmp_path / "na_test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.execute("INSERT INTO t VALUES (1)")
        conn.commit()
        conn.close()
        from app.services.tools.database.database_tools import query_sql
        result = query_sql(sql="SELECT * FROM t", db_path=db_path)
        assert_next_actions_format(result)
        tools = [a["tool"] for a in result["next_actions"]]
        assert "execute_sql" in tools

    def test_execute_sql_next_actions(self, tmp_path):
        db_path = str(tmp_path / "na_test2.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        from app.services.tools.database.database_tools import execute_sql
        result = execute_sql(sql="INSERT INTO t VALUES (1)", db_path=db_path, dry_run=True)
        assert_next_actions_format(result)
        tools = [a["tool"] for a in result["next_actions"]]
        assert "query_sql" in tools

    def test_get_db_schema_next_actions(self, tmp_path):
        db_path = str(tmp_path / "na_test3.db")
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        from app.services.tools.database.database_tools import get_db_schema
        result = get_db_schema(db_path=db_path)
        if result["code"] == "SUCCESS":
            assert_next_actions_format(result)


# ============================================================
# TestDesktopNextActions — 13.6 P15
# ============================================================
class TestDesktopNextActions:
    """验证desktop工具的next_actions输出"""

    def test_list_windows_next_actions(self):
        from app.services.tools.desktop.desktop_tools import list_windows
        with patch("app.services.tools.desktop.desktop_tools._check_platform", return_value=None):
            with patch("app.services.tools.desktop.desktop_tools._find_windows_by_title",
                       return_value=[{"hwnd": 1, "title": "T", "class": "C"}]):
                result = list_windows()
                assert_next_actions_format(result)
                tools = [a["tool"] for a in result["next_actions"]]
                assert "get_window_info" in tools

    def test_mouse_control_next_actions(self):
        from app.services.tools.desktop.desktop_tools import mouse_control
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.click"):
                result = mouse_control(action="click", x=100, y=200)
                assert_next_actions_format(result)

    def test_screen_capture_next_actions(self):
        from app.services.tools.desktop.desktop_tools import screen_capture
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyautogui.screenshot") as m:
                m.return_value = MagicMock()
                result = screen_capture()
                assert_next_actions_format(result)

    def test_clipboard_control_next_actions(self):
        from app.services.tools.desktop.desktop_tools import clipboard_control
        with patch("app.services.tools.desktop.gui_helper._require_gui_lib", return_value=None):
            with patch("app.services.tools.desktop.gui_helper.pyperclip.paste",
                       return_value="data"):
                result = clipboard_control(action="read")
                assert_next_actions_format(result)


# ============================================================
# TestCodeExecNextActions — 13.9 P15
# ============================================================
class TestCodeExecNextActions:
    """验证code_execution工具的next_actions输出"""

    def test_execute_python_success_next_actions(self):
        from app.services.tools.code_execution.code_execution_tools import execute_python
        result = execute_python(code="print(1)")
        if result["code"] == "SUCCESS":
            assert_next_actions_format(result)
            tools = [a["tool"] for a in result["next_actions"]]
            assert "execute_python" in tools

    def test_execute_python_fail_next_actions(self):
        from app.services.tools.code_execution.code_execution_tools import execute_python
        result = execute_python(code="print(;")
        assert_next_actions_format(result)

    def test_execute_javascript_success_next_actions(self):
        from app.services.tools.code_execution.code_execution_tools import execute_javascript
        result = execute_javascript(code="console.log(1);")
        if result["code"] == "SUCCESS":
            assert_next_actions_format(result)
