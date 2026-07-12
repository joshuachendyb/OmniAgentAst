# -*- coding: utf-8 -*-
"""
answer_handler — 统一处理所有"说"类型(action以外的答案/错误/未知)

从react_cycle.py拷出_handle_answer函数+_handle_llm_error+_handle_unknown
合并为统一handler，减少react_cycle分派分支

Author: 小沈 - 2026-06-09
v2.0: 新增错误消息检测，LLM返回错误时设FAILED而非COMPLETED — 小欧 2026-06-28
v3.0: reasoning-only分支+tool call文本格式化 — 小欧 2026-07-12
v4.0: 合并error/unknown处理，react_cycle只分两路 — 小欧 2026-07-12
"""
import time
from typing import Dict

from app.services.agent.steps import ThoughtStep, FinalStep, ErrorStep
from app.utils.text_utils import format_tool_call_markup
from app.logger import logger


async def handle_answer(agent, parsed: Dict, chunk_buffer):
    """统一处理所有非action的LLM返回类型（answer/error/unknown）"""
    step = agent.llm_call_count
    parsed_type = parsed.get("type", "answer")

    # ── type="error" │ yiled ErrorStep ──
    if parsed_type == "error":
        content = parsed.get("content", "") or "LLM流式错误"
        agent.message_builder.add_assistant_message(content)
        print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, error={content}")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="llm_error", error_message=content,
        ))
        return

    # ── 未知类型 │ yiled ErrorStep ──
    if parsed_type != "answer":
        logger.warning(f"[handle_answer] 未知返回类型: {parsed_type}, 设置为FAILED")
        content = parsed.get("content", "") or parsed.get("thought", "") or ""
        print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, type={parsed_type}, content={content}")
        if content:
            agent.message_builder.add_assistant_message(f"[无效响应:{parsed_type}] {content}")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="unknown_response",
            error_message=f"LLM返回未知响应类型: {parsed_type}",
        ))
        return

    # ── type="answer" ──
    content = format_tool_call_markup(parsed.get("content", ""))
    reasoning = format_tool_call_markup(parsed.get("reasoning", ""))

    # 真·空：content和reasoning都空 → ErrorStep SUSPENDED
    if not content and not reasoning:
        logger.warning(f"[handle_answer] LLM返回空内容(step={step})")
        agent.message_builder.add_assistant_message("")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="empty_response",
            error_message="LLM返回空内容",
            recoverable=True,
        ))
        return

    # reasoning-only：LLM只返回推理没给最终答案 → 注入observation继续循环
    # 本处分两条路径往conversation_history写3条消息，原因如下：
    #   ① add_assistant_message("") → role=assistant, content=""     真实记录：本轮LLM实际返回空
    #   ② add_observation(reasoning) → _append_observation拆成2条：
    #       ②-1 assistant(tool_calls=[], content=reasoning)           合成注入：模拟FC格式，把reasoning当assistant工具调用
    #       ②-2 tool(tool_call_id="", content=reasoning)             合成注入：模拟FC格式，把reasoning当工具结果
    #   ① 是"LLM说了什么"的日志记录，②是"喂给下一轮LLM的上文"。
    #   这样下一轮LLM收到历史时能看到"我上轮推理了这些内容+得到了observation"，从而继续执行。
    #   — 小欧 2026-07-12
    if not content and reasoning:
        logger.info(f"[handle_answer] LLM返回推理内容(step={step}), 注入observation继续循环")
        agent.message_builder.add_assistant_message("")
        agent.message_builder.add_observation(
            reasoning,
            {"tool_call_id": "", "tool_calls": [], "llm_content": reasoning},
        )
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=reasoning, reasoning="",
        ))
        return

    thought = parsed.get("thought", content)

    if thought:
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=thought, reasoning=reasoning,
        ))

    yield agent._step_emitter.emit(FinalStep(
        step=step, response=content, thought=thought,
    ))
    agent.message_builder.add_assistant_message(content)
