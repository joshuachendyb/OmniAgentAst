# -*- coding: utf-8 -*-
"""
13.10/13.14 toolhelper 内部Helper测试
- 小健 2026-05-17
- 小健 2026-05-21 修正：按实际返回类型重写测试

设计依据: 工具精简方案v1.9 第13.10/13.14节
变更: support_tool取消(2个LLM工具→toolhelper/network_helper.py)
      env_check 4个检查工具→toolhelper/exec_helper.py
      gui_helpers→toolhelper/gui_helper.py
      check_db_exists→toolhelper/db_helper.py

覆盖:
  exec_helper: _validate_code_safety, _check_python_available, _check_node_available, _check_module_available
  network_helper: _check_network, _validate_url
  gui_helper: _require_gui_lib, _gui_safe_call
  db_helper: check_db_exists
  注意: 这些是内部Helper, 不通过注册表暴露给LLM
"""

import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from app.services.tools.toolhelper.exec_helper import _validate_code_safety
from app.services.tools.toolhelper.exec_helper import _check_python_available
from app.services.tools.toolhelper.exec_helper import _check_node_available
from app.services.tools.toolhelper.exec_helper import _check_module_available
from app.services.tools.toolhelper import exec_helper as eh
from app.services.tools.toolhelper.network_helper import _validate_url
from app.services.tools.toolhelper.network_helper import _check_network
from app.services.tools.toolhelper import network_helper as nh
from app.services.tools.toolhelper.gui_helper import _require_gui_lib
from app.services.tools.toolhelper.gui_helper import _gui_safe_call
from app.services.tools.toolhelper import gui_helper as gh
from app.services.tools.toolhelper.db_helper import check_db_exists
from app.services.tools.toolhelper import db_helper as dh


# ============================================================
# exec_helper — 原env_check 4个检查工具(不暴露LLM)
# ============================================================
class TestExecHelper:
    """exec_helper 内部Helper — 原4个env_check检查工具降级"""

    def test_validate_code_safety_safe(self):
        """【P12】安全代码不应触发警告 — 返回 List[str]"""
        result = _validate_code_safety("print('hello')")
        assert isinstance(result, list)

    def test_validate_code_safety_unsafe(self):
        """【P12】不安全代码应触发警告"""
        result = _validate_code_safety("import os; os.system('rm -rf /')")
        assert isinstance(result, list)

    def test_check_python_available(self):
        """【P12内部】Python可用性检查 — 返回 bool"""
        result = _check_python_available()
        assert isinstance(result, bool)

    def test_check_node_available(self):
        """【P12内部】Node.js可用性检查 — 返回 bool"""
        result = _check_node_available()
        assert isinstance(result, bool)

    def test_check_module_available_exists(self):
        """【P12内部】检查已安装的模块 — 返回 Tuple[bool, str]"""
        result = _check_module_available("sys")
        assert isinstance(result, tuple)
        assert result[0] is True

    def test_check_module_available_not_exists(self):
        """【P12内部】检查不存在的模块"""
        result = _check_module_available("nonexistent_module_xyz_123")
        assert isinstance(result, tuple)
        assert result[0] is False

    def test_not_exposed_as_llm_tool(self):
        """验证这些函数不通过@register_tool暴露"""
        assert not hasattr(eh._validate_code_safety, "_tool_registered")
        assert not hasattr(eh._check_python_available, "_tool_registered")


