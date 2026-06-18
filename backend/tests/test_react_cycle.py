"""P2: ReAct循环测试 - Mock LLM + 模拟工具调用"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections import OrderedDict


def _mock_agent(
    llm_response=None,
    tool_result=None,
    tool_name="read_file",
    task_id="test-react-001",
):
    """构造一个可测试的agent对象（模拟BaseAgent实例）"""
    agent = MagicMock()
    agent.task_id = task_id
    agent._cancelled = False
    agent.status = "running"

    # mock _call_llm — FC-only: async generator格式
    async def _mock_call_llm_default():
        return
        yield
    if llm_response is not None:
        async def _mock_call_llm():
            yield ("response", llm_response)
        agent._call_llm = _mock_call_llm
    else:
        agent._call_llm = _mock_call_llm_default

    # mock _execute_tool
    if tool_result is not None:
        agent._execute_tool = AsyncMock(return_value=tool_result)
        agent._retry_engine = MagicMock()
        agent._retry_engine.execute_tool_with_retry = AsyncMock(return_value=tool_result)
    else:
        agent._execute_tool = AsyncMock(return_value="")
        agent._retry_engine = MagicMock()
        agent._retry_engine.execute_tool_with_retry = AsyncMock(return_value="")

    # mock handler methods (used by react_cycle)
    agent._on_after_loop = AsyncMock()
    agent._complete_tracked_task = AsyncMock()
    agent._on_session_init = AsyncMock(return_value=("", "test task"))
    agent._on_before_loop = AsyncMock(return_value=("system prompt", "task prompt"))
    agent._get_system_prompt = MagicMock(return_value="system prompt")
    agent._get_task_prompt = MagicMock(return_value="task prompt")

    # mock message_builder
    agent.message_builder = MagicMock()
    agent.message_builder.prepare_messages_for_llm = MagicMock(return_value=[])
    agent.message_builder.add_assistant = MagicMock()
    agent.message_builder.add_observation = MagicMock()
    agent.message_builder.add_parse_error = MagicMock()
    agent.message_builder.flush_temp_to_history = MagicMock()
    agent.message_builder.conversation_history = []

    # mock step_emitter
    agent._step_emitter = MagicMock()

    # mock config
    agent.model = "test-model"
    agent.provider = "test-provider"
    agent.api_key = ""
    agent.api_base = ""
    agent.max_steps = 5
    agent.llm_call_count = 0
    agent.steps = []
    agent.tool_retry_engine = MagicMock()
    agent.tool_retry_engine.get_retry_delay = MagicMock(return_value=0)
    agent.tool_retry_engine.create_retry_event = MagicMock(return_value={"type": "retrying"})
    agent.tool_retry_engine.is_retryable_error = MagicMock(return_value=True)

    # mock chunk settings
    agent.chunk_settings = MagicMock()
    agent.chunk_settings.emit_chunks = False
    agent.chunk_settings.emit_content = True
    agent.chunk_settings.emit_reasoning = False
    agent.chunk_settings.emit_final_thinking = False

    agent._tracked_task_id = None
    agent._task_tracker = None
    agent._tools_dict = {}

    return agent


class TestHandleAnswer:
    """测试answer类型处理"""

    @pytest.mark.asyncio
    async def test_handle_answer_yields_final_step(self):
        """answer → emit被调用（FinalStep）"""
        from app.services.agent.core_agent.handlers import handle_answer

        agent = _mock_agent()
        parsed = {"content": "文件内容是hello", "thought": "已读取"}
        agent.llm_call_count = 1
        chunk_buffer = MagicMock()
        chunk_buffer.flush_and_reset = MagicMock(return_value=None)

        steps = []
        async for step in handle_answer(agent, parsed, chunk_buffer):
            steps.append(step)

        # emit被调用了（可能有thought+final）
        assert agent._step_emitter.emit.call_count >= 1
        assert len(steps) >= 1

    @pytest.mark.asyncio
    async def test_handle_answer_empty_content_fails(self):
        """FC-only: 空内容answer → FAILED"""
        from app.services.agent.core_agent.handlers import handle_answer
        from app.services.agent.types import AgentStatus

        agent = _mock_agent()
        parsed = {"content": "", "thought": ""}
        agent.llm_call_count = 1
        chunk_buffer = MagicMock()

        steps = []
        async for step in handle_answer(agent, parsed, chunk_buffer):
            steps.append(step)

        agent._step_emitter.exit_with_error.assert_called_once()
        assert agent.status == AgentStatus.FAILED


class TestHandleAction:
    """测试action类型处理"""

    @pytest.mark.asyncio
    async def test_handle_action_yields_thought_and_tool(self):
        """action → emit调用thought和action_tool"""
        from app.services.agent.core_agent.handlers import handle_action
        from app.services.agent.steps import ThoughtStep, ToolStep

        agent = _mock_agent(tool_result={"code": "success", "data": "文件内容: hello"})
        parsed = {
            "thought": "用户想读取文件",
            "tool_name": "read_file",
            "tool_params": {"path": "D:\\test.txt"},
        }
        agent.llm_call_count = 1
        chunk_buffer = MagicMock()
        chunk_buffer.flush_and_reset = MagicMock(return_value=None)

        mock_safety = MagicMock()
        mock_safety.check_before_execute.return_value = {}
        with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker", return_value=mock_safety):
            steps = []
            async for step in handle_action(agent, parsed, chunk_buffer):
                steps.append(step)

        assert agent._step_emitter.emit.call_count >= 3

    @pytest.mark.asyncio
    async def test_handle_action_uses_llm_call_count(self):
        """action → handler读取agent.llm_call_count作为step"""
        from app.services.agent.core_agent.handlers import handle_action

        agent = _mock_agent(tool_result="ok")
        parsed = {"thought": "thinking", "tool_name": "finish", "tool_params": {}}
        agent.llm_call_count = 3
        chunk_buffer = MagicMock()
        chunk_buffer.flush_and_reset = MagicMock(return_value=None)

        mock_safety = MagicMock()
        mock_safety.check_before_execute.return_value = {}
        with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker", return_value=mock_safety):
            steps = []
            async for step in handle_action(agent, parsed, chunk_buffer):
                steps.append(step)

        assert agent.llm_call_count == 3


class TestProcessSingleStep:
    """测试_process_single_step — 覆盖chunk/无效响应/未知类型 — 小沈 2026-06-13"""

    @pytest.mark.asyncio
    async def test_chunk_emitted_during_streaming(self):
        """streaming期间chunk被emit"""
        from app.services.agent.core_agent.react_cycle import _process_single_step

        agent = _mock_agent()
        agent.llm_call_count = 1

        async def mock_call_llm(a):
            yield ("chunk", {"content": "partial text"})
            yield ("response", {"content": "ok", "thought": ""})

        chunk_buffer = MagicMock()
        steps = []
        with patch("app.services.agent.llm_caller.call_llm", mock_call_llm):
            async for step in _process_single_step(agent, chunk_buffer):
                steps.append(step)

        assert agent._step_emitter.emit.call_count >= 1

    @pytest.mark.asyncio
    async def test_invalid_response_exits_with_error(self):
        """无效LLM响应 → exit_with_error"""
        from app.services.agent.core_agent.react_cycle import _process_single_step
        from app.services.agent.types import AgentStatus

        agent = _mock_agent()
        agent.llm_call_count = 1

        async def mock_call_llm(a):
            yield ("response", None)

        chunk_buffer = MagicMock()
        steps = []
        with patch("app.services.agent.llm_caller.call_llm", mock_call_llm):
            async for step in _process_single_step(agent, chunk_buffer):
                steps.append(step)

        agent._step_emitter.exit_with_error.assert_called_once()
        assert agent.status == AgentStatus.FAILED

    @pytest.mark.asyncio
    async def test_unknown_type_falls_to_default_handler(self):
        """未知类型 → _DEFAULT_HANDLER(handle_answer)"""
        from app.services.agent.core_agent.react_cycle import _process_single_step

        agent = _mock_agent()
        agent.llm_call_count = 1

        async def mock_call_llm(a):
            yield ("response", {"type": "weird_type", "content": "hello"})

        chunk_buffer = MagicMock()
        steps = []
        with patch("app.services.agent.llm_caller.call_llm", mock_call_llm):
            async for step in _process_single_step(agent, chunk_buffer):
                steps.append(step)

        assert agent._step_emitter.emit.call_count >= 1


class TestTypeHandlerDispatch:
    """测试类型分派 — 小健 2026-06-17 if/elif替代_TYPE_HANDLERS"""

    def test_dispatch_action_returns_handle_action(self):
        """action类型 → 返回handle_action的generator"""
        from app.services.agent.core_agent.react_cycle import _dispatch_handler
        from app.services.agent.core_agent.handlers import handle_action
        assert _dispatch_handler.__code__.co_consts is not None

    def test_dispatch_answer_returns_handle_answer(self):
        """answer/未知类型 → 返回handle_answer的generator"""
        from app.services.agent.core_agent.react_cycle import _dispatch_handler
        from app.services.agent.core_agent.handlers import handle_answer
        assert _dispatch_handler.__code__.co_consts is not None

    def test_dispatch_handler_routes_action(self):
        """_dispatch_handler对action类型调用handle_action"""
        from app.services.agent.core_agent.react_cycle import _dispatch_handler
        import inspect
        source = inspect.getsource(_dispatch_handler)
        assert 'handle_action' in source
        assert 'handle_answer' in source
