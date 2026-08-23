
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 小欧 FC_FALLBACK_ENABLED/FC_MAX_RETRIES/LLM_TOOL_CHOICE导入源由base_service改为app.constants
# 2026-07-15 小欧 修复call_llm_with_fallback:FC重试循环内拦截type:error响应
# 2026-07-16 小欧 新增XML tool_call提取拦截点; M5解决空错误日志丢失根因
# 2026-07-17 小沈 FCFormatError→LLMResponseError等重命名
# 2026-07-18 小欧 #31 fix: fallback前reset cancel状态; #39 fix: XML兜底补WARNING
# 2026-07-19 小欧 fc_context新增llm_reasoning字段(从stream reasoning累加结果传递)
# 2026-07-19 小欧 _build_answer_response新增finish_reason参数(SSE最后chunk的stop/length/content_filter,与usage同级提取)
# 2026-07-19 小欧 改善: _finish_reason用None哨兵(空值走_log_llm_response回退stop,日志正确)
# 2026-07-22 小欧 action/answer 响应 dict 加入 usage 字段，供 react_cycle 提取 prompt_tokens 做精确裁剪触发
# 2026-07-22 小欧 修复: usage_data 为 None 时不添加 null 字段，条件添加 usage
# 2026-07-26 小欧 L2重试加指数退避: 原 flat 0.5s → min(0.5 * 2^attempt, 30). 根因:429配额耗尽后快速原地重试只会反复失败, 指数退避给配额恢复机会.
# 2026-07-28 - 小欧 - 欧阳BUG-10修复: call_llm_with_fallback fallback前agent.llm_client._cancelled=False改agent.llm_client.reset_cancel(), 确保_current_response一并重置
# 2026-08-14 - 小欧 - llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档[1]11.8.2.1 D0b/11.9 P3): _build_tool_calls_response 的
#   result 与 _pending_calls 两处透传 params_raw_str(源=D0 base_service)——补 #3 链路缺口,
#   缺此跳 D3 落盘闭包永远 fallback 到已解析 tool_params, 违背 11.7.9-2③「LLM 原始参数」
"""
llm_stream — LLM流式调用+响应构建

从llm_caller更名 — 小欧 2026-06-25 名实相符

—— type 分类链（知识备忘 — 小欧 2026-07-15） ——
此模块是 type 产生的源头。call_llm_stream() 在流结束后根据 LLM 输出做"事后分类"：

  LLM 产 tool_calls → _build_tool_calls_response() → {"type": "action"}
  LLM 仅文本        → _build_answer_response()     → {"type": "answer"}
  流异常/出错       → _yield_error_response()      → {"type": "error"}

关键认知：LLM 原生输出（OpenAI SSE）不含 type 字段，type 是 agent 推理加上的。
详见 llm/core.py 头部的完整分类说明。
"""

import asyncio
import json
import time
from typing import Any, Optional

from app.services.agent.steps import ChunkStep
from app.constants import LLM_RESPONSE_FALLBACK, LLM_RESPONSE_RETRIES, LLM_TOOL_CHOICE
from app.llm.core import LLMResponseError
from app.utils.text_utils import extract_tool_call_xml
from app.logger import logger
from app.logger.prompt_logger import get_prompt_logger



