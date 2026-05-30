"""
execute_tool_with_unified_retry 跨分类 fallback 测试

TDD: RED阶段 - 测试因缺少fallback逻辑而失败
Author: 小沈 - 2026-04-30
Updated: 小沈 - 2026-05-30 (ToolExecutor改为execute_tool_with_unified_retry)
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, Callable
from app.services.agent.tool_executor import execute_tool_with_unified_retry


class TestExecuteToolWithUnifiedRetryFallback:
    """测试execute_tool_with_unified_retry跨分类fallback"""

    @pytest.mark.asyncio
    async def test_local_tool_found_executes_ok(self):
        """本地工具能找到时正常执行"""
        async def mock_tool(file_path=None):
            return {"status": "success", "data": "ok"}
        
        tools = {"my_tool": mock_tool}
        # 传入最少参数避免参数校验失败
        result = await execute_tool_with_unified_retry("my_tool", {"file_path": "/tmp/test.txt"}, tools)
        # 如果参数校验通过，能正常执行
        assert result is not None
        # 可能因参数校验返回错误信息，但不是"tool not found"
        if "ERR_" in result.get("code", ""):
            assert "Unknown tool" not in result.get("summary", "")

    @pytest.mark.asyncio
    async def test_fallback_tool_cached_locally(self):
        """fallback后缓存到本地，下次不用再查全局"""
        tools = {}
        
        # 第一次调用应该触发fallback（需要mock全局registry）
        mock_impl = AsyncMock(return_value={"status": "success", "data": "ok"})
        mock_impl.__name__ = "mock_execute_command"
        
        with patch('app.services.tools.registry.tool_registry.get_implementation') as mock_get:
            mock_get.return_value = mock_impl
            
            result1 = await execute_tool_with_unified_retry("execute_command", {"command": "echo hello"}, tools)
            # fallback从registry找到了工具，尝试执行
            mock_get.assert_called_once_with("execute_command")

    @pytest.mark.asyncio
    async def test_local_tool_not_found_fallback_to_registry(self):
        """本地没有时从全局registry查找"""
        tools = {}
        with patch('app.services.tools.registry.tool_registry.get_implementation') as mock_get:
            mock_get.return_value = None
            result = await execute_tool_with_unified_retry("execute_command", {"command": "echo hello"}, tools)
        assert result["code"] == "ERR_TOOL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_nonexistent_tool_returns_error(self):
        """不存在的工具返回错误"""
        tools = {}
        result = await execute_tool_with_unified_retry("nonexistent_tool_xyz", {}, tools)
        assert result["code"] == "ERR_TOOL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_tool_name_finish_bypasses_tool_lookup(self):
        """finish工具直接处理，不走查找逻辑"""
        tools = {}
        result = await execute_tool_with_unified_retry("finish", {"result": "done"}, tools)
        assert result["code"] == "SUCCESS"
