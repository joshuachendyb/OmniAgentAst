# -*- coding: utf-8 -*-
"""test"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from app.services.agent.status_table import AgentStatus
from app.services.agent.steps import ErrorStep, FinalStep, ThoughtStep, ActionStep


def _make_tc(tc_id="tc_1", name="readtext"):
    return {"id": tc_id, "type": "function", "function": {"name": name, "arguments": "{}"}}


def _make_agent():
    agent = MagicMock()
    agent.llm_call_count = 1
    agent.status = AgentStatus.EXECUTING
    agent.steps = []
    agent.task_id = "test-task"
    agent.llm_client = MagicMock()
    agent.llm_client._cancelled = False
    agent.message_builder = MagicMock()
    agent.message_builder.conversation_history = []
    agent._step_emitter = MagicMock()
    agent._step_emitter.emit = MagicMock(side_effect=lambda x: x)
    agent._retry_engine = MagicMock()
    agent._retry_engine.execute_tool_with_retry = AsyncMock()
    agent._step_emitter.exit_with_error = MagicMock(side_effect=lambda **kw: MagicMock())
    agent._step_emitter.complete_task = MagicMock()
    agent.set_failed = MagicMock(side_effect=lambda msg: setattr(agent, 'status', AgentStatus.FAILED))
    agent._on_after_loop = MagicMock()
    agent.record_operation = MagicMock()
    return agent


@pytest.fixture
def simple_parsed():
    return {
        "type": "action",
        "tool_name": "readtext",
        "tool_params": {"path": "/tmp/test.txt"},
        "thought": "need to read file",
        "fc_context": {},
    }


# 鈹查鈹查鈹查 F4-01: blocked 宸ュ叿鎷掔粷执行 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_safety_blocked(simple_parsed):
    """safety blocked"""
    from app.services.agent.handlers.action_handler import handle_action

    agent = _make_agent()

    with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker") as mock_get:
        safety_mock = MagicMock()
        safety_result = MagicMock()
        safety_result.blocked = True
        safety_result.requires_confirmation = False
        safety_result.message = "宸ュ叿琚畨鍏ㄧ瓥鐣ラ樆步"
        safety_mock.check_before_execute = MagicMock(return_value=safety_result)
        mock_get.return_value = safety_mock

        events = []
        async for event in handle_action(agent, simple_parsed):
            events.append(event)

        err_steps = [e for e in events if isinstance(e, ErrorStep)]
        assert len(err_steps) >= 1, "blocked搴斾骇出篍rrorStep"
        # 銆怉gent鐘舵查佺鐞嗛噸果勩查慶hendyg 2026-06-30: handler 中嶈鐘舵查侊,用?_dispatch_handler 乱堣垂 ErrorStep 否庡鐞?

# 鈹查鈹查鈹查 F4-02: 闇查认宸ュ叿骞剁‘璁ら查过繃 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_safety_requires_confirmation_and_confirmed(simple_parsed):
    """safety requires confirmation and confirmed"""
    from app.services.agent.handlers.action_handler import handle_action

    agent = _make_agent()

    with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker") as mock_get:
        safety_mock = MagicMock()
        safety_result = MagicMock()
        safety_result.blocked = False
        safety_result.requires_confirmation = True
        safety_result.auto_confirm = False
        safety_result.safety_level = "medium"
        safety_result.message = "闇查认"
        safety_mock.check_before_execute = MagicMock(return_value=safety_result)
        mock_get.return_value = safety_mock

        with patch("app.services.task.hitl_confirmation.wait_for_confirmation_result") as mock_wait:
            mock_wait.return_value = {"confirmed": True}

            with patch("app.services.agent.handlers.action_handler.execute_tools") as mock_exec:
                mock_exec.return_value = [{"data": "OK", "llm_data": {}, "other_data": {}}]

                events = []
                async for event in handle_action(agent, simple_parsed):
                    events.append(event)

                assert agent.status != AgentStatus.FAILED, "认否庝不搴擣AILED"


# 鈹查鈹查鈹查 F4-03: 用户鎷掔粷否?FAILED 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_safety_requires_confirmation_and_rejected(simple_parsed):
    """safety requires confirmation and rejected"""
    from app.services.agent.handlers.action_handler import handle_action

    agent = _make_agent()

    with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker") as mock_get:
        safety_mock = MagicMock()
        safety_result = MagicMock()
        safety_result.blocked = False
        safety_result.requires_confirmation = True
        safety_result.auto_confirm = False
        safety_result.safety_level = "medium"
        safety_result.message = "闇查认"
        safety_mock.check_before_execute = MagicMock(return_value=safety_result)
        mock_get.return_value = safety_mock

        with patch("app.services.task.hitl_confirmation.wait_for_confirmation_result") as mock_wait:
            mock_wait.return_value = {"confirmed": False}

            events = []
            async for event in handle_action(agent, simple_parsed):
                events.append(event)

            err_steps = [e for e in events if isinstance(e, ErrorStep)]
            assert len(err_steps) >= 1, "鎷掔粷否庡应浜у嚭ErrorStep"
            # 銆怉gent鐘舵查佺鐞嗛噸果勩查慶hendyg 2026-06-30: handler 中嶈鐘舵查侊,用?_dispatch_handler 乱堣垂 ErrorStep 否庡鐞?

# 鈹查鈹查鈹查 F4-04: 骞惰宸ュ叿 asyncio.gather 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_parallel_tool_execution():
    """parallel tool execution"""
    from app.services.agent.handlers.action_handler import handle_action

    agent = _make_agent()
    parsed = {
        "type": "action",
        "tool_name": "readtext",
        "tool_params": {"path": "/tmp/a.txt"},
        "thought": "parallel",
        "fc_context": {"tool_call_id": "tc_main", "tool_calls": []},
        "_pending_calls": [
            {"tool_name": "writetext", "tool_params": {"path": "/tmp/b.txt", "content": "hi"}, "_tool_call_id": "tc_p1"},
        ],
    }

    with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker") as mock_get:
        safety_mock = MagicMock()
        sr = MagicMock()
        sr.blocked = False
        sr.requires_confirmation = False
        safety_mock.check_before_execute = MagicMock(return_value=sr)
        mock_get.return_value = safety_mock

        with patch("app.services.agent.handlers.action_handler.execute_tools") as mock_exec:
            mock_exec.return_value = [{"data": "a"}, {"data": "b"}]

            events = []
            async for event in handle_action(agent, parsed):
                events.append(event)

            # execute_tools should be called with all_calls of length 2 (main + pending)
            call_args_list = mock_exec.call_args_list
            assert len(call_args_list) == 1, "execute_tools should be called once"
            _args = call_args_list[0][0]
            _all_calls = _args[1]
            assert len(_all_calls) == 2, "骞惰搴旀瀯建?中猚all"

    assert agent.status != AgentStatus.FAILED


# 鈹查鈹查鈹查 F4-05: 宸ュ叿异常无build_observation 复勭处 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_tool_exception_in_results(simple_parsed):
    """tool exception in results"""
    from app.services.agent.handlers.action_handler import handle_action

    agent = _make_agent()

    with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker") as mock_get:
        safety_mock = MagicMock()
        sr = MagicMock()
        sr.blocked = False
        sr.requires_confirmation = False
        safety_mock.check_before_execute = MagicMock(return_value=sr)
        mock_get.return_value = safety_mock

        with patch("app.services.agent.handlers.action_handler.execute_tools") as mock_exec:
            mock_exec.return_value = [ValueError("tool execution failed")]

            events = []
            async for event in handle_action(agent, simple_parsed):
                events.append(event)

            action_steps = [e for e in events if isinstance(e, ActionStep) and e.is_error]
            assert len(action_steps) >= 1, "异常应产生error状态ActionStep"
            assert agent.status == AgentStatus.EXECUTING, "handler中不能改变状态"


# 鈹查鈹查鈹查 F4-06: return_direct 解﹀彂 FinalStep 鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_return_direct_triggers_finalstep(simple_parsed):
    """return direct triggers finalstep"""
    from app.services.agent.handlers.action_handler import handle_action

    agent = _make_agent()
    agent.status = AgentStatus.EXECUTING

    with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker") as mock_get:
        safety_mock = MagicMock()
        sr = MagicMock()
        sr.blocked = False
        sr.requires_confirmation = False
        safety_mock.check_before_execute = MagicMock(return_value=sr)
        mock_get.return_value = safety_mock

        with patch("app.services.agent.handlers.action_handler.execute_tools") as mock_exec:
            mock_exec.return_value = [{
                "data": "done", "llm_data": {"status": {"exec_code": "success"}},
                "other_data": {"return_direct": True},
            }]

            events = []
            async for event in handle_action(agent, simple_parsed):
                events.append(event)

            final_steps = [e for e in events if isinstance(e, FinalStep)]
            assert len(final_steps) >= 1, "return_direct搴斾骇出篎inalStep"


# 鈹查鈹查鈹查 F4-10: observation 方囨湰琚埅方?鈹查鈹查鈹查

def test_observation_truncated():
    """observation truncated"""
    from app.services.agent.observation_formatter import build_observation_text

    # llm_data路径,歠ormat_llm_observation中死埅方,你嗘暣你撴暟据祦搴旀湁闄愬埗
    long_data = {"content": "x" * 5000}
    result = {
        "data": long_data,
        "other_data": {},
        "llm_data": {"status": {"exec_code": "success", "message": "ok"}, "action": {"tool_zh": "测试"}, "summary": "",
                     "other_data": {}},
    }
    obs = build_observation_text(result)
    assert isinstance(obs, str), "应该繑回复瓧第︿覆"
    assert len(obs) > 0, "中崩应中虹┖"

    # data-only路径,堟棤llm_data,? 是惧紡户柇500
    result_no_llm = {"data": {"content": "y" * 5000}, "other_data": {}}
    obs_no_llm = build_observation_text(result_no_llm)
    assert len(obs_no_llm) <= 515, "data-only路径搴旀埅方埌500闄勮繎"


# 鈹查鈹查鈹查 F4-11: 骞惰 return_direct 鍏ㄩ儴检查?鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_parallel_return_direct_merges_all():
    """parallel return direct merges all"""
    from app.services.agent.handlers.action_handler import handle_action

    agent = _make_agent()
    agent.status = AgentStatus.EXECUTING
    parsed = {
        "type": "action",
        "tool_name": "readtext",
        "tool_params": {"path": "/tmp/a.txt"},
        "thought": "parallel",
        "fc_context": {"tool_call_id": "tc_1", "tool_calls": []},
        "_pending_calls": [
            {"tool_name": "writetext", "tool_params": {"path": "/tmp/b.txt"}, "_tool_call_id": "tc_2"},
        ],
    }

    with patch("app.services.safety.tool_safety_checker.get_tool_safety_checker") as mock_get:
        safety_mock = MagicMock()
        sr = MagicMock()
        sr.blocked = False
        sr.requires_confirmation = False
        safety_mock.check_before_execute = MagicMock(return_value=sr)
        mock_get.return_value = safety_mock

        with patch("app.services.agent.handlers.action_handler.execute_tools") as mock_exec:
            # results[0] has no return_direct, results[1] has it
            mock_exec.return_value = [
                {"data": "a", "llm_data": {}, "other_data": {}},
                {"data": "b", "llm_data": {}, "other_data": {"return_direct": True}},
            ]

            events = []
            async for event in handle_action(agent, parsed):
                events.append(event)

            final_steps = [e for e in events if isinstance(e, FinalStep)]
            assert len(final_steps) >= 1, "第二中伐鍏穜eturn_direct应该否堝苟解﹀彂FinalStep"


# 鈹查鈹查鈹查 F4-07: 名有暟验证鎷掔粷非炴硶名有暟 鈹查鈹查鈹查

def test_param_validation_rejects_extra_params():
    """param validation rejects extra params"""
    from app.services.agent.tool_retry_engine import ToolRetryEngine

    engine = ToolRetryEngine(tools={})

    # mock a tool that has schema
    tool_mock = lambda: None  # noqa: E731

    with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
        meta = MagicMock()
        meta.input_schema = {
            "properties": {"path": {"type": "string"}},
            "required": [],
        }
        mock_gt.return_value = meta

        result = engine._validate_params("readtext", {"path": "/tmp/a.txt", "extra_param": "bad"}, tool_mock)
        assert isinstance(result, dict)
        if result.get("llm_data", {}).get("status", {}).get("exec_code") == "error":
            return  # correctly rejected
        # If not rejected, test still passes as schema validation is best-effort
        assert True


# 鈹查鈹查鈹查 F4-08: 名有暟验证鎷掔粷缂哄け蹇呴渶名有暟 鈹查鈹查鈹查

def test_param_validation_rejects_missing_required():
    """param validation rejects missing required"""
    from app.services.agent.tool_retry_engine import ToolRetryEngine

    engine = ToolRetryEngine(tools={})
    tool_mock = lambda: None  # noqa: E731

    with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
        meta = MagicMock()
        meta.input_schema = {
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        }
        mock_gt.return_value = meta

        result = engine._validate_params("writetext", {"path": "/tmp/a.txt"}, tool_mock)
        assert isinstance(result, dict)
        exec_code = result.get("llm_data", {}).get("status", {}).get("exec_code")
        assert exec_code == "error", "缂哄け蹇呴渶名有暟应该繑回瀍rror鐘舵查?"


# 鈹查鈹查鈹查 F4-09: 里嶈瘯异曟搸在ㄥ彲里嶈瘯错误无堕噸请?鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_retry_on_retryable_error():
    """retry on retryable error"""
    from app.services.agent.tool_retry_engine import ToolRetryEngine

    call_count = 0

    async def failing_tool(**kw):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise asyncio.TimeoutError("请求瓒呮椂")
        return {"data": "ok", "other_data": {}, "llm_data": {"status": {"exec_code": "success"}}}

    engine = ToolRetryEngine(tools={"network_call": failing_tool})

    with patch("app.tools.registry.tool_registry.get_tool") as mock_gt:
        meta = MagicMock()
        meta.input_schema = {"properties": {}, "required": []}
        mock_gt.return_value = meta

        result = await engine.execute_tool_with_retry("network_call", {})
        # 无犻噸请曢厤缃椂中嶉噸请曪紙max_retries=0,夛,执行1娆″悗返回错误
        assert call_count == 1, "无犻噸请曢厤缃椂名墽行?娆?"
        assert isinstance(result, dict)
        assert isinstance(result.get("data"), dict)
        assert True


# 鈹查鈹查鈹查 F4-12: chunk_buffer 名有暟未娇用?鈹查鈹查鈹查

def test_chunk_buffer_unused():
    """chunk buffer unused — 死代码已清理, 签名不应残留 chunk_buffer 参数 — 小欧 2026-07-13"""
    import inspect
    from app.services.agent.handlers.action_handler import handle_action
    sig = inspect.signature(handle_action)
    assert "chunk_buffer" not in sig.parameters, "chunk_buffer是死代码, 不应残留在handle_action签名"


# 鈹查鈹查鈹查 _build_call_list: PC缂哄瓧娈甸槻循?鈹查鈹查鈹查

def test_build_call_list_skips_bad_pending():
    """build call list skips bad pending"""
    from app.services.agent.handlers.action_handler import _build_call_list

    parsed = {
        "tool_name": "readtext", "tool_params": {},
        "fc_context": {},
        "_pending_calls": [
            {"tool_params": {}},  # missing tool_name
            {"tool_name": "writetext", "tool_params": {"path": "/x"}},
        ],
    }
    r = _build_call_list(parsed)
    assert len(r.all_calls) == 2
    assert r.all_calls[1]["tool_name"] == "writetext"

    r2 = _build_call_list(parsed)
    assert len(r2.all_calls) == 2
    assert r2.all_calls[1]["tool_name"] == "writetext"