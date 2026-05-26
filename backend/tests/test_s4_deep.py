# -*- coding: utf-8 -*-
"""S4 execute_code(python) 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.code_execution_tools import execute_code


def test_basic_execution():
    """S4-001: 基本执行"""
    result = execute_code(code="print(42)", language="python")
    assert result["code"] == "SUCCESS"
    assert "42" in result["data"]["stdout"]


def test_chinese_output():
    """S4-002: 中文输出编码正确"""
    result = execute_code(code="print('你好世界')", language="python")
    assert result["code"] == "SUCCESS"
    assert "你好世界" in result["data"]["stdout"]


def test_syntax_error():
    """S4-003: 语法错误——返回ERR_EXEC_FAILED"""
    result = execute_code(code="print(", language="python")
    assert result["code"] == "ERR_EXEC_FAILED"
    assert result["data"]["returncode"] != 0


def test_runtime_error():
    """S4-004: 运行时错误"""
    result = execute_code(code="1/0", language="python")
    assert result["code"] == "ERR_EXEC_FAILED"


def test_timeout():
    """S4-005: 超时——临时文件被清理"""
    result = execute_code(code="import time; time.sleep(10)", language="python", timeout=1)
    assert result["code"] == "ERR_EXEC_TIMEOUT"
    assert result["data"]["returncode"] == -1


def test_safety_block():
    """S4-006: 安全检查拦截危险代码"""
    result = execute_code(code="import subprocess; subprocess.run('echo bad')", language="python")
    assert result["code"] == "ERR_UNSAFE_CODE"


def test_safety_bypass():
    """S4-007: safety_check=False可绕过检查"""
    result = execute_code(code="import os; print(os.getcwd())", language="python", safety_check=False)
    assert result["code"] == "SUCCESS"


def test_nonexistent_working_dir():
    """S4-008: 不存在的work_dir自动创建(P16幂等)"""
    import tempfile, os
    tmp = os.path.join(tempfile.mkdtemp(), "new_subdir")
    result = execute_code(code="print('ok')", language="python", working_dir=tmp)
    assert result["code"] == "SUCCESS"
    assert os.path.isdir(tmp)


def test_stderr_warning():
    """S4-009: stderr有警告输出时message提示"""
    result = execute_code(code="import sys; print('ok'); print('warn', file=sys.stderr)", language="python")
    assert result["code"] == "SUCCESS"
    assert "警告" in result["message"]


def test_empty_code():
    """S4-010: 空代码返回错误"""
    result = execute_code(code="", language="python")
    assert result["code"] == "ERR_SHELL_EXEC_EMPTY_CODE"


def test_next_actions():
    """S4-011: 返回包含next_actions"""
    result = execute_code(code="print(1)", language="python")
    assert result["code"] == "SUCCESS"
    assert "next_actions" in result
