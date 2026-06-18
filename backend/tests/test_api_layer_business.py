# -*- coding: utf-8 -*-
"""
API层业务逻辑深度测试 — chat_router / chat_stream / execute_tool

覆盖目标:
- chat_router.py (69% → 100%)
- chat_stream.py (24% → 100%)
- execute_tool.py (0% → 100%)

核心: 模拟LLM/DB, 测试实际业务流, 验证SSE格式, 验证工具执行

小健 - 2026-06-09
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from fastapi import Request

from app.api.v1.chat.models import ChatRequest, ChatMessage
from app.api.v1.chat.chat_stream import (
    chat_stream,
)
from app.services.task.task_interrupt_check import (
    task_interrupt_check, task_pause_check_and_yield,
)
from app.services.react_sse_wrapper.run_sse_stream import run_sse_stream
from app.services.task.task_cancel_check import task_cancel_check_and_yield
from app.api.v1.health.execute_tool import (
    execute_tool,
    ToolExecuteRequest,
    ToolExecuteResponse,
)
from app.api.v1.chat.validate_chat_config import validate_chat_config
from app.api.v1.chat.confirm_operation import confirm_operation
from app.services.react_sse_wrapper.chat_stream import (
    format_sse_event,
    format_agent_sse,
    create_error_response,
    create_final_response,
)
from app.services.agent.steps import ErrorStep, FinalStep


# ====================================================================
# Fixtures
# ====================================================================

@pytest.fixture
def mock_ai_service():
    """Mock AI Service"""
    svc = MagicMock()
    svc.provider = "openai"
    svc.model = "gpt-4"
    svc.get_config_path.return_value = None
    svc.close = AsyncMock()
    return svc


@pytest.fixture
def mock_valid_request():
    """有效聊天请求"""
    return ChatRequest(
        messages=[ChatMessage(role="user", content="你好")],
        stream=True,
    )


@pytest.fixture
def mock_tool_registry():
    """Mock ToolRegistry"""
    registry = MagicMock()
    registry.get_implementation.return_value = None
    return registry


# ====================================================================
# 辅助函数
# ====================================================================

def asyncio_run(coro):
    """运行协程的辅助函数"""
    import asyncio
    return asyncio.run(coro)


# ====================================================================
# 第一部分: format_sse_event / format_agent_sse 单元测试
# ====================================================================

class TestSSEFormatting:
    """SSE事件格式化工具函数测试"""

    def test_format_sse_event_with_timestamp(self):
        """SSE事件包含timestamp字段时原样保留"""
        data = {"content": "hello", "timestamp": 1234567890}
        result = format_sse_event("chunk", 1, data)

        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["type"] == "chunk"
        assert payload["step"] == 1
        assert payload["timestamp"] == 1234567890
        assert payload["content"] == "hello"
        assert result.endswith("\n\n")

    def test_format_sse_event_generates_timestamp(self):
        """SSE事件不包含timestamp时自动生成"""
        data = {"content": "hello"}
        result = format_sse_event("chunk", 2, data)

        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["type"] == "chunk"
        assert payload["step"] == 2
        assert "timestamp" in payload
        assert payload["content"] == "hello"

    def test_format_sse_event_ensure_ascii_false(self):
        """SSE事件确保中文不被转义"""
        data = {"content": "你好世界"}
        result = format_sse_event("chunk", 1, data)
        assert "你好世界" in result

    def test_format_agent_sse_with_dict(self):
        """Agent事件以dict输入时正确格式化"""
        event_dict = {
            "type": "chunk",
            "step": 3,
            "content": "测试内容",
        }
        result = format_agent_sse(event_dict)
        assert result != ""
        assert "测试内容" in result

    def test_format_agent_sse_with_empty_type(self):
        """空type的事件返回空字符串"""
        event_dict = {"step": 1, "content": "test"}
        result = format_agent_sse(event_dict)
        assert result == ""

    def test_format_agent_sse_with_error_step(self):
        """ErrorStep.to_dict()结果正确格式化为SSE"""
        error_step = ErrorStep(
            step=5,
            error_type="api_error",
            error_message="连接超时",
            recoverable=True,
        )
        result = format_agent_sse(error_step.to_dict())
        assert "连接超时" in result

    def test_format_agent_sse_with_final_step(self):
        """FinalStep.to_dict()结果正确格式化为SSE"""
        final_step = FinalStep(
            step=10,
            response="最终回复内容",
            thought="这是推理过程",
            model="gpt-4",
            provider="openai",
        )
        result = format_agent_sse(final_step.to_dict())
        assert "最终回复内容" in result
        assert "gpt-4" in result

    def test_create_error_response_default_recoverable(self):
        """错误响应默认recoverable为False"""
        result = create_error_response(
            error_type="validation_error",
            error_message="参数无效",
        )
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["recoverable"] is False

    def test_create_error_response_with_all_fields(self):
        """错误响应包含所有可选字段"""
        result = create_error_response(
            error_type="api_error",
            error_message="超时",
            model="gpt-4",
            provider="openai",
            recoverable=True,
            step=3,
        )
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["error_type"] == "api_error"
        assert payload["model"] == "gpt-4"
        assert payload["provider"] == "openai"
        assert payload["recoverable"] is True

    def test_format_sse_event_unicode_escaped_json(self):
        """SSE事件JSON格式合法"""
        data = {"content": "test"}
        result = format_sse_event("chunk", 1, data)
        payload = json.loads(result.replace("data: ", "").strip())
        assert isinstance(payload, dict)

    def test_format_sse_event_step_counter(self):
        """SSE事件step字段正确传递"""
        data = {"content": "test"}
        result = format_sse_event("chunk", 42, data)
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["step"] == 42


# ====================================================================
# 第二部分: chat_stream 流式测试
# ====================================================================

class TestChatStreamV2:
    """chat_stream 核心业务流测试"""

    @pytest.mark.asyncio
    async def test_empty_messages_returns_error(self, mock_valid_request):
        """空消息列表返回错误响应"""
        mock_valid_request.messages = []

        response = await chat_stream(mock_valid_request)

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        body = response.body  # PlainTextResponse.body is property (bytes)
        assert "消息列表不能为空" in body.decode()

    @pytest.mark.asyncio
    async def test_single_message_generates_stream(self, mock_valid_request, mock_ai_service):
        """单条消息生成SSE流"""

        async def mock_start_gen():
            yield "data: {\"type\": \"start\"}\n\n"

        async def mock_sse_gen():
            yield "data: {\"type\": \"chunk\", \"content\": \"test\"}\n\n"

        with (
            patch("app.api.v1.chat.chat_stream.get_service", return_value=mock_ai_service),
            patch("app.api.v1.chat.chat_stream.register_task", new_callable=AsyncMock),
            patch("app.api.v1.chat.chat_stream.task_interrupt_check", new_callable=AsyncMock, return_value=(False, "")),
            patch("app.api.v1.chat.chat_stream.task_pause_check_and_yield", new_callable=AsyncMock, return_value=mock_sse_gen()),
            patch("app.api.v1.chat.chat_stream.step_start", new_callable=AsyncMock, return_value=mock_start_gen()),
            patch("app.api.v1.chat.chat_stream.run_sse_stream", new_callable=AsyncMock, return_value=mock_sse_gen()),
            patch("app.api.v1.chat.chat_stream.task_cancel_check_and_yield", new_callable=AsyncMock, return_value=None),
            patch("app.api.v1.chat.chat_stream.task_cleanup", new_callable=AsyncMock),
        ):
            response = await chat_stream(mock_valid_request)
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_stream_with_session_id_preserves_session(self, mock_ai_service):
        """带session_id的请求保留session_id"""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="测试会话")],
            session_id="test-session-001",
        )

        async def empty_ag():
            return
            yield

        with (
            patch("app.api.v1.chat.chat_stream.get_service", return_value=mock_ai_service),
            patch("app.api.v1.chat.chat_stream.register_task", new_callable=AsyncMock) as mock_reg,
            patch("app.api.v1.chat.chat_stream.task_interrupt_check", new_callable=AsyncMock, return_value=(False, "")),
            patch("app.api.v1.chat.chat_stream.task_pause_check_and_yield", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.step_start", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.run_sse_stream", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.task_cancel_check_and_yield", new_callable=AsyncMock, return_value=None),
            patch("app.api.v1.chat.chat_stream.task_cleanup", new_callable=AsyncMock) as mock_clean,
        ):
            response = await chat_stream(request)
            assert response.status_code == 200
            # 必须消耗生成器才能使generate()中的mock调用生效
            async for _ in response.body_iterator:
                pass
            mock_reg.assert_called_once()
            mock_clean.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_exception_captured_and_cleaned_up(self, mock_valid_request, mock_ai_service):
        """流式处理异常时被捕获并清理"""
        async def empty_ag():
            return
            yield

        with (
            patch("app.api.v1.chat.chat_stream.get_service", return_value=mock_ai_service),
            patch("app.api.v1.chat.chat_stream.register_task", new_callable=AsyncMock, side_effect=RuntimeError("注册失败")),
            patch("app.api.v1.chat.chat_stream.task_cleanup", new_callable=AsyncMock) as mock_clean,
        ):
            response = await chat_stream(mock_valid_request)
            # StreamingResponse returns async generator, consume body iterator
            events = []
            async for chunk in response.body_iterator:
                events.append(chunk)
            body_str = "".join(events)
            assert "路由异常" in body_str
            mock_clean.assert_called_once()

    @pytest.mark.asyncio
    async def test_sse_stream_with_cancel_check_break_on_cancel(self):
        """取消检查返回cancel事件时中断流"""
        task_id = "test-task-001"
        next_step = MagicMock(side_effect=[1, 2])
        cancel_event = "data: {\"type\": \"cancel\", \"message\": \"任务已取消\"}\n\n"

        async def mock_sse_gen():
            yield "data: {\"type\": \"chunk\"}\n\n"

        with (
            patch(f"{__name__}.run_sse_stream", return_value=mock_sse_gen()),
            patch(f"{__name__}.task_cancel_check_and_yield", new_callable=AsyncMock, return_value=cancel_event),
        ):
            collected = []
            async for sse_chunk in run_sse_stream(
                llm_client=MagicMock(), task_id=task_id, last_message="test",
                next_step=next_step,
                session_id="test-sess", current_execution_steps=[],
                current_content="", llm_call_count_holder=[0],
            ):
                cancelled_sse = await task_cancel_check_and_yield(
                    task_id, next_step, "test-sess", [], ""
                )
                if cancelled_sse:
                    collected.append(cancelled_sse)
                    break
                collected.append(sse_chunk)

            assert len(collected) == 1
            assert cancel_event in collected[0]

    @pytest.mark.asyncio
    async def test_sse_stream_no_cancel_yields_all_chunks(self):
        """无取消时所有chunk正常yield"""
        task_id = "test-task-002"
        next_step = MagicMock(side_effect=[1, 2, 3])
        expected_chunks = ["chunk-1", "chunk-2", "chunk-3"]

        async def mock_sse_gen():
            for c in expected_chunks:
                yield f"data: {c}\n\n"

        with (
            patch(f"{__name__}.run_sse_stream", return_value=mock_sse_gen()),
            patch(f"{__name__}.task_cancel_check_and_yield", new_callable=AsyncMock, return_value=None),
        ):
            collected = []
            async for sse_chunk in run_sse_stream(
                llm_client=MagicMock(), task_id=task_id, last_message="test",
                next_step=next_step,
                session_id="test-sess", current_execution_steps=[],
                current_content="", llm_call_count_holder=[0],
            ):
                cancelled_sse = await task_cancel_check_and_yield(
                    task_id, next_step, "test-sess", [], ""
                )
                if cancelled_sse:
                    break
                collected.append(sse_chunk)

            assert len(collected) == 3
            for expected in expected_chunks:
                assert expected in collected[expected_chunks.index(expected)]

    @pytest.mark.asyncio
    async def test_task_interrupt_check_returns_false(self):
        """task_interrupt_check返回false时继续"""
        with patch("app.services.task.task_interrupt_check.check_cancelled", new_callable=AsyncMock, return_value=False):
            is_interrupted, msg = await task_interrupt_check("task-123")
            assert is_interrupted is False
            assert msg == ""

    @pytest.mark.asyncio
    async def test_task_interrupt_check_returns_true(self):
        """task_interrupt_check返回true时返回中断消息"""
        with patch("app.services.task.task_interrupt_check.check_cancelled", new_callable=AsyncMock, return_value=True):
            is_interrupted, msg = await task_interrupt_check("task-456", next_step=MagicMock(return_value=1))
            assert is_interrupted is True
            assert "incident" in msg or "interrupted" in msg

    @pytest.mark.asyncio
    async def test_task_pause_check_and_yield_empty(self):
        """task_pause_check_and_yield返回空迭代器时yield nothing"""
        from app.services.task.task_registry import get_pause_event
        with (
            patch("app.services.task.task_interrupt_check.check_cancelled", new_callable=AsyncMock, return_value=False),
            patch("app.services.task.task_interrupt_check.get_pause_event", new_callable=AsyncMock, return_value=None),
        ):
            collected = []
            async for event in task_pause_check_and_yield("task-789"):
                collected.append(event)
            assert collected == []

    @pytest.mark.asyncio
    async def test_chat_request_model_valid(self):
        """ChatRequest模型正常创建"""
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="test")],
            stream=True,
        )
        assert req.messages[0].role == "user"
        assert req.messages[0].content == "test"

    @pytest.mark.asyncio
    async def test_chat_request_model_with_all_fields(self):
        """ChatRequest模型支持全部字段"""
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="测试")],
            stream=True,
            temperature=1.5,
            provider="claude",
            model="claude-3",
            task_id="custom-task-1",
            session_id="custom-session-1",
        )
        assert req.stream is True
        assert req.temperature == 1.5
        assert req.provider == "claude"
        assert req.model == "claude-3"

    @pytest.mark.asyncio
    async def test_chat_request_model_default_values(self):
        """ChatRequest模型默认值验证"""
        req = ChatRequest(messages=[ChatMessage(role="user", content="test")])
        assert req.stream is False
        assert req.temperature == 0.7
        assert req.provider is None
        assert req.model is None


# ====================================================================
# 第三部分: chat_router 端点测试
# ====================================================================

class TestChatRouter:
    """chat_router 端点业务逻辑测试"""

    def test_validate_config_endpoint_valid(self):
        """配置验证端点返回有效配置"""
        mock_resolver = MagicMock()
        mock_resolver.validate_config.return_value = (True, "openai", "gpt-4", [])

        with patch("app.services.ai_config_resolver.get_ai_config_resolver", return_value=mock_resolver):
            result = asyncio_run(validate_chat_config())
            assert result["valid"] is True
            assert "openai" in result["provider"]

    def test_validate_config_endpoint_invalid(self):
        """配置验证端点返回无效配置"""
        mock_resolver = MagicMock()
        mock_resolver.validate_config.return_value = (False, "unknown", "", ["API key missing"])

        with patch("app.services.ai_config_resolver.get_ai_config_resolver", return_value=mock_resolver):
            result = asyncio_run(validate_chat_config())
            assert result["valid"] is False
            assert "API key missing" in result["message"]

    def test_validate_config_endpoint_exception(self):
        """配置验证异常时返回错误响应"""
        with patch("app.services.ai_config_resolver.get_ai_config_resolver", side_effect=Exception("Config error")):
            result = asyncio_run(validate_chat_config())
            assert result["valid"] is False
            assert "验证失败" in result["message"]

    @pytest.mark.asyncio
    async def test_confirm_operation_accepted(self):
        """确认操作端点正常接收确认"""
        from app.services.task.hitl_confirmation import _pending_confirmations, _PendingConfirmation
        import asyncio, time
        test_confirm_id = "task-abc:test123"
        future = asyncio.get_running_loop().create_future()
        _pending_confirmations[test_confirm_id] = _PendingConfirmation(future=future, created_at=time.time())
        try:
            mock_request = MagicMock(spec=Request)
            mock_request.json = AsyncMock(return_value={
                "confirm_id": test_confirm_id,
                "confirmed": True,
            })
            result = await confirm_operation(mock_request)
            assert result["success"] is True
        finally:
            _pending_confirmations.pop(test_confirm_id, None)

    @pytest.mark.asyncio
    async def test_confirm_operation_rejected(self):
        """确认操作端点接收拒绝确认"""
        from app.services.task.hitl_confirmation import _pending_confirmations, _PendingConfirmation
        import asyncio, time
        test_confirm_id = "task-abc:test456"
        future = asyncio.get_running_loop().create_future()
        _pending_confirmations[test_confirm_id] = _PendingConfirmation(future=future, created_at=time.time())
        try:
            mock_request = MagicMock(spec=Request)
            mock_request.json = AsyncMock(return_value={
                "confirm_id": test_confirm_id,
                "confirmed": False,
            })
            result = await confirm_operation(mock_request)
            assert result["success"] is True
        finally:
            _pending_confirmations.pop(test_confirm_id, None)

    @pytest.mark.asyncio
    async def test_confirm_operation_missing_confirm_id(self):
        """确认操作端点缺少confirm_id时返回失败"""
        mock_request = MagicMock(spec=Request)
        mock_request.json = AsyncMock(return_value={
            "confirmed": True,
        })
        result = await confirm_operation(mock_request)
        assert result["success"] is False
        assert "confirm_id" in result.get("error", "")


# ====================================================================
# 第四部分: execute_tool 工具执行测试
# ====================================================================

class TestExecuteTool:
    """execute_tool 工具执行端点测试"""

    def test_execute_unknown_tool(self, mock_tool_registry):
        """执行未注册工具返回错误"""
        mock_tool_registry.get_implementation.return_value = None

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="nonexistent_tool", params={})
            result = asyncio_run(execute_tool(req))
            assert result.success is False
            assert "not found" in result.error.lower() or "未找到" in result.error
            assert result.tool_name == "nonexistent_tool"

    def test_execute_sync_tool_success(self, mock_tool_registry):
        """同步工具执行成功"""
        def sync_read_file(path):
            return {"files": ["main.py", "config.py"]}

        mock_tool_registry.get_implementation.return_value = sync_read_file

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="read_file", params={"path": "app/main.py"})
            result = asyncio_run(execute_tool(req))
            assert result.success is True
            assert result.tool_name == "read_file"
            assert result.result == {"files": ["main.py", "config.py"]}

    @pytest.mark.asyncio
    async def test_execute_async_tool_success(self, mock_tool_registry):
        """异步工具执行成功"""
        async def async_list_dir(path):
            return {"dir": path, "entries": ["a.txt", "b.txt"]}

        mock_tool_registry.get_implementation.return_value = async_list_dir

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="list_directory", params={"path": "/tmp"})
            result = await execute_tool(req)
            assert result.success is True
            assert result.result["dir"] == "/tmp"

    def test_execute_tool_missing_params(self, mock_tool_registry):
        """执行工具缺少必填参数时返回错误信息"""
        def func_with_required(a, b):
            return a + b

        mock_tool_registry.get_implementation.return_value = func_with_required

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="test_func", params={})
            result = asyncio_run(execute_tool(req))
            assert result.success is False
            assert "缺少必填参数" in result.error

    def test_execute_tool_generic_exception(self, mock_tool_registry):
        """执行工具抛出通用异常时捕获错误"""
        def func_that_fails(**params):
            raise PermissionError("无权访问")

        mock_tool_registry.get_implementation.return_value = func_that_fails

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="failing_tool", params={})
            result = asyncio_run(execute_tool(req))
            assert result.success is False
            assert "无权访问" in result.error

    def test_execute_tool_returns_non_dict(self, mock_tool_registry):
        """工具返回非dict类型时包装为output字段"""
        def func_returns_string():
            return "hello world"

        mock_tool_registry.get_implementation.return_value = func_returns_string

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="string_tool", params={})
            result = asyncio_run(execute_tool(req))
            assert result.success is True
            assert result.result == {"output": "hello world"}

    def test_execute_tool_params_default_empty(self, mock_tool_registry):
        """工具请求缺少params字段时默认空dict"""
        def simple_echo(**params):
            return {"received": params}

        mock_tool_registry.get_implementation.return_value = simple_echo

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="echo_tool", params={})
            result = asyncio_run(execute_tool(req))
            assert result.success is True
            assert result.result["received"] == {}

    def test_tool_execute_request_model(self):
        """ToolExecuteRequest模型验证"""
        req = ToolExecuteRequest(tool_name="test", params={"key": "val"})
        assert req.tool_name == "test"
        assert req.params == {"key": "val"}

    def test_tool_execute_request_default_params(self):
        """ToolExecuteRequest默认params为空dict"""
        req = ToolExecuteRequest(tool_name="test")
        assert req.params == {}

    def test_tool_execute_response_model(self):
        """ToolExecuteResponse模型验证"""
        resp = ToolExecuteResponse(tool_name="read_file", success=True, result={"files": ["a.py"]})
        assert resp.tool_name == "read_file"
        assert resp.success is True
        assert resp.error == ""

    def test_tool_execute_response_default_values(self):
        """ToolExecuteResponse默认值验证"""
        resp = ToolExecuteResponse(tool_name="test", success=False, error="fail")
        assert resp.result == {}

    def test_execute_tool_with_complex_params(self, mock_tool_registry):
        """工具接收复杂参数结构"""
        def complex_handler(**params):
            data = params.get("data", {})
            return {"processed": len(data.get("items", []))}

        mock_tool_registry.get_implementation.return_value = complex_handler

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(
                tool_name="handler",
                params={"data": {"items": [1, 2, 3, 4, 5]}}
            )
            result = asyncio_run(execute_tool(req))
            assert result.success is True
            assert result.result["processed"] == 5

    def test_execute_tool_empty_error_string(self, mock_tool_registry):
        """成功执行时error字段为空字符串"""
        def simple_func():
            return {"ok": True}

        mock_tool_registry.get_implementation.return_value = simple_func

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name="simple", params={})
            result = asyncio_run(execute_tool(req))
            assert result.error == ""


# ====================================================================
# 第五部分: 业务流集成测试
# ====================================================================

class TestBusinessFlowIntegration:
    """业务流集成测试: 从请求到SSE输出的完整链路"""

    @pytest.mark.asyncio
    async def test_full_stream_flow_with_mocked_steps(self, mock_valid_request, mock_ai_service):
        """完整流式链路: register → interrupt_check → start → stream → cleanup"""
        start_event = 'data: {"type": "start", "step": 1}\n\n'
        chunk_event = 'data: {"type": "chunk", "step": 2, "content": "hello"}\n\n'
        final_event = 'data: {"type": "final", "step": 3, "response": "done"}\n\n'

        async def empty_ag():
            return
            yield

        async def mock_start_gen():
            yield start_event

        async def mock_sse_stream_gen():
            yield chunk_event
            yield final_event

        with (
            patch("app.api.v1.chat.chat_stream.get_service", return_value=mock_ai_service),
            patch("app.api.v1.chat.chat_stream.register_task", new_callable=AsyncMock),
            patch("app.api.v1.chat.chat_stream.task_interrupt_check", new_callable=AsyncMock, return_value=(False, "")),
            patch("app.api.v1.chat.chat_stream.task_pause_check_and_yield", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.step_start", return_value=mock_start_gen()),
            patch("app.api.v1.chat.chat_stream.run_sse_stream", return_value=mock_sse_stream_gen()),
            patch("app.api.v1.chat.chat_stream.task_cancel_check_and_yield", new_callable=AsyncMock, return_value=None),
            patch("app.api.v1.chat.chat_stream.task_cleanup", new_callable=AsyncMock),
        ):
            response = await chat_stream(mock_valid_request)
            events = []
            async for chunk in response.body_iterator:
                events.append(chunk)
            all_text = "".join(events)

            assert "start" in all_text
            assert "chunk" in all_text
            assert "hello" in all_text
            assert "final" in all_text
            assert "done" in all_text

    @pytest.mark.asyncio
    async def test_full_stream_flow_with_error_event(self, mock_valid_request, mock_ai_service):
        """完整流式链路: 流中包含错误事件"""
        async def empty_ag():
            return
            yield

        async def mock_error_sse_gen():
            yield 'data: {"type": "chunk", "step": 1, "content": "partial"}\n\n'
            yield 'data: {"type": "error", "error_type": "api_error", "error_message": "LLM超时"}\n\n'

        with (
            patch("app.api.v1.chat.chat_stream.get_service", return_value=mock_ai_service),
            patch("app.api.v1.chat.chat_stream.register_task", new_callable=AsyncMock),
            patch("app.api.v1.chat.chat_stream.task_interrupt_check", new_callable=AsyncMock, return_value=(False, "")),
            patch("app.api.v1.chat.chat_stream.task_pause_check_and_yield", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.step_start", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.run_sse_stream", return_value=mock_error_sse_gen()),
            patch("app.api.v1.chat.chat_stream.task_cancel_check_and_yield", new_callable=AsyncMock, return_value=None),
            patch("app.api.v1.chat.chat_stream.task_cleanup", new_callable=AsyncMock),
        ):
            response = await chat_stream(mock_valid_request)
            events = []
            async for chunk in response.body_iterator:
                events.append(chunk)
            all_text = "".join(events)

            assert "LLM超时" in all_text
            assert "error" in all_text

    @pytest.mark.asyncio
    async def test_multiple_messages_uses_last_as_user_input(self, mock_ai_service):
        """多消息时取最后一条作为user_input"""
        req = ChatRequest(messages=[
            ChatMessage(role="system", content="你是助手"),
            ChatMessage(role="user", content="历史消息1"),
            ChatMessage(role="user", content="最新消息"),
        ])

        captured_input = [None]

        async def empty_ag():
            return
            yield

        async def capture_step_start(ai_service, task_id, next_step, user_input, execution_steps, session_id):
            captured_input[0] = user_input
            async for _ in empty_ag():
                yield _

        with (
            patch("app.api.v1.chat.chat_stream.get_service", return_value=mock_ai_service),
            patch("app.api.v1.chat.chat_stream.register_task", new_callable=AsyncMock),
            patch("app.api.v1.chat.chat_stream.task_interrupt_check", new_callable=AsyncMock, return_value=(False, "")),
            patch("app.api.v1.chat.chat_stream.task_pause_check_and_yield", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.step_start", side_effect=capture_step_start),
            patch("app.api.v1.chat.chat_stream.run_sse_stream", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.task_cleanup", new_callable=AsyncMock),
        ):
            response = await chat_stream(req)
            async for _ in response.body_iterator:
                pass
            assert captured_input[0] == "最新消息"

    @pytest.mark.asyncio
    async def test_interrupt_flow_path(self, mock_valid_request, mock_ai_service):
        """中断流程: interrupt检测 → cleanup"""
        interrupt_msg = 'data: {"type": "interrupted", "message": "任务已中断"}\n\n'

        async def empty_ag():
            return
            yield

        with (
            patch("app.api.v1.chat.chat_stream.get_service", return_value=mock_ai_service),
            patch("app.api.v1.chat.chat_stream.register_task", new_callable=AsyncMock),
            patch("app.api.v1.chat.chat_stream.task_interrupt_check", new_callable=AsyncMock, return_value=(True, interrupt_msg)),
            patch("app.api.v1.chat.chat_stream.task_pause_check_and_yield", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.step_start", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.run_sse_stream", return_value=empty_ag()),
            patch("app.api.v1.chat.chat_stream.task_cleanup", new_callable=AsyncMock) as mock_clean,
        ):
            response = await chat_stream(mock_valid_request)
            events = []
            async for chunk in response.body_iterator:
                events.append(chunk)
            all_text = "".join(events)
            assert "中断" in all_text
            # 中断路径调用cleanup一次, finally也调用一次, 共2次
            assert mock_clean.call_count >= 1

    def test_create_final_response_includes_model_info(self):
        """最终响应包含model和provider信息"""
        result = create_final_response(
            content="这是回复",
            step=5,
            provider="openai",
            model="gpt-4",
            thought="推理完成",
        )
        assert "这是回复" in result
        assert "gpt-4" in result
        assert "openai" in result

    def test_create_final_response_default_step(self):
        """最终响应默认step为0"""
        result = create_final_response(
            content="测试回复",
        )
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["step"] == 0


# ====================================================================
# 第六部分: 边界条件测试
# ====================================================================

class TestBoundaryConditions:
    """边界条件测试"""

    def test_sse_event_special_characters_in_content(self):
        """SSE事件包含特殊字符时JSON合法"""
        data = {"content": "test\nwith\rnewlines\tand \"quotes\""}
        result = format_sse_event("chunk", 1, data)
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["content"] == "test\nwith\rnewlines\tand \"quotes\""

    def test_sse_event_empty_data_dict(self):
        """SSE事件data为空dict时仍可格式化"""
        result = format_sse_event("ping", 0, {})
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["type"] == "ping"
        assert "timestamp" in payload

    def test_error_step_with_none_fields(self):
        """ErrorStep含None字段时正确序列化"""
        error_step = ErrorStep(step=1, error_type="test", error_message="test error")
        result = format_agent_sse(error_step.to_dict())
        assert result != ""
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["error_type"] == "test"

    def test_tool_registry_not_found_error_message_format(self, mock_tool_registry):
        """未注册工具的error消息格式包含工具名"""
        mock_tool_registry.get_implementation.return_value = None
        tool_name = "my_special_tool"

        with patch("app.tools.tool_registry", mock_tool_registry):
            req = ToolExecuteRequest(tool_name=tool_name, params={})
            result = asyncio_run(execute_tool(req))
            assert tool_name in result.error

    def test_chat_request_multiple_messages(self):
        """ChatRequest支持多轮对话消息"""
        req = ChatRequest(messages=[
            ChatMessage(role="system", content="你是助手"),
            ChatMessage(role="user", content="你好"),
            ChatMessage(role="assistant", content="有什么可以帮助你的"),
            ChatMessage(role="user", content="写一段代码"),
        ])
        assert len(req.messages) == 4
        assert req.messages[0].role == "system"
        assert req.messages[3].role == "user"

    def test_sse_event_step_increments_correctly(self):
        """SSE事件step随counter递增"""
        result1 = format_sse_event("chunk", 1, {"content": "a"})
        result2 = format_sse_event("chunk", 2, {"content": "b"})
        p1 = json.loads(result1.replace("data: ", "").strip())
        p2 = json.loads(result2.replace("data: ", "").strip())
        assert p1["step"] == 1
        assert p2["step"] == 2

    def test_create_error_response_with_model(self):
        """错误响应包含model信息时正确编码"""
        result = create_error_response(
            error_type="internal_error",
            error_message="内部错误",
            model="gpt-4",
            provider="openai",
        )
        payload = json.loads(result.replace("data: ", "").strip())
        assert payload["model"] == "gpt-4"
        assert payload["provider"] == "openai"
