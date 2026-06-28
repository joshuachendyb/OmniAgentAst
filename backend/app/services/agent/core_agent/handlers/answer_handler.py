# -*- coding: utf-8 -*-
"""
answer_handler — answer/implicit类型处理

从react_cycle.py拷出_handle_answer函数，保持业务逻辑不变

Author: 小沈 - 2026-06-09
v2.0: 新增错误消息检测，LLM返回错误时设FAILED而非COMPLETED — 小欧 2026-06-28
"""
from typing import Dict

from app.services.agent.steps import ThoughtStep, FinalStep


async def handle_answer(agent, parsed: Dict, chunk_buffer):
    """处理answer类型 — FC-only: 空内容/错误内容均视为失败"""
    step = agent.llm_call_count
    content = parsed.get("content", "")

    if not content:
        from app.utils.logger import logger
        logger.warning(f"[handle_answer] LLM返回空内容(step={step})")
        # 【P1-17修复】空内容应设FAILED而非COMPLETED — chendyg 2026-06-26
        agent.set_failed("LLM返回空内容")
        # 【Bug3修复】空内容也需保存assistant消息到对话历史，保持FC协议完整性 — chendyg 2026-06-26
        agent.message_builder.add_assistant_message("")
        yield agent._step_emitter.emit(FinalStep(
            step=step, response="", thought="",
        ))
        return

    thought = parsed.get("thought", content)
    reasoning = parsed.get("reasoning", "")

    if thought:
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=thought, thought=thought, reasoning=reasoning,
        ))

    yield agent._step_emitter.emit(FinalStep(
        step=step, response=content, thought=thought,
    ))
    # 【修复P0-2】保存assistant回复到对话历史 — 北京老陈 2026-06-13
    # 【J-1修复】走MessageBuilder封装入口 — 小欧 2026-06-25
    agent.message_builder.add_assistant_message(content)
    agent.set_completed()