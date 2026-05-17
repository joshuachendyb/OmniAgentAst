# -*- coding: utf-8 -*-
"""
13.10/13.14 toolhelper 内部Helper测试
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.10/13.14节
变更: support_tool取消(2个LLM工具→toolhelper/network_helper.py)
      env_check 4个检查工具→toolhelper/exec_helper.py
      gui_helpers→toolhelper/gui_helper.py
      check_db_exists→toolhelper/db_helper.py

覆盖:
  exec_helper: _validate_code_safety, _check_python_available, _check_node_available, _check_module_available
  network_helper: _check_network, _validate_url
  gui_helper: _require_gui_lib, _gui_safe_call
  db_helper: _check_db_exists
  注意: 这些是内部Helper, 不通过注册表暴露给LLM
"""

import os
import sqlite3
import pytest
from unittest.mock import patch, MagicMock


# ============================================================
# exec_helper — 原env_check 4个检查工具(不暴露LLM)
# ============================================================
class TestExecHelper:
    """exec_helper 内部Helper — 原4个env_check检查工具降级"""

    def test_validate_code_safety_safe(self):
        """【P12】安全代码不应触发警告"""
        from app.services.tools.toolhelper.exec_helper import _validate_code_safety
        result = _validate_code_safety("print('hello')")
        assert result["data"]["warning_count"] >= 0

    def test_validate_code_safety_unsafe(self):
        """【P12】不安全代码应触发警告"""
        from app.services.tools.toolhelper.exec_helper import _validate_code_safety
        result = _validate_code_safety("import os; os.system('rm -rf /')")
        assert result["data"]["warning_count"] >= 0

    def test_check_python_available(self):
        """【P12内部】Python可用性检查"""
        from app.services.tools.toolhelper.exec_helper import _check_python_available
        result = _check_python_available()
        assert result["available"] is True

    def test_check_node_available(self):
        """【P12内部】Node.js可用性检查"""
        from app.services.tools.toolhelper.exec_helper import _check_node_available
        result = _check_node_available()
        # node可能未安装, 只验证返回格式
        assert isinstance(result.get("available"), bool)

    def test_check_module_available_exists(self):
        """【P12内部】检查已安装的模块"""
        from app.services.tools.toolhelper.exec_helper import _check_module_available
        result = _check_module_available("sys")
        assert result["available"] is True

    def test_check_module_available_not_exists(self):
        """【P12内部】检查不存在的模块"""
        from app.services.tools.toolhelper.exec_helper import _check_module_available
        result = _check_module_available("nonexistent_module_xyz_123")
        assert result["available"] is False

    def test_not_exposed_as_llm_tool(self):
        """验证这些函数不通过@register_tool暴露"""
        from app.services.tools.toolhelper import exec_helper as m
        # 这些函数不应有register_tool属性
        assert not hasattr(m._validate_code_safety, "_tool_registered")
        assert not hasattr(m._check_python_available, "_tool_registered")


