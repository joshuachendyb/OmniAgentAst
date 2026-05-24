# -*- coding: utf-8 -*-
"""S5 execute_code(javascript) 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.code_execution_tools import execute_code


def test_basic():
    """S5-001: 基本执行"""
    result = execute_code(code="console.log(42)", language="javascript")
    assert result["code"] == "SUCCESS"
    assert "42" in result["data"]["stdout"]


def test_error():
    """S5-002: 运行时错误"""
    result = execute_code(code="throw new Error('test error')", language="javascript")
    assert result["code"] == "ERR_EXEC_FAILED"


def test_timeout():
    """S5-003: 超时"""
    result = execute_code(code="while(true){}", language="javascript", timeout=1)
    assert result["code"] == "ERR_EXEC_TIMEOUT"


def test_safety_block():
    """S5-004: 安全检查拦截"""
    result = execute_code(code="require('child_process')", language="javascript")
    assert result["code"] == "ERR_UNSAFE_CODE"


def test_safety_eval_block():
    """S5-005: eval被拦截"""
    result = execute_code(code="eval('1+1')", language="javascript")
    assert result["code"] == "ERR_UNSAFE_CODE"


def test_safety_bypass():
    """S5-006: safety_check=False绕过"""
    result = execute_code(code="console.log(eval('1+1'))", language="javascript", safety_check=False)
    assert result["code"] == "SUCCESS"


def test_empty_code():
    """S5-007: 空代码"""
    result = execute_code(code="", language="javascript")
    assert result["code"] == "SUCCESS"


def test_multiline():
    """S5-008: 多行代码"""
    result = execute_code(code="const a=1;\nconst b=2;\nconsole.log(a+b)", language="javascript")
    assert result["code"] == "SUCCESS"
    assert "3" in result["data"]["stdout"]


def test_capabilities():
    """S5-009: 验证capabilities_used"""
    result = execute_code(code="console.log(1)", language="javascript")
    assert "capabilities_used" in result
    assert "node.js" in result["capabilities_used"]
