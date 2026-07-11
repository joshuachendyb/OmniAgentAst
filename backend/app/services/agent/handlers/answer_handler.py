# -*- coding: utf-8 -*-
"""
answer_handler — answer/implicit类型处理

从react_cycle.py拷出_handle_answer函数，保持业务逻辑不变

Author: 小沈 - 2026-06-09
v2.0: 新增错误消息检测，LLM返回错误时设FAILED而非COMPLETED — 小欧 2026-06-28
v3.0: reasoning-only分支+tool call文本格式化 — 小欧 2026-07-12
"""
from typing import Dict

from app.services.agent.steps import ThoughtStep, FinalStep, ErrorStep
from app.utils.text_utils import format_tool_call_markup
from app.logger import logger


async def handle_answer(agent, parsed: Dict, chunk_buffer):
    """处理answer类型 — FC-only: 空内容/错误内容均视为失败"""
    step = agent.llm_call_count
    content = format_tool_call_markup(parsed.get("content", ""))
    reasoning = format_tool_call_markup(parsed.get("reasoning", ""))

    # ── 真·空：content和reasoning都空 → ErrorStep SUSPENDED ──
    if not content and not reasoning:
        logger.warning(f"[handle_answer] LLM返回空内容(step={step})")
        # chendyg 2026-07-01: yield ErrorStep让_dispatch_handler推断FAILED
        # 保留add_assistant_message("")，FC协议要求空assistant消息也入历史
        agent.message_builder.add_assistant_message("")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="empty_response",
            error_message="LLM返回空内容",
            recoverable=True,
        ))
        return

    # ── reasoning-only：content空但reasoning有内容 → 注入observation继续循环 ──
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

    # thought 步骤 — content=LLM回答文本, reasoning=内部思维过程 — 小欧 2026-07-01
    if thought:
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=thought, reasoning=reasoning,
        ))

    yield agent._step_emitter.emit(FinalStep(
        step=step, response=content, thought=thought,
    ))
    # 保留add_assistant_message，数据就地 — chendyg 2026-07-01
    agent.message_builder.add_assistant_message(content)
