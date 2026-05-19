# -*- coding: utf-8 -*-
"""S5 execute_javascript 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.code_execution_tools import execute_javascript


@pytest.mark.asyncio
async def test_js_basic():
    """S5-001: 基本JS执行"""
    result = execute_javascript(code="console.log('hello')")
    assert result["code"] == "SUCCESS"
    assert "hello" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_js_error():
    """S5-002: 运行时错误"""
    result = execute_javascript(code="console.log(undefinedVar)")
    assert result["code"] == "ERR_EXEC_FAILED"


@pytest.mark.asyncio
async def test_js_timeout():
    """S5-003: 超时"""
    result = execute_javascript(code="while(true){}", timeout=1)
    assert result["code"] == "ERR_EXEC_TIMEOUT"


@pytest.mark.asyncio
async def test_js_capabilities():
    """S5-004: 验证capabilities_used"""
    result = execute_javascript(code="console.log(1)")
    assert result["code"] == "SUCCESS"
    assert "capabilities_used" in result
    assert "node.js" in result["capabilities_used"]
