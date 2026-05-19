# -*- coding: utf-8 -*-
"""S4 execute_python 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.code_execution_tools import execute_python


@pytest.mark.asyncio
async def test_python_basic():
    """S4-001: 基本Python执行"""
    result = execute_python(code="print('hello')")
    assert result["code"] == "SUCCESS"
    assert "hello" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_python_error():
    """S4-002: 语法错误"""
    result = execute_python(code="print(undefined_var")
    assert result["code"] == "ERR_EXEC_FAILED"


@pytest.mark.asyncio
async def test_python_timeout():
    """S4-003: 超时"""
    result = execute_python(code="import time; time.sleep(5)", timeout=1)
    assert result["code"] == "ERR_EXEC_TIMEOUT"


@pytest.mark.asyncio
async def test_python_safety():
    """S4-004: 安全检查"""
    result = execute_python(code="import os; os.system('echo bad')")
    assert result["code"] == "ERR_UNSAFE_CODE"


@pytest.mark.asyncio
async def test_python_capabilities():
    """S4-005: 验证capabilities_used"""
    result = execute_python(code="print(1)")
    assert result["code"] == "SUCCESS"
    assert "capabilities_used" in result
    assert "python" in result["capabilities_used"]
