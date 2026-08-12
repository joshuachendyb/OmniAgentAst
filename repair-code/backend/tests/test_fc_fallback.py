# -*- coding: utf-8 -*-
"""test"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Any


from app.services.llm.core import LLMResponseError


class _ChunkResult:
    def __init__(self, content="", tool_calls=None, is_done=False, usage=None, stream_error=None, is_reasoning=False):
        self.content = content
        self.tool_calls = tool_calls
        self.is_done = is_done
        self.usage = usage
        self.stream_error = stream_error
        self.is_reasoning = is_reasoning


def _make_fc_tool_call(tool_name="readtext", tool_params='{"path":"E:/test.txt"}', call_id="call_abc123"):
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


# 鈹查鈹查鈹查 在写櫙1: FC妯″紡户愬姛 鈫?标存接返回结果 鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_fc_success_no_fallback():
    """test"""
    from app.services.agent.llm_stream import call_llm_with_fallback

    agent = _make_agent()
    messages = [{"role": "user", "content": "hello"}]
    openai_tools = [{"type": "function", "function": {"name": "readtext"}}]

    call_count = 0

    async def mock_request_stream(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LLMResponseError(message="tool_calls名有暟解ｆ瀽失败", details={"failed_tools": ["readtext"]})
        yield _ChunkResult(content="thinking...", is_reasoning=True)
        yield _ChunkResult(tool_calls=[_make_fc_tool_call()], is_done=True, usage={"total_tokens": 100})

    agent.llm_client.request_stream = mock_request_stream

    results = await _collect_results(call_llm_with_fallback(agent, messages, openai_tools))

    response_results = [r for r in results if r[0] == "response"]
    assert len(response_results) == 1, "里嶈瘯户愬姛否庡应有中猺esponse"
    assert response_results[0][1]["type"] == "action", "里嶈瘯户愬姛应该繑回瀉ction类型"
    assert call_count == 2, "应该皟用?娆LM,?娆″け璐?1娆℃垚动燂級"


# 鈹查鈹查鈹查 在写櫙3: FC妯″紡失败2娆″悗闄嶇骇列癟ext妯″紡 鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_fc_fallback_to_text():
    """fc fallback to text"""
    from app.services.agent.llm_stream import call_llm_with_fallback

    agent = _make_agent()
    messages = [{"role": "user", "content": "hello"}]
    openai_tools = [{"type": "function", "function": {"name": "readtext"}}]

    call_count = 0

    async def mock_request_stream(**kwargs):
        nonlocal call_count
        call_count += 1
        tools = kwargs.get("tools")
        if tools is not None:
            raise LLMResponseError(message="tool_calls名有暟解ｆ瀽失败", details={"failed_tools": ["readtext"]})
        yield _ChunkResult(content="I can help you with that.", is_done=True, usage={"total_tokens": 50})

    agent.llm_client.request_stream = mock_request_stream

    results = await _collect_results(call_llm_with_fallback(agent, messages, openai_tools))

    response_results = [r for r in results if r[0] == "response"]
    assert len(response_results) == 1, "闄嶇骇否庡应有中猺esponse"
    assert response_results[0][1]["type"] == "answer", "闄嶇骇列癟ext妯″紡应该繑回瀉nswer类型"
    assert call_count == 3, f"应该皟用?娆LM,?娆C失败+1娆ext闄嶇骇,夛,实际{call_count}娆?"


# 鈹查鈹查鈹查 在写櫙4: FC闄嶇骇鍏抽棴 鈫?返回错误 鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查

@pytest.mark.asyncio
async def test_fc_fallback_disabled():
    """fc fallback disabled"""
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

    assert received_tools is None, "openai_tools=None should make request_stream tools=None"
    response_results = [r for r in results if r[0] == "response"]
    assert len(response_results) == 1, "Text妯″紡应该繑回?中猺esponse"
    assert response_results[0][1]["type"] == "answer", "Text妯″紡应该繑回瀉nswer类型"


# 鈹查鈹查鈹查 在写櫙6: LLMResponseError异常类绘认伐你?鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查

def test_fc_format_error_exception():
    """LLMResponseError should be createable and work correctly"""
    error = LLMResponseError(message="test error")
    assert str(error) == "test error"
    assert isinstance(error, Exception)
    assert error.details == {}

    error_with_details = LLMResponseError(message="test error", details={"failed_parses": ["tool1"]})
    assert str(error_with_details) == "test error"
    assert error_with_details.details == {"failed_parses": ["tool1"]}

    with pytest.raises(LLMResponseError, match="解ｆ瀽失败"):
        raise LLMResponseError(message="tool_calls解ｆ瀽失败")