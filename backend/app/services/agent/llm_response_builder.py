# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 8.5拆分(llm_stream.py提取builder成员): 5个纯函数逐字移入本文件(仅改import路径, 业务零改动)
#   _build_tool_calls_response/_log_llm_response/_format_response_error/_yield_error_response/_build_answer_response
#   原llm_stream.py余部只剩call_llm_stream+call_llm_with_fallback, git mv改名llm_call.py
"""
llm_response_builder — LLM响应组装纯函数

type 分类链的主体：LLM 原生输出（OpenAI SSE）不含 type 字段，type 是 agent 推理加上的。
call_llm_stream() 在流结束后根据 LLM 输出做"事后分类"：

  LLM 产 tool_calls → _build_tool_calls_response() → {"type": "action"}
  LLM 仅文本        → _build_answer_response()     → {"type": "answer"}
  流异常/出错       → _yield_error_response()      → {"type": "error"}
"""

import json
from typing import Optional

from app.llm.core import LLMResponseError
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
    return ("response", {"type": "error", "content": error_msg, "error_type": exc_type})


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