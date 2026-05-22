# -*- coding: utf-8 -*-
"""S4 execute_python 深度测试 — 小沈 2026-05-19"""
import pytest
from app.services.tools.shell.code_execution_tools import execute_python


@pytest.mark.asyncio
async def test_basic_execution():
    """S4-001: 基本执行"""
    result = execute_python(code="print(42)")
    assert result["code"] == "SUCCESS"
    assert "42" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_chinese_output():
    """S4-002: 中文输出编码正确"""
    result = execute_python(code="print('你好世界')")
    assert result["code"] == "SUCCESS"
    assert "你好世界" in result["data"]["stdout"]


@pytest.mark.asyncio
async def test_syntax_error():
    """S4-003: 语法错误——返回ERR_EXEC_FAILED"""
    result = execute_python(code="print(")
    assert result["code"] == "ERR_EXEC_FAILED"
    assert result["data"]["returncode"] != 0


@pytest.mark.asyncio
async def test_runtime_error():
    """S4-004: 运行时错误"""
    result = execute_python(code="1/0")
    assert result["code"] == "ERR_EXEC_FAILED"


@pytest.mark.asyncio
async def test_timeout():
    """S4-005: 超时——临时文件被清理"""
    result = execute_python(code="import time; time.sleep(10)", timeout=1)
    assert result["code"] == "ERR_EXEC_TIMEOUT"
    assert result["data"]["returncode"] == -1


@pytest.mark.asyncio
async def test_safety_block():
    """S4-006: 安全检查拦截危险代码"""
    result = execute_python(code="import subprocess; subprocess.run('echo bad')")
    assert result["code"] == "ERR_UNSAFE_CODE"


@pytest.mark.asyncio
async def test_safety_bypass():
    """S4-007: safety_check=False可绕过检查"""
    result = execute_python(code="import os; print(os.getcwd())", safety_check=False)
    assert result["code"] == "SUCCESS"


@pytest.mark.asyncio
async def test_nonexistent_working_dir():
    """S4-008: 不存在的work_dir自动创建(P16幂等)"""
    import tempfile, os
    tmp = os.path.join(tempfile.mkdtemp(), "new_subdir")
    result = execute_python(code="print('ok')", working_dir=tmp)
    assert result["code"] == "SUCCESS"
    assert os.path.isdir(tmp)


@pytest.mark.asyncio
async def test_stderr_warning():
    """S4-009: stderr有警告输出时message提示"""
    result = execute_python(code="import sys; print('ok'); print('warn', file=sys.stderr)")
    assert result["code"] == "SUCCESS"
    assert "警告" in result["message"]


@pytest.mark.asyncio
async def test_empty_code():
    """S4-010: 空代码正常执行"""
    result = execute_python(code="")
    assert result["code"] == "SUCCESS"


@pytest.mark.asyncio
async def test_capabilities_and_next_actions():
    """S4-011: 返回包含capabilities和next_actions"""
    result = execute_python(code="print(1)")
    assert "capabilities_used" in result
    assert "python" in result["capabilities_used"]
    assert "next_actions" in result
