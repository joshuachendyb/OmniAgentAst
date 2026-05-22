# -*- coding: utf-8 -*-
"""S5 execute_javascript 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.code_execution_tools import execute_javascript


@pytest.mark.asyncio
async def test_basic():
    """S5-001: 基本执行"""
    result = execute_javascript(code="console.log(42)")
    assert result["code"] == "SUCCESS"
    assert "42" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_error():
    """S5-002: 运行时错误"""
    result = execute_javascript(code="throw new Error('test error')")
    assert result["code"] == "ERR_EXEC_FAILED"


@pytest.mark.asyncio
async def test_timeout():
    """S5-003: 超时"""
    result = execute_javascript(code="while(true){}", timeout=1)
    assert result["code"] == "ERR_EXEC_TIMEOUT"


@pytest.mark.asyncio
async def test_safety_block():
    """S5-004: 安全检查拦截"""
    result = execute_javascript(code="require('child_process')")
    assert result["code"] == "ERR_UNSAFE_CODE"


@pytest.mark.asyncio
async def test_safety_eval_block():
    """S5-005: eval被拦截"""
    result = execute_javascript(code="eval('1+1')")
    assert result["code"] == "ERR_UNSAFE_CODE"


@pytest.mark.asyncio
async def test_safety_bypass():
    """S5-006: safety_check=False绕过"""
    result = execute_javascript(code="console.log(eval('1+1'))", safety_check=False)
    assert result["code"] == "SUCCESS"


@pytest.mark.asyncio
async def test_empty_code():
    """S5-007: 空代码"""
    result = execute_javascript(code="")
    assert result["code"] == "SUCCESS"


@pytest.mark.asyncio
async def test_multiline():
    """S5-008: 多行代码"""
    result = execute_javascript(code="const a=1;\nconst b=2;\nconsole.log(a+b)")
    assert result["code"] == "SUCCESS"
    assert "3" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_capabilities():
    """S5-009: 验证capabilities_used"""
    result = execute_javascript(code="console.log(1)")
    assert "capabilities_used" in result
    assert "node.js" in result["capabilities_used"]
