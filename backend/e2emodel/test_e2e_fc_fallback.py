# -*- coding: utf-8 -*-
"""FC降级机制集成测试

验证FCFormatError触发后，call_llm_with_fallback能正确降级到Text模式

测试场景:
  1. FC模式成功 → 直接返回结果，不降级
  2. FC模式失败1次后成功 → 重试成功，不降级
  3. FC模式失败2次后降级 → 降级到Text模式，返回answer
  4. FC降级关闭 → FC_MAX_RETRIES耗尽后返回错误
  5. call_llm_stream tools=None走Text模式
  6. FCFormatError异常类正确工作

-- 小欧 2026-06-25
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Any


from app.services.llm.core import FCFormatError


class _ChunkResult:
    def __init__(self, content="", tool_calls=None, is_done=False, usage=None, stream_error=None, is_reasoning=False):
        self.content = content
        self.tool_calls = tool_calls
        self.is_done = is_done
        self.usage = usage
        self.stream_error = stream_error
        self.is_reasoning = is_reasoning


def _make_fc_tool_call(tool_name="read_text_file", tool_params='{"path":"E:/test.txt"}', call_id="call_abc123"):
    return {
        "tool_name": tool_name,
        "tool_params": tool_params,
        "tool_call_id": call_id,
        "tool_calls": [{"id": call_id, "type": "function", "function": {"name": tool_name, "arguments": tool_params}}],
    }


def _make_agent():
    agent = MagicMock()
    agent.llm_call_count = 0
    agent.llm_client = MagicMock()
    agent.llm_client._cancelled = False
    agent.llm_client.model = "test-model"
    agent.llm_client.provider = "test-provider"
    return agent


async def _collect_results(gen):
    results = []
    async for item in gen:
        results.append(item)
    return results


# ─── 场景1: FC模式成功 → 直接返回结果 ──────────────────────────

@pytest.mark.asyncio
async def test_fc_success_no_fallback():
    """FC模式成功时不应降级"""
    from app.services.agent.llm_stream import call_llm_with_fallback

    agent = _make_agent()
    messages = [{"role": "user", "content": "hello"}]
    openai_tools = [{"type": "function", "function": {"name": "read_text_file"}}]

    fc_chunks = [
        _ChunkResult(content="thinking...", is_reasoning=True),
        _ChunkResult(tool_calls=[_make_fc_tool_call()], is_done=True, usage={"total_tokens": 100}),
    ]

    async def mock_request_stream(**kwargs):
        for chunk in fc_chunks:
            yield chunk

    agent.llm_client.request_stream = mock_request_stream

    results = await _collect_results(call_llm_with_fallback(agent, messages, openai_tools))

    response_results = [r for r in results if r[0] == "response"]
    assert len(response_results) == 1, "应有1个response"
    assert response_results[0][1]["type"] == "action", "FC成功应返回action类型"


# ─── 场景2: FC模式失败1次后成功 → 重试成功 ──────────────────────

@pytest.mark.asyncio
async def test_fc_retry_success():
    """FC模式失败1次后重试成功，不应降级"""
    from app.services.agent.llm_stream import call_llm_with_fallback

    agent = _make_agent()
    messages = [{"role": "user", "content": "hello"}]
    openai_tools = [{"type": "function", "function": {"name": "read_text_file"}}]

    call_count = 0

    async def mock_request_stream(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise FCFormatError("tool_calls参数解析失败: ['read_text_file']")
        yield _ChunkResult(content="thinking...", is_reasoning=True)
        yield _ChunkResult(tool_calls=[_make_fc_tool_call()], is_done=True, usage={"total_tokens": 100})

    agent.llm_client.request_stream = mock_request_stream

    results = await _collect_results(call_llm_with_fallback(agent, messages, openai_tools))

    response_results = [r for r in results if r[0] == "response"]
    assert len(response_results) == 1, "重试成功后应有1个response"
    assert response_results[0][1]["type"] == "action", "重试成功应返回action类型"
    assert call_count == 2, "应调用2次LLM（1次失败+1次成功）"


# ─── 场景3: FC模式失败2次后降级到Text模式 ───────────────────────

@pytest.mark.asyncio
async def test_fc_fallback_to_text():
    """FC模式2次重试均失败后降级到Text模式"""
    from app.services.agent.llm_stream import call_llm_with_fallback

    agent = _make_agent()
    messages = [{"role": "user", "content": "hello"}]
    openai_tools = [{"type": "function", "function": {"name": "read_text_file"}}]

    call_count = 0

    async def mock_request_stream(**kwargs):
        nonlocal call_count
        call_count += 1
        tools = kwargs.get("tools")
        if tools is not None:
            raise FCFormatError("tool_calls参数解析失败: ['read_text_file']")
        yield _ChunkResult(content="I can help you with that.", is_done=True, usage={"total_tokens": 50})

    agent.llm_client.request_stream = mock_request_stream

    results = await _collect_results(call_llm_with_fallback(agent, messages, openai_tools))

    response_results = [r for r in results if r[0] == "response"]
    assert len(response_results) == 1, "降级后应有1个response"
    assert response_results[0][1]["type"] == "answer", "降级到Text模式应返回answer类型"
    assert call_count == 3, f"应调用3次LLM（2次FC失败+1次Text降级），实际{call_count}次"


# ─── 场景4: FC降级关闭 → 返回错误 ──────────────────────────────

@pytest.mark.asyncio
async def test_fc_fallback_disabled():
    """FC降级关闭时，重试耗尽后返回错误"""
    from app.services.agent.llm_stream import call_llm_with_fallback, _yield_error_response

    agent = _make_agent()
    messages = [{"role": "user", "content": "hello"}]
    openai_tools = [{"type": "function", "function": {"name": "read_text_file"}}]

    call_count = 0

    async def mock_call_llm_stream(agent, messages, openai_tools=None):
        nonlocal call_count
        call_count += 1
        if openai_tools is not None:
            raise FCFormatError("tool_calls参数解析失败: ['read_text_file']")
        yield ("response", {"type": "answer", "content": "text fallback"})

    with patch("app.services.agent.llm_stream.call_llm_stream", mock_call_llm_stream):
        with patch("app.services.llm.llm_constants.FC_FALLBACK_ENABLED", False):
            results = await _collect_results(call_llm_with_fallback(agent, messages, openai_tools))

            response_results = [r for r in results if r[0] == "response"]
            assert len(response_results) == 1, "降级关闭时应返回1个错误response"
            assert response_results[0][1]["type"] == "error", "错误response应为error类型"
            assert "FC模式失败" in response_results[0][1]["content"], f"错误信息应包含FC模式失败，实际: {response_results[0][1]['content']}"
            assert call_count == 2, f"应调用2次LLM（FC_MAX_RETRIES=2），实际{call_count}次"


# ─── 场景5: call_llm_stream tools=None走Text模式 ────────────────

@pytest.mark.asyncio
async def test_call_llm_stream_text_mode():
    """call_llm_stream 传入openai_tools=None时应走Text模式"""
    from app.services.agent.llm_stream import call_llm_stream

    agent = _make_agent()
    messages = [{"role": "user", "content": "hello"}]

    text_chunks = [
        _ChunkResult(content="Hello! ", is_reasoning=False),
        _ChunkResult(content="How can I help?", is_reasoning=False),
        _ChunkResult(is_done=True, usage={"total_tokens": 50}),
    ]

    received_tools = "NOT_SET"

    async def mock_request_stream(**kwargs):
        nonlocal received_tools
        received_tools = kwargs.get("tools", "NOT_SET")
        for chunk in text_chunks:
            yield chunk

    agent.llm_client.request_stream = mock_request_stream

    results = await _collect_results(call_llm_stream(agent, messages, openai_tools=None))

    assert received_tools is None, f"openai_tools=None时request_stream应收到tools=None，实际收到{received_tools}"
    response_results = [r for r in results if r[0] == "response"]
    assert len(response_results) == 1, "Text模式应返回1个response"
    assert response_results[0][1]["type"] == "answer", "Text模式应返回answer类型"


# ─── 场景6: FCFormatError异常类正确工作 ─────────────────────────

def test_fc_format_error_exception():
    """FCFormatError应能正确创建和捕获"""
    error = FCFormatError("test error")
    assert str(error) == "test error"
    assert isinstance(error, Exception)

    with pytest.raises(FCFormatError, match="解析失败"):
        raise FCFormatError("tool_calls解析失败")
