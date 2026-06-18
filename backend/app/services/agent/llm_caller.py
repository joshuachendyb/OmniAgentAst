# -*- coding: utf-8 -*-
"""
llm_caller — LLM调用逻辑

从universal_agent拆出 — 小沈 2026-06-17
"""

import json
from typing import Any

from app.services.agent.steps import ChunkStep
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger


async def call_llm(agent):
    """调用LLM — 纯FC模式 — FC-only重构 2026-06-11 小沈"""
    agent.llm_call_count += 1
    agent.message_builder.trim_history()

    messages = agent.message_builder.prepare_messages_for_llm()
    openai_tools = agent._get_openai_tools()

    prompt_logger = get_prompt_logger()
    prompt_logger.log_llm_call(
        round_number=agent.llm_call_count,
        messages=messages,
        model=getattr(agent.llm_client, 'model', 'unknown'),
        provider=getattr(agent.llm_client, 'provider', 'unknown'),
        call_type="tools",
        extra_params={"tool_count": len(openai_tools) if openai_tools else 0},
    )

    if not openai_tools:
        logger.error("[call_llm] 无可用工具")

    async for item in call_llm_fc_stream(agent, messages, openai_tools):
        yield item


def _build_tool_calls_response(full_content, tool_calls_result, usage_data, agent):
    """构建action类型响应并日志 — 小欧 2026-06-18 从call_llm_fc_stream提取"""
    first = tool_calls_result[0]
    built_tool_calls = []
    for tc in tool_calls_result:
        for call in tc.get("tool_calls", []):
            if isinstance(call, dict):
                built_tool_calls.append(call)

    _pending_calls = []
    for tc in tool_calls_result[1:]:
        _pending_calls.append({
            "tool_name": tc["tool_name"], "tool_params": tc["tool_params"],
            "_tool_call_id": tc.get("tool_call_id", ""),
        })

    logger.info(f"[FC] LLM原始响应(action): tool={first['tool_name']}, parallel={len(_pending_calls)}")
    prompt_logger = get_prompt_logger()
    assembled = {"content": full_content, "tool_calls": built_tool_calls}
    prompt_logger.log_llm_response(
        round_number=agent.llm_call_count, response_content=json.dumps(assembled, ensure_ascii=False),
        raw_response=json.dumps(assembled, ensure_ascii=False), response_type="action",
        finish_reason="tool_calls",
        extra_info={"tool_name": first["tool_name"], "parallel_calls": len(_pending_calls), "usage": usage_data},
    )
    return ("response", {
        "type": "action", "thought": full_content,
        "fc_context": {"tool_call_id": first.get("tool_call_id", ""), "tool_calls": built_tool_calls, "llm_content": full_content},
        "_pending_calls": _pending_calls, "tool_name": first["tool_name"],
        "tool_params": first["tool_params"], "tool_call_id": first.get("tool_call_id", ""),
        "tool_calls": first.get("tool_calls", []),
    })


def _build_answer_response(content, usage_data, agent):
    """构建answer类型响应并日志 — 小欧 2026-06-18 从call_llm_fc_stream提取"""
    logger.info(f"[FC] LLM原始响应(answer): {content}")
    prompt_logger = get_prompt_logger()
    assembled = {"content": content}
    extra_info = {"usage": usage_data} if usage_data else None
    prompt_logger.log_llm_response(
        round_number=agent.llm_call_count, response_content=content,
        raw_response=json.dumps(assembled, ensure_ascii=False), response_type="answer",
        finish_reason="stop", extra_info=extra_info,
    )
    return ("response", {"type": "answer", "content": content, "thought": ""})


async def call_llm_fc_stream(agent, messages: list, openai_tools: list):
    """FC模式流式调用 — tool_calls原生消费,不经过JSON roundtrip — 小沈 2026-06-12; 小健 2026-06-17 新增usage"""
    full_content = ""
    full_reasoning = ""
    tool_calls_result = None
    stream_error = None
    _raw_chunks: list = []
    usage_data = None

    try:
        async for chunk in agent.llm_client.request_stream(
            messages=messages, tools=openai_tools, tool_choice="auto",
        ):
            if chunk.raw_data:
                _raw_chunks.append(chunk.raw_data)

            if chunk.stream_error:
                stream_error = chunk.stream_error
                break

            if chunk.tool_calls:
                if tool_calls_result is None:
                    tool_calls_result = chunk.tool_calls
                else:
                    tool_calls_result.extend(chunk.tool_calls)

            if chunk.content:
                is_reasoning = getattr(chunk, "is_reasoning", False)
                if is_reasoning:
                    full_reasoning += chunk.content
                else:
                    full_content += chunk.content
                yield ("chunk", ChunkStep(step=agent.llm_call_count, content=chunk.content, is_reasoning=is_reasoning))

            if chunk.is_done:
                if chunk.usage:
                    usage_data = chunk.usage
                break
    except Exception as e:
        logger.error(f"[FC] 流式异常: {e}")
        raw_msg = f"LLM调用异常: {e}"
        get_prompt_logger().log_llm_response(
            round_number=agent.llm_call_count, response_content=raw_msg,
            raw_response=raw_msg, response_type="answer", finish_reason="error",
        )
        yield ("response", {"type": "answer", "content": raw_msg})
        return

    if stream_error:
        logger.error(f"[FC] 流式错误: {stream_error}")
        raw_msg = f"LLM流式错误: {stream_error}"
        get_prompt_logger().log_llm_response(
            round_number=agent.llm_call_count, response_content=raw_msg,
            raw_response=raw_msg, response_type="answer", finish_reason="error",
        )
        yield ("response", {"type": "answer", "content": raw_msg})
        return

    complete_raw = "\n".join(_raw_chunks)
    logger.debug(f"[FC] raw_response(raw): {complete_raw}")

    if tool_calls_result:
        yield _build_tool_calls_response(full_content, tool_calls_result, usage_data, agent)
        return

    content = full_content or full_reasoning or ""
    yield _build_answer_response(content, usage_data, agent)