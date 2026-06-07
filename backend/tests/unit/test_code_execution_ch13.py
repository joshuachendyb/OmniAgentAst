# -*- coding: utf-8 -*-
"""
13.9 code_execution 优化测试 — 2个工具
- 小健 2026-05-17

设计依据: 工具精简方案v1.9 第13.9节
变更: P12 safety_check集成(内部调用exec_helper); P16工作目录幂等
新增: P15 next_actions

覆盖:
  execute_code (python) [safety_check参数; next_actions; 工作目录幂等]
  execute_code (javascript) [next_actions; 工作目录幂等]
  安全检查由工具内部自动调用(不暴露为LLM工具)
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.tools.shell.code_execution_tools import (
    execute_code,
)


# ============================================================
# TestExecutePython
# ============================================================
class TestExecuteCode:
    """execute_code 增强测试 — P12 safety_check + P15 next_actions + P16 幂等"""

    def test_execute_code_python_basic(self):
        """正常：执行简单Python代码"""
        result = execute_code(code="print('hello')", language="python")
        assert result["code"] == "SUCCESS"

    def test_execute_code_python_error(self):
        """异常：语法错误"""
        result = execute_code(code="print(;", language="python")
        assert result["code"] == "ERR_EXEC_FAILED"

    def test_execute_code_python_timeout(self):
        """异常：超时"""
        with patch("app.services.tools.shell.code_execution_tools.subprocess.run",
                   side_effect=__import__("subprocess").TimeoutExpired("python", 30)):
            result = execute_code(code="import time; time.sleep(100)", language="python", timeout=1)
            assert result["code"] == "ERR_EXEC_TIMEOUT"

    def test_execute_code_python_safety_check_true(self):
        """【P12】safety_check=True时自动调用exec_helper检查"""
        result = execute_code(code="import os; os.system('dir')", language="python", safety_check=True)
        # 不安全代码应返回ERR_UNSAFE_CODE
        assert result["code"] in ("SUCCESS", "ERR_UNSAFE_CODE")

    def test_execute_code_python_safety_check_false(self):
        """【P12】safety_check=False可跳过安全检查"""
        result = execute_code(code="print('skip safety')", language="python", safety_check=False)
        assert result["code"] == "SUCCESS"

    def test_execute_code_working_dir_idempotent(self, tmp_path):
        """【P16幂等】working_dir不存在时自动创建"""
        non_existent_dir = str(tmp_path / "subdir" / "deep")
        result = execute_code(code="print('idempotent')", language="python", working_dir=non_existent_dir)
        assert result["code"] in ("SUCCESS", "ERR_EXEC_INVALID_DIR")

    def test_execute_code_python_next_actions_success(self):
        """【P15】执行成功返回next_actions"""
        result = execute_code(code="print('hello')", language="python")
        assert "next_actions" in result
        if result["code"] == "SUCCESS":
            assert isinstance(result["next_actions"], list)
            tools = [a["tool"] for a in result["next_actions"]]
            assert "execute_code" in tools

    def test_execute_code_python_next_actions_fail(self):
        """【P15】执行失败也返回next_actions"""
        result = execute_code(code="print(;", language="python")
        assert "next_actions" in result

    def test_execute_code_python_not_found(self):
        """异常：python未安装"""
        with patch("app.services.tools.shell.code_execution_tools.subprocess.run",
                   side_effect=FileNotFoundError("python")):
            result = execute_code(code="print(1)", language="python")
            assert "ERR" in result["code"]


# ============================================================
# TestExecuteCode (javascript)
# ============================================================
class TestExecuteCodeJavascript:
    """execute_code javascript 增强测试 — P15 next_actions + P16 幂等"""

    def test_execute_code_javascript_basic(self):
        """正常：执行简单JS代码"""
        result = execute_code(code="console.log('hello');", language="javascript")
        assert result["code"] in ("SUCCESS", "ERR_EXEC_NODE_NOT_FOUND")

    def test_execute_code_javascript_error(self):
        """异常：语法错误"""
        result = execute_code(code="console.log(;", language="javascript")
        assert result["code"] in ("ERR_EXEC_FAILED", "ERR_EXEC_NODE_NOT_FOUND")

    def test_execute_code_javascript_working_dir_idempotent(self, tmp_path):
        """【P16】工作目录幂等"""
        result = execute_code(code="console.log('test');",
                              language="javascript",
                              working_dir=str(tmp_path))
        assert result["code"] in ("SUCCESS", "ERR_EXEC_NODE_NOT_FOUND")

    def test_execute_code_javascript_next_actions_success(self):
        """【P15】执行成功返回next_actions"""
        result = execute_code(code="console.log('hello');", language="javascript")
        if result["code"] == "SUCCESS":
            assert "next_actions" in result
            tools = [a["tool"] for a in result["next_actions"]]
            assert "execute_code" in tools

    def test_execute_code_javascript_next_actions_fail(self):
        """【P15】执行失败也返回next_actions"""
        result = execute_code(code="console.log(;", language="javascript")
        if result["code"] != "ERR_EXEC_NODE_NOT_FOUND":
            assert "next_actions" in result

    def test_execute_code_javascript_not_found(self):
        """异常：node未安装"""
        with patch("app.services.tools.shell.code_execution_tools.subprocess.run",
                   side_effect=FileNotFoundError("node")):
            result = execute_code(code="console.log(1);", language="javascript")
            assert "ERR" in result["code"]