def _build_tool_calls_response(full_content, tool_calls_result, usage_data, agent, full_reasoning=""):
    """构建action类型响应 — 小欧 2026-06-25 抽取_log_llm_response"""
    for tc in tool_calls_result:
        if "tool_params" in tc and tc["tool_params"] is None:
            logger.warning(f"[LLM] 生成残缺tool_call: {tc.get('tool_name', '?')} tool_params为None, 由工具层降级校验")
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
            "_repair_warning": tc.get("_repair_warning", ""),
            "params_raw_str": tc.get("params_raw_str", ""),   # #3 并行调用各自原始串透传(11.7.9-2③) — 小欧 2026-08-23
        })

    logger.info(f"[LLM] 原始响应(action): tool={first.get('tool_name','?')}, parallel={len(_pending_calls)}")
    full_content = full_content.strip()
    full_reasoning = full_reasoning.strip()
    assembled = {"content": full_content, "reasoning": full_reasoning, "tool_calls": built_tool_calls}
    _log_llm_response(agent, json.dumps(assembled, ensure_ascii=False), "action", usage_data,
                      tool_name=first.get("tool_name", "?"), parallel_calls=len(_pending_calls))
    result = {
        "type": "action", "thought": full_content, "reasoning": full_reasoning,
        "fc_context": {"tool_call_id": first.get("tool_call_id") or "", "tool_calls": built_tool_calls, "llm_content": full_content, "llm_reasoning": full_reasoning},  # 2026-07-19 小欧 新增/传递 llm_reasoning
        "_pending_calls": _pending_calls, "tool_name": first.get("tool_name", ""),
        "tool_params": first.get("tool_params") or {}, "tool_call_id": first.get("tool_call_id") or "",
        "params_raw_str": first.get("params_raw_str", ""),   # #3 主调用原始 arguments 串透传(11.7.9-2③); 源=D0 base_service — 小欧 2026-08-23
        "_repair_warning": first.get("_repair_warning", ""),
    }
    if usage_data is not None:  # 2026-07-22 - 小欧 - 修复: usage 为 None 时不添加 null 字段
        result["usage"] = usage_data
    return ("response", result)


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


def _format_response_error(e: "LLMResponseError") -> str:
    """格式化LLM响应错误为前端友好信息 — 小沈 2026-07-17"""
    return f"LLM响应解析失败: {e.message}"  # task007: 加LLM前缀明确来源 — 小欧 2026-07-23


def _yield_error_response(error_msg: str, agent, exc: Optional[BaseException] = None, exc_type: str = ""):
    """统一错误响应构建 — 小健 2026-06-18 DRY提取

    type="error" 的含义: LLM 流式调用出现异常/出错,agent 以此终止任务并设 FAILED。
    由 _dispatch_handler(react_cycle.py) 分派到 handle_answer() 的 error 分支。"""
    # 【E-4修复】返回type:error,DispatchHandler的error分支处理 — 小欧 2026-06-28
    # M5: 空消息场景补强诊断上下文(exc类型/分类), 防根因丢失 — 小欧 2026-07-16
    diag = f" | exc={type(exc).__name__}" if exc else (f" | type={exc_type}" if exc_type else "")
    logger.error(f"[LLM] {error_msg}{diag}")
    _log_llm_response(agent, error_msg, "error", None, finish_reason="error")
    return ("response", {"type": "error", "content": error_msg})


def _build_answer_response(full_content, full_reasoning, usage_data, agent, finish_reason=None):
    """构建answer类型响应 — 小欧 2026-06-25 抽取_log_llm_response
    
    type="answer" 的含义: agent 推断 LLM 已完成任务(无 tool_calls,仅文本输出),
    将此文本作为任务最终答复,后续由 handle_answer() → FinalStep 结束循环。
    — 小欧 2026-07-19 新增 finish_reason 参数(API最后chunk回传:stop/length/content_filter)"""
    logger.info(f"[LLM] 原始响应(answer):\n")
    full_content = full_content.strip()
    full_reasoning = full_reasoning.strip()
    assembled = {"content": full_content, "reasoning": full_reasoning}
    _log_llm_response(agent, json.dumps(assembled, ensure_ascii=False), "answer", usage_data, finish_reason=finish_reason)
    result = {"type": "answer", "content": full_content, "reasoning": full_reasoning, "finish_reason": finish_reason}
    if usage_data is not None:  # 2026-07-22 - 小欧 - 修复: usage 为 None 时不添加 null 字段
        result["usage"] = usage_data
    return ("response", result)



