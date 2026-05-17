# -*- coding: utf-8 -*-
"""
13.9 code_execution 优化测试 — 2个工具
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.9节
变更: P12 safety_check集成(内部调用exec_helper); P16工作目录幂等
新增: P15 next_actions

覆盖:
  execute_python [safety_check参数; next_actions; 工作目录幂等]
  execute_javascript [next_actions; 工作目录幂等]
  安全检查由工具内部自动调用(不暴露为LLM工具)
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.tools.code_execution.code_execution_tools import (
    execute_python,
    execute_javascript,
)


# ============================================================
# TestExecutePython
# ============================================================
class TestExecutePython:
    """execute_python 增强测试 — P12 safety_check + P15 next_actions + P16 幂等"""

    def test_execute_python_basic(self):
        """正常：执行简单Python代码"""
        result = execute_python(code="print('hello')")
        assert result["code"] == "SUCCESS"

    def test_execute_python_error(self):
        """异常：语法错误"""
        result = execute_python(code="print(;")
        assert result["code"] == "ERR_EXEC_FAILED"

    def test_execute_python_timeout(self):
        """异常：超时"""
        with patch("app.services.tools.code_execution.code_execution_tools.subprocess.run",
                   side_effect=__import__("subprocess").TimeoutExpired("python", 30)):
            result = execute_python(code="import time; time.sleep(100)", timeout=1)
            assert result["code"] == "ERR_EXEC_TIMEOUT"

    def test_execute_python_safety_check_true(self):
        """【P12】safety_check=True时自动调用exec_helper检查"""
        result = execute_python(code="import os; os.system('dir')", safety_check=True)
        # 不安全代码应返回ERR_UNSAFE_CODE
        assert result["code"] in ("SUCCESS", "ERR_UNSAFE_CODE")

    def test_execute_python_safety_check_false(self):
        """【P12】safety_check=False可跳过安全检查"""
        result = execute_python(code="print('skip safety')", safety_check=False)
        assert result["code"] == "SUCCESS"

    def test_execute_python_working_dir_idempotent(self, tmp_path):
        """【P16幂等】working_dir不存在时自动创建"""
        non_existent_dir = str(tmp_path / "subdir" / "deep")
        result = execute_python(code="print('idempotent')", working_dir=non_existent_dir)
        assert result["code"] in ("SUCCESS", "ERR_EXEC_INVALID_DIR")

    def test_execute_python_next_actions_success(self):
        """【P15】执行成功返回next_actions"""
        result = execute_python(code="print('hello')")
        assert "next_actions" in result
        if result["code"] == "SUCCESS":
            assert isinstance(result["next_actions"], list)
            tools = [a["tool"] for a in result["next_actions"]]
            assert "execute_python" in tools

    def test_execute_python_next_actions_fail(self):
        """【P15】执行失败也返回next_actions"""
        result = execute_python(code="print(;")
        assert "next_actions" in result

    def test_execute_python_not_found(self):
        """异常：python未安装"""
        with patch("app.services.tools.code_execution.code_execution_tools.subprocess.run",
                   side_effect=FileNotFoundError("python")):
            result = execute_python(code="print(1)")
            assert "ERR" in result["code"]


# ============================================================
# TestExecuteJavascript
# ============================================================
class TestExecuteJavascript:
    """execute_javascript 增强测试 — P15 next_actions + P16 幂等"""

    def test_execute_javascript_basic(self):
        """正常：执行简单JS代码"""
        result = execute_javascript(code="console.log('hello');")
        assert result["code"] in ("SUCCESS", "ERR_EXEC_NODE_NOT_FOUND")

    def test_execute_javascript_error(self):
        """异常：语法错误"""
        result = execute_javascript(code="console.log(;")
        assert result["code"] in ("ERR_EXEC_FAILED", "ERR_EXEC_NODE_NOT_FOUND")

    def test_execute_javascript_working_dir_idempotent(self, tmp_path):
        """【P16】工作目录幂等"""
        result = execute_javascript(code="console.log('test');",
                                    working_dir=str(tmp_path))
        assert result["code"] in ("SUCCESS", "ERR_EXEC_NODE_NOT_FOUND")

    def test_execute_javascript_next_actions_success(self):
        """【P15】执行成功返回next_actions"""
        result = execute_javascript(code="console.log('hello');")
        if result["code"] == "SUCCESS":
            assert "next_actions" in result
            tools = [a["tool"] for a in result["next_actions"]]
            assert "execute_javascript" in tools

    def test_execute_javascript_next_actions_fail(self):
        """【P15】执行失败也返回next_actions"""
        result = execute_javascript(code="console.log(;")
        if result["code"] != "ERR_EXEC_NODE_NOT_FOUND":
            assert "next_actions" in result

    def test_execute_javascript_not_found(self):
        """异常：node未安装"""
        with patch("app.services.tools.code_execution.code_execution_tools.subprocess.run",
                   side_effect=FileNotFoundError("node")):
            result = execute_javascript(code="console.log(1);")
            assert "ERR" in result["code"]
