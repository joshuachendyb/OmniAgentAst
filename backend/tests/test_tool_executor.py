"""
ToolExecutor 测试 - 小沈

测试工具执行器的核心功能。

Author: 小沈 - 2026-03-21
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

from app.services.agent.tool_executor import ToolExecutor


class TestToolExecutorInitialization:
    """测试ToolExecutor初始化"""
    
    def test_executor_initialization(self):
        """测试执行器初始化"""
        tools = {"test": MagicMock()}
        executor = ToolExecutor(tools)
        assert executor.available_tools == tools
    
    def test_executor_has_available_tools(self):
        """测试执行器有可用工具属性"""
        tools = {"read_file": MagicMock(), "write_file": MagicMock()}
        executor = ToolExecutor(tools)
        assert "read_file" in executor.available_tools
        assert "write_file" in executor.available_tools


class TestToolExecutorExecution:
    """测试ToolExecutor执行功能"""
    
    @pytest.mark.asyncio
    async def test_execute_finish(self):
        """测试执行finish动作"""
        executor = ToolExecutor({})
        result = await executor.execute("finish", {"result": "done"})
        
        # 【更新 2026-04-01 小沈】finish返回格式已统一为与普通工具一致
        # 之前：{"success": True, "result": {...}}
        # 修复后：{"status": "success", "summary": "Task completed", "result": {...}, "data": ..., "retry_count": 0}
        assert result["status"] == "success"
        assert result["summary"] == "Task completed"
        assert result["result"]["operation_type"] == "finish"
        assert result["result"]["message"] == "done"
        assert result["data"] == "done"
        assert result["retry_count"] == 0
    
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """测试执行未知工具"""
        executor = ToolExecutor({})
        result = await executor.execute("unknown_tool", {})
        
        # 【更新 2026-04-01 小沈】未知工具返回格式也使用status字段
        assert result["status"] == "error"
        assert "Unknown tool" in result["summary"]
    
    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试执行成功"""
        async def mock_tool(param1, param2):
            return {"success": True, "message": "ok", "data": {"result": "test"}}
        
        executor = ToolExecutor({"test_tool": mock_tool})
        result = await executor.execute("test_tool", {"param1": "a", "param2": "b"})
        
        assert result["status"] == "success"
        assert result["data"]["success"] == True
    
    @pytest.mark.asyncio
    async def test_execute_error(self):
        """测试执行错误"""
        async def mock_tool():
            raise Exception("Tool failed")
        
        executor = ToolExecutor({"test_tool": mock_tool})
        result = await executor.execute("test_tool", {})
        
        assert result["status"] == "error"
        assert "Tool failed" in result["summary"]


class TestToolExecutorParameterNormalization:
    """测试ToolExecutor参数规范化"""
    
    def test_normalize_read_file_params(self):
        """测试read_file参数规范化
        
        【更新 2026-04-01 小沈】
        2026-03-24 tool_executor.py已删除参数映射代码，改为只监控不转换
        参数由LLM直接返回，tool_executor不做默认设置
        """
        executor = ToolExecutor({})
        
        # 参数不再映射，直接返回原始值
        params = executor._normalize_params("read_file", {"path": "test.txt"})
        assert "path" in params
        assert params["path"] == "test.txt"
    
    def test_normalize_list_directory_params(self):
        """测试list_directory参数规范化
        
        【更新 2026-04-01 小沈】参数不再映射，直接返回原始值
        """
        executor = ToolExecutor({})
        
        params = executor._normalize_params("list_directory", {"path": "test_dir"})
        assert "path" in params
        assert params["path"] == "test_dir"
    
    def test_normalize_move_file_params(self):
        """测试move_file参数规范化
        
        【更新 2026-04-01 小沈】参数不再映射，直接返回原始值
        """
        executor = ToolExecutor({})
        
        params = executor._normalize_params("move_file", {"source": "a.txt", "destination": "b.txt"})
        assert "source" in params
        assert params["source"] == "a.txt"
        assert "destination" in params
        assert params["destination"] == "b.txt"
    
    def test_normalize_search_files_params(self):
        """测试search_files参数规范化
        
        【更新 2026-04-01 小沈】参数不再设置默认值，直接返回原始值
        """
        executor = ToolExecutor({})
        
        params = executor._normalize_params("search_files", {"pattern": "test"})
        assert params["pattern"] == "test"
        # 不再添加默认path参数
        assert "path" not in params
    
    def test_normalize_preserves_correct_params(self):
        """测试保留正确参数名"""
        executor = ToolExecutor({})
        
        # 已经使用正确参数名时不应该改变
        params = executor._normalize_params("read_file", {"file_path": "test.txt"})
        assert params["file_path"] == "test.txt"
        assert "path" not in params