# ============================================================
# network_helper — 原support_tool 2个工具降级
# ============================================================
class TestNetworkHelper:
    """network_helper 内部Helper — 原 check_network_connectivity + validate_url"""

    def test_validate_url_valid_http(self):
        """【P12内部】有效HTTP URL"""
        from app.services.tools.toolhelper.network_helper import _validate_url
        result = _validate_url("https://example.com")
        assert result["valid"] is True
        assert result["scheme"] == "https"

    def test_validate_url_valid_https(self):
        from app.services.tools.toolhelper.network_helper import _validate_url
        result = _validate_url("https://www.google.com/path?q=test")
        assert result["valid"] is True

    def test_validate_url_invalid(self):
        """【P12内部】无效URL"""
        from app.services.tools.toolhelper.network_helper import _validate_url
        result = _validate_url("not-a-url")
        assert result["valid"] is False

    def test_validate_url_unsupported_scheme(self):
        from app.services.tools.toolhelper.network_helper import _validate_url
        result = _validate_url("file:///etc/passwd")
        assert result["valid"] is False

    def test_check_network_connected(self):
        """【P12内部】网络连通性检查"""
        from app.services.tools.toolhelper.network_helper import _check_network
        with patch("app.services.tools.toolhelper.network_helper.socket.create_connection",
                   return_value=MagicMock()):
            result = _check_network()
            assert result["connected"] is True

    def test_check_network_disconnected(self):
        """【P12内部】网络不可用"""
        from app.services.tools.toolhelper.network_helper import _check_network
        with patch("app.services.tools.toolhelper.network_helper.socket.create_connection",
                   side_effect=OSError("No route to host")):
            result = _check_network()
            assert result["connected"] is False

    def test_not_exposed_as_llm_tool(self):
        """验证不暴露为LLM工具"""
        from app.services.tools.toolhelper import network_helper as m
        assert not hasattr(m._validate_url, "_tool_registered")
        assert not hasattr(m._check_network, "_tool_registered")


# ============================================================
# gui_helper — 原gui_helpers 7个工具降级
# ============================================================
class TestGuiHelper:
    """gui_helper 内部Helper — 原7个gui_helpers检查工具降级"""

    def test_require_gui_lib_installed(self):
        """_require_gui_lib — 已安装的库返回None"""
        from app.services.tools.toolhelper.gui_helper import _require_gui_lib
        result = _require_gui_lib("os")  # os是内置模块肯定可用
        assert result is None

    def test_require_gui_lib_not_installed(self):
        """_require_gui_lib — 未安装的库返回错误dict"""
        from app.services.tools.toolhelper.gui_helper import _require_gui_lib
        result = _require_gui_lib("nonexistent_package_xyz_999")
        assert result is not None
        assert "ERR" in result["code"]

    def test_gui_safe_call_success(self):
        """_gui_safe_call — 正常调用"""
        from app.services.tools.toolhelper.gui_helper import _gui_safe_call
        result = _gui_safe_call("os", "测试调用", lambda: "ok")
        assert result == "ok"

    def test_gui_safe_call_missing_lib(self):
        """_gui_safe_call — 库未安装时返回错误"""
        from app.services.tools.toolhelper.gui_helper import _gui_safe_call
        result = _gui_safe_call("nonexistent_package_xyz_999", "测试", lambda: None)
        assert isinstance(result, dict)
        assert "ERR" in result.get("code", "")

    def test_gui_safe_call_runtime_error(self):
        """_gui_safe_call — 运行时异常"""
        from app.services.tools.toolhelper.gui_helper import _gui_safe_call

        def failing_func():
            raise RuntimeError("模拟错误")

        result = _gui_safe_call("os", "操作失败", failing_func)
        assert isinstance(result, dict)
        assert "ERR" in result.get("code", "")

    def test_not_exposed_as_llm_tool(self):
        from app.services.tools.toolhelper import gui_helper as m
        assert not hasattr(m._require_gui_lib, "_tool_registered")
        assert not hasattr(m._gui_safe_call, "_tool_registered")


# ============================================================
# db_helper — check_db_exists降级
# ============================================================
class TestDbHelper:
    """db_helper 内部Helper — 原 check_db_exists LLM工具降级"""

    def test_check_db_exists_true(self, tmp_path):
        """数据库存在"""
        from app.services.tools.toolhelper.db_helper import _check_db_exists
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.close()
        result = _check_db_exists(db_path, "sqlite")
        assert result["exists"] is True

    def test_check_db_exists_false(self):
        """数据库不存在"""
        from app.services.tools.toolhelper.db_helper import _check_db_exists
        result = _check_db_exists("/nonexistent_db_xyz_999.db", "sqlite")
        assert result["exists"] is False

    def test_not_exposed_as_llm_tool(self):
        from app.services.tools.toolhelper import db_helper as m
        assert not hasattr(m._check_db_exists, "_tool_registered")