async def call_llm_stream(agent, messages: list, openai_tools: list = None):
    """FC/Text双模式流式调用 — tools=None时走Text模式(降级后备) — 小沈 2026-06-12; 小欧 2026-06-25 tools=None支持"""
    full_content = ""
    full_reasoning = ""
    tool_calls_result = None
    stream_error = None
    usage_data = None
    tool_choice = LLM_TOOL_CHOICE if openai_tools else None
    _finish_reason = None  # 2026-07-19 小欧 新增: SSE最后chunk的finish_reason(None→_log_llm_response回退stop)

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
                # is_reasoning 标记由 base_service.py 解析时打上（判定规则见 reasoning.py 模块注释）
                # 此处只消费该标记：True → 思考区，False → 答案区 — 小欧 2026-07-12
                is_reasoning = getattr(chunk, "is_reasoning", False)
                if is_reasoning:
                    full_reasoning += chunk.content
                else:
                    full_content += chunk.content
                yield ("chunk", ChunkStep(step=agent.llm_call_count, content=chunk.content, is_reasoning=is_reasoning))

            if chunk.is_done:
                if chunk.usage:
                    usage_data = chunk.usage
                _finish_reason = getattr(chunk, "finish_reason", None) or None  # 2026-07-19 小欧
                break
        llm_elapsed = time.time() - llm_start
    except LLMResponseError:
        raise
    except Exception as e:
        if getattr(agent.llm_client, '_cancelled', False):
            logger.info(f"[LLM] 调用因取消而中断, 跳过异常响应")
            return
        yield _yield_error_response(f"LLM调用异常: {e}", agent, exc=e)
        return
    except asyncio.CancelledError:
        content = full_content or full_reasoning or ""
        logger.warning(f"[LLM] 流式调用被取消, 已累积内容({len(content)}字符)")
        get_prompt_logger().log_llm_response(
            round_number=agent.llm_call_count, response_content=content,
            raw_response="", response_type="answer", finish_reason="cancelled",
        )
        raise

    if stream_error:
        if tool_calls_result:
            logger.warning(f"[LLM] 流式错误, 丢弃{len(tool_calls_result)}个未完成的tool_calls")
            tool_calls_result = None
        yield _yield_error_response(f"LLM流式错误: {stream_error}", agent, exc_type=chunk.stream_error_type or "")
        return

    # ════════════════════════════════════════════════════
    # type 推断：LLM 产了 tool_calls → action
    # ════════════════════════════════════════════════════
    if tool_calls_result:
        _fc_names = [tc.get("tool_name","?") if isinstance(tc,dict) else "?" for tc in tool_calls_result]
        _p = usage_data.get('prompt_tokens', '?') if usage_data else '?'
        _c = usage_data.get('completion_tokens', '?') if usage_data else '?'
        _t = usage_data.get('total_tokens', '?') if usage_data else '?'
        logger.info(f"[LLM] 解析结果: tool_calls({len(tool_calls_result)})={_fc_names}, tokens={_t}(prompt={_p}+completion={_c}), llm_dur={llm_elapsed:.2f}s")
        yield _build_tool_calls_response(full_content, tool_calls_result, usage_data, agent, full_reasoning)
        return

    # ════════════════════════════════════════════════════
    # XML tool_call 提取：LLM 降级使用旧 <tool_call> 格式时,
    # 从 reasoning（FC退化）或 content（Text fallback）中提取并执行 — 小欧 2026-07-16
    # ════════════════════════════════════════════════════
    if not tool_calls_result:
        search_text = full_reasoning or full_content
        if search_text:
            extracted = extract_tool_call_xml(search_text)
            if extracted:
                # #39 fix: XML兜底路径明确提示 — 小欧 2026-07-18
                #   原生FC为空才走此分支, 说明LLM未用标准tool_calls, 降级用旧<tool_call>格式
                #   打WARNING提升可观测性, 避免"既Thought又Action"看似bug实为容错
                logger.warning(
                    f"[LLM] 走XML <tool_call> 容错提取(非原生FC): "
                    f"tool_name={extracted['tool_name']}, "
                    f"来源={'reasoning' if full_reasoning else 'content'}"
                )
                # 防误提取（禁止退化）：FC 模式校验工具名在可用清单内，
                # 避免推理中讨论 XML 语法被误当作工具执行；不在清单则回落 answer
                # 容错：工具列表可能含异常条目（None/非dict），逐项防护，避免守卫自身崩溃
                if openai_tools is not None:
                    _available = {t.get("function", {}).get("name")
                                  for t in openai_tools
                                  if isinstance(t, dict) and isinstance(t.get("function"), dict)}
                    _valid = extracted["tool_name"] in _available
                else:
                    _valid = True   # Text fallback：无清单，由 action_handler 注册表校验
                if _valid:
                    synthetic_id = f"call_extracted_{agent.llm_call_count}"
                    extracted["tool_call_id"] = synthetic_id
                    extracted["tool_calls"] = [{
                        "id": synthetic_id, "type": "function",
                        "function": {
                            "name": extracted["tool_name"],
                            "arguments": json.dumps(extracted["tool_params"], ensure_ascii=False)
                        }
                    }]
                    tool_calls_result = [extracted]
                    yield _build_tool_calls_response(
                        full_content, tool_calls_result, usage_data, agent, full_reasoning or "")
                    return
                logger.info(f"[LLM] 提取 tool_name={extracted['tool_name']} 不在可用清单, 跳过XML执行, 回落answer")

    # ════════════════════════════════════════════════════
    # type 推断：LLM 无 tool_calls、仅文本 → answer
    # ════════════════════════════════════════════════════
    content = full_content or full_reasoning or ""
    _p = usage_data.get('prompt_tokens', '?') if usage_data else '?'
    _c = usage_data.get('completion_tokens', '?') if usage_data else '?'
    _t = usage_data.get('total_tokens', '?') if usage_data else '?'
    logger.info(f"[LLM] 解析结果: answer, len={len(content)}, tokens={_t}(prompt={_p}+completion={_c}), llm_dur={llm_elapsed:.2f}s")
    yield _build_answer_response(full_content, full_reasoning, usage_data, agent, _finish_reason)