class TestToolExecutorResultFormatting:
    """测试ToolExecutor结果格式化"""
    
    def test_format_result_with_status_and_summary(self):
        """测试格式化带status和summary的结果"""
        executor = ToolExecutor({})
        result = executor._format_result(
            {"status": "success", "summary": "done", "data": {"result": "test"}},
            "test_tool"
        )
        
        assert result["status"] == "success"
        assert result["summary"] == "done"
        assert result["data"]["result"] == "test"
    
    def test_format_result_with_success_flag(self):
        """测试格式化带success标志的结果"""
        executor = ToolExecutor({})
        result = executor._format_result(
            {"success": True, "message": "ok", "data": {"result": "test"}},
            "test_tool"
        )
        
        assert result["status"] == "success"
        assert result["summary"] == "ok"
    
    def test_format_result_with_error(self):
        """测试格式化错误结果"""
        executor = ToolExecutor({})
        result = executor._format_result(
            {"success": False, "error": "failed"},
            "test_tool"
        )
        
        assert result["status"] == "error"
        assert result["summary"] == "failed"
    
    def test_format_result_non_dict(self):
        """测试格式化非字典结果"""
        executor = ToolExecutor({})
        result = executor._format_result("simple result", "test_tool")
        
        assert result["status"] == "success"
        assert result["data"] == "simple result"


class TestToolExecutorExecutionStatus:
    """测试ToolExecutor execution_status 功能"""
    
    @pytest.mark.asyncio
    async def test_execute_timeout(self):
        """测试工具执行超时"""
        from app.services.agent.tool_executor import TOOL_TIMEOUTS
        
        # 创建一个会超时的工具
        async def slow_tool():
            await asyncio.sleep(10)  # 睡眠10秒
            return {"data": "done"}
        
        executor = ToolExecutor({"slow_tool": slow_tool})
        
        # 临时修改超时配置，设置极短的超时时间来触发超时
        original_timeout = TOOL_TIMEOUTS.get("slow_tool")
        TOOL_TIMEOUTS["slow_tool"] = 0.1  # 100ms超时
        
        try:
            result = await executor.execute("slow_tool", {})
            
            assert result["status"] == "timeout"
            assert "timed out" in result["summary"].lower() or "timeout" in result["summary"].lower()
            assert "slow_tool" in result["summary"]  # 包含工具名称
            assert result["data"] is None
        finally:
            # 恢复原始超时配置
            if original_timeout is None:
                TOOL_TIMEOUTS.pop("slow_tool", None)
            else:
                TOOL_TIMEOUTS["slow_tool"] = original_timeout
    
    @pytest.mark.asyncio
    async def test_timeout_message_format(self):
        """测试超时消息格式"""
        from app.services.agent.tool_executor import TOOL_TIMEOUTS
        
        async def search_tool():
            await asyncio.sleep(10)
            return {"data": "results"}
        
        executor = ToolExecutor({"search_tool": search_tool})
        
        # 临时修改超时配置
        original_timeout = TOOL_TIMEOUTS.get("search_tool")
        TOOL_TIMEOUTS["search_tool"] = 0.1
        
        try:
            result = await executor.execute("search_tool", {})
            
            # 验证消息格式 - 实际返回 "Tool 'search_tool' execution timed out after 0.1 seconds"
            assert result["status"] == "timeout"
            assert "timed out" in result["summary"].lower() or "timeout" in result["summary"].lower()
            assert "search_tool" in result["summary"]  # 包含工具名称
            assert "0.1" in result["summary"]  # 超时时间
        finally:
            # 恢复原始超时配置
            if original_timeout is None:
                TOOL_TIMEOUTS.pop("search_tool", None)
            else:
                TOOL_TIMEOUTS["search_tool"] = original_timeout
    
    @pytest.mark.asyncio
    async def test_execute_permission_denied(self):
        """测试权限拒绝"""
        # 创建一个会抛出 PermissionError 的工具
        async def protected_tool():
            raise PermissionError("[WinError 5] Access is denied")
        
        executor = ToolExecutor({"protected_tool": protected_tool})
        result = await executor.execute("protected_tool", {})
        
        assert result["status"] == "permission_denied"
        assert "Permission denied" in result["summary"]
        assert result["data"] is None
    
    @pytest.mark.asyncio
    async def test_execute_warning(self):
        """测试工具返回 warning 状态"""
        async def truncated_tool():
            return {
                "status": "warning",
                "summary": "File truncated, showing first 1000 lines",
                "data": {"content": "...truncated..."}
            }
        
        executor = ToolExecutor({"truncated_tool": truncated_tool})
        result = await executor.execute("truncated_tool", {})
        
        assert result["status"] == "warning"
        assert "truncated" in result["summary"].lower()
        assert result["data"] is not None
    
    def test_tool_timeouts_config(self):
        """测试工具超时配置"""
        from app.services.agent.tool_executor import TOOL_TIMEOUTS
        
        # 验证关键工具超时配置
        assert TOOL_TIMEOUTS.get("read_file") == 30
        assert TOOL_TIMEOUTS.get("search_file_content") == 60
        assert TOOL_TIMEOUTS.get("execute_command") == 120
        assert TOOL_TIMEOUTS.get("default") == 30