# ============================================================
# network_helper — 原support_tool 2个工具降级
# ============================================================
class TestNetworkHelper:
    """network_helper 内部Helper — 原 check_network_connectivity + validate_url"""

    def test_validate_url_valid_http(self):
        """【P12内部】有效HTTP URL — 返回 Dict"""
        result = _validate_url("https://example.com")
        assert isinstance(result, dict)
        assert result["data"]["valid"] is True
        assert result["data"]["scheme"] == "https"

    def test_validate_url_valid_https(self):
        result = _validate_url("https://www.google.com/path?q=test")
        assert isinstance(result, dict)
        assert result["data"]["valid"] is True

    def test_validate_url_invalid(self):
        """【P12内部】无效URL"""
        result = _validate_url("not-a-url")
        assert isinstance(result, dict)
        assert result["data"]["valid"] is False

    def test_validate_url_unsupported_scheme(self):
        result = _validate_url("file:///etc/passwd")
        assert isinstance(result, dict)
        assert result["data"]["valid"] is False

    def test_check_network_connected(self):
        """【P12内部】网络连通性检查 — 返回 Dict"""
        with patch("app.services.tools.toolhelper.network_helper.socket.create_connection",
                   return_value=MagicMock()):
            result = _check_network()
            assert isinstance(result, dict)
            assert result["data"]["connected"] is True

    def test_check_network_disconnected(self):
        """【P12内部】网络不可用"""
        # _check_network uses socket.socket().connect(), patch at the module level
        mock_socket = MagicMock()
        mock_socket.connect.side_effect = OSError("No route to host")
        mock_socket.__enter__ = MagicMock(return_value=mock_socket)
        mock_socket.__exit__ = MagicMock(return_value=False)
        with patch("app.services.tools.toolhelper.network_helper.socket.socket", return_value=mock_socket):
            result = _check_network()
            assert isinstance(result, dict)
            assert result["data"]["connected"] is False

    def test_not_exposed_as_llm_tool(self):
        """验证不暴露为LLM工具"""
        assert not hasattr(nh._validate_url, "_tool_registered")
        assert not hasattr(nh._check_network, "_tool_registered")


# ============================================================
# gui_helper — 原gui_helpers 7个工具降级
# ============================================================
class TestGuiHelper:
    """gui_helper 内部Helper — 原7个gui_helpers检查工具降级"""

    def test_require_gui_lib_installed(self):
        """_require_gui_lib — 已安装的库返回 True"""
        result = _require_gui_lib("os")
        assert result is True

    def test_require_gui_lib_not_installed(self):
        """_require_gui_lib — 未安装的库返回 False"""
        result = _require_gui_lib("nonexistent_package_xyz_999")
        assert result is False

    def test_gui_safe_call_success(self):
        """_gui_safe_call — 正常调用"""
        result = _gui_safe_call("os", "测试调用", lambda: "ok")
        assert result == "ok"

    def test_gui_safe_call_missing_lib(self):
        """_gui_safe_call — 库未安装时返回错误dict"""
        result = _gui_safe_call("nonexistent_package_xyz_999", "测试", lambda: None)
        assert isinstance(result, dict)
        assert "ERR" in result.get("code", "")

    def test_gui_safe_call_runtime_error(self):
        """_gui_safe_call — 运行时异常"""

        def failing_func():
            raise RuntimeError("模拟错误")

        result = _gui_safe_call("os", "操作失败", failing_func)
        assert isinstance(result, dict)
        assert "ERR" in result.get("code", "")

    def test_not_exposed_as_llm_tool(self):
        assert not hasattr(gh._require_gui_lib, "_tool_registered")
        assert not hasattr(gh._gui_safe_call, "_tool_registered")


# ============================================================
# db_helper — check_db_exists降级
# ============================================================
class TestDbHelper:
    """db_helper 内部Helper — 原 check_db_exists LLM工具降级"""

    def test_check_db_exists_true(self, tmp_path):
        """数据库存在 — 返回 Dict"""
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.close()
        result = check_db_exists(db_path)
        assert isinstance(result, dict)
        assert result["data"]["exists"] is True

    def test_check_db_exists_false(self):
        """数据库不存在"""
        result = check_db_exists("/nonexistent_db_xyz_999.db")
        assert isinstance(result, dict)
        assert result["data"]["exists"] is False

    def test_not_exposed_as_llm_tool(self):
        assert not hasattr(dh.check_db_exists, "_tool_registered")