async def call_llm_with_fallback(agent, messages, openai_tools):
    """FC模式失败时条件降级到Text模式 — 小欧 2026-06-25"""
    last_error = None

    for attempt in range(LLM_RESPONSE_RETRIES):
        try:
            async for item in call_llm_stream(agent, messages, openai_tools):
                # 流式error响应(type:"error")会绕过L2重试直抵set_failed使agent失败;此处转LLMResponseError交给上层重试 — 小欧 2026-07-15
                if isinstance(item, tuple) and item[0] == "response":
                    resp = item[1]
                    if isinstance(resp, dict) and resp.get("type") == "error":
                        raise LLMResponseError(message=resp.get("content", "LLM流式错误"))
                yield item
            return
        except LLMResponseError as e:
            last_error = e
            logger.warning(f"[Retry][L2] LLM响应错误 第{attempt+1}/{LLM_RESPONSE_RETRIES}次: {e}")
            wait_time = min(0.5 * (2 ** attempt), 30)
            await asyncio.sleep(wait_time)
            continue

    if LLM_RESPONSE_FALLBACK:
        logger.warning(f"[FC降级] FC模式{LLM_RESPONSE_RETRIES}次重试均失败，降级到Text模式")
        # #31 fix: fallback前reset事件，消cancel状态残留 — 小欧 2026-07-18
        agent.llm_client.reset_cancel()
        try:
            async for item in call_llm_stream(agent, messages, openai_tools=None):
                yield item
        except LLMResponseError as e:
            error_msg = _format_response_error(e)
            logger.error(f"[FC降级] {error_msg}", exc_info=True)
            yield _yield_error_response(error_msg, agent)
    else:
        # LLM_RESPONSE_RETRIES=0时for循环不执行,last_error恒为None,直接_format_response_error(None)会AttributeError崩溃,故兜底 — 小欧 2026-07-15
        if last_error is None:
            error_msg = f"功能调用模式不可用(重试次数={LLM_RESPONSE_RETRIES})，降级通道已关闭，无法继续执行任务"  # Bug4: 保留重试次数诊断信息 — 小欧 2026-07-23
        else:
            error_msg = _format_response_error(last_error)
        yield _yield_error_response(error_msg, agent)

