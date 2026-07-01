# -*- coding: utf-8 -*-
"""
llm_stream — LLM流式调用+响应构建

从llm_caller更名 — 小欧 2026-06-25 名实相符
"""

import asyncio
import json
import time
from typing import Any

from app.services.agent.steps import ChunkStep
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger



def _build_tool_calls_response(full_content, tool_calls_result, usage_data, agent, full_reasoning=""):
    """构建action类型响应 — 小欧 2026-06-25 抽取_log_llm_response"""
    for tc in tool_calls_result:
        if "tool_params" in tc and tc["tool_params"] is None:
            logger.warning(f"[FC] LLM生成残缺tool_call: {tc.get('tool_name', '?')} tool_params为None, 由工具层降级校验")
    first = tool_calls_result[0]
    built_tool_calls = []
    for tc in tool_calls_result:
        for call in tc.get("tool_calls", []):
            if isinstance(call, dict):
                built_tool_calls.append(call)

    _pending_calls = []
    for tc in tool_calls_result[1:]:
        _pending_calls.append({
            "tool_name": tc.get("tool_name", ""), "tool_params": tc.get("tool_params") or {},
            "_tool_call_id": tc.get("tool_call_id") or "",
        })

    logger.info(f"[FC] LLM原始响应(action): tool={first.get('tool_name','?')}, parallel={len(_pending_calls)}")
    assembled = {"content": full_content, "tool_calls": built_tool_calls}
    _log_llm_response(agent, json.dumps(assembled, ensure_ascii=False), "action", usage_data,
                      tool_name=first.get("tool_name", "?"), parallel_calls=len(_pending_calls))
    return ("response", {
        "type": "action", "thought": full_content, "reasoning": full_reasoning,
        "fc_context": {"tool_call_id": first.get("tool_call_id") or "", "tool_calls": built_tool_calls, "llm_content": full_content},
        "_pending_calls": _pending_calls, "tool_name": first.get("tool_name", ""),
        "tool_params": first.get("tool_params") or {}, "tool_call_id": first.get("tool_call_id") or "",
        "tool_calls": first.get("tool_calls", []),
    })


def _log_llm_response(agent, assembled_json, response_type, usage_data, finish_reason=None, **extra):
    """统一LLM响应日志 — 小欧 2026-06-25 SRP提取"""
    if finish_reason is None:
        finish_reason = "tool_calls" if response_type == "action" else "stop"
    get_prompt_logger().log_llm_response(
        round_number=agent.llm_call_count, response_content=assembled_json,
        raw_response=assembled_json, response_type=response_type,
        finish_reason=finish_reason,
        extra_info={**extra, "usage": usage_data} if usage_data else {**extra},
    )


def _yield_error_response(error_msg: str, agent):
    """统一错误响应构建 — 小健 2026-06-18 DRY提取"""
    # 【E-4修复】返回type:error,DispatchHandler的error分支处理 — 小欧 2026-06-28
    logger.error(f"[FC] {error_msg}")
    _log_llm_response(agent, error_msg, "error", None, finish_reason="error")
    return ("response", {"type": "error", "content": error_msg})


def _build_answer_response(content, usage_data, agent, full_reasoning=""):
    """构建answer类型响应 — 小欧 2026-06-25 抽取_log_llm_response"""
    logger.info(f"[FC] LLM原始响应(answer): {content}")
    assembled = {"content": content}
    _log_llm_response(agent, json.dumps(assembled, ensure_ascii=False), "answer", usage_data)
    return ("response", {"type": "answer", "content": content, "reasoning": full_reasoning})



async def call_llm_stream(agent, messages: list, openai_tools: list = None):
    """FC/Text双模式流式调用 — tools=None时走Text模式(降级后备) — 小沈 2026-06-12; 小欧 2026-06-25 tools=None支持"""
    from app.services.llm.llm_constants import LLM_TOOL_CHOICE
    full_content = ""
    full_reasoning = ""
    tool_calls_result = None
    stream_error = None
    usage_data = None
    tool_choice = LLM_TOOL_CHOICE if openai_tools else None

    llm_start = time.time()
    try:
        async for chunk in agent.llm_client.request_stream(
            messages=messages, tools=openai_tools, tool_choice=tool_choice,
        ):

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
        llm_elapsed = time.time() - llm_start
    except Exception as e:
        from app.services.llm.core import FCFormatError
        if isinstance(e, FCFormatError):
            raise  # 小欧 2026-06-25: FCFormatError穿透，由call_llm_with_fallback处理
        if getattr(agent.llm_client, '_cancelled', False):
            logger.info(f"[FC] LLM调用因取消而中断, 跳过异常响应")
            return
        yield _yield_error_response(f"LLM调用异常: {e}", agent)
        return
    except asyncio.CancelledError:
        content = full_content or full_reasoning or ""
        logger.warning(f"[FC] LLM流式调用被取消, 已累积内容({len(content)}字符)")
        get_prompt_logger().log_llm_response(
            round_number=agent.llm_call_count, response_content=content,
            raw_response="", response_type="answer", finish_reason="cancelled",
        )
        raise

    if stream_error:
        if tool_calls_result:
            logger.warning(f"[FC] LLM流式错误, 丢弃{len(tool_calls_result)}个未完成的tool_calls")
            tool_calls_result = None
        yield _yield_error_response(f"LLM流式错误: {stream_error}", agent)
        return

    if tool_calls_result:
        _fc_names = [tc.get("tool_name","?") if isinstance(tc,dict) else "?" for tc in tool_calls_result]
        _p = usage_data.get('prompt_tokens','?') if usage_data else '?'; _c = usage_data.get('completion_tokens','?') if usage_data else '?'; _t = usage_data.get('total_tokens','?') if usage_data else '?'
        logger.info(f"[FC] 解析结果: tool_calls({len(tool_calls_result)})={_fc_names}, tokens={_t}(prompt={_p}+completion={_c}), llm_dur={llm_elapsed:.2f}s")
        yield _build_tool_calls_response(full_content, tool_calls_result, usage_data, agent, full_reasoning)
        return

    content = full_content or full_reasoning or ""
    _p = usage_data.get('prompt_tokens','?') if usage_data else '?'; _c = usage_data.get('completion_tokens','?') if usage_data else '?'; _t = usage_data.get('total_tokens','?') if usage_data else '?'
    logger.info(f"[FC] 解析结果: answer, len={len(content)}, tokens={_t}(prompt={_p}+completion={_c}), llm_dur={llm_elapsed:.2f}s")
    yield _build_answer_response(content, usage_data, agent)


async def call_llm_with_fallback(agent, messages, openai_tools):
    """FC模式失败时条件降级到Text模式 — 小欧 2026-06-25"""
    from app.services.llm.llm_constants import FC_FALLBACK_ENABLED, FC_MAX_RETRIES
    from app.services.llm.core import FCFormatError

    last_error = None

    for attempt in range(FC_MAX_RETRIES):
        try:
            async for item in call_llm_stream(agent, messages, openai_tools):
                yield item
            return
        except FCFormatError as e:
            last_error = e
            logger.warning(f"[Retry][L2] FC模式第{attempt+1}/{FC_MAX_RETRIES}次失败: {e}")
            await asyncio.sleep(0.5)
            continue

    if FC_FALLBACK_ENABLED:
        logger.warning(f"[FC降级] FC模式{FC_MAX_RETRIES}次重试均失败，降级到Text模式")
        async for item in call_llm_stream(agent, messages, openai_tools=None):
            yield item
    else:
        yield _yield_error_response(f"FC模式失败: {last_error}", agent)