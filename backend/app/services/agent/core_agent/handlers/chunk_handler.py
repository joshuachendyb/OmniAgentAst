# -*- coding: utf-8 -*-
"""
chunk_handler — chunk类型处理

从react_cycle.py拷出_handle_chunk函数，保持业务逻辑不变

Author: 小沈 - 2026-06-09
"""
from typing import Dict

from app.services.agent.steps import ChunkStep, ThoughtStep


async def handle_chunk(agent, parsed: Dict, llm_response: str, step_counter: list, chunk_buffer):
    """处理chunk类型
    
    从react_cycle.py第229-237行拷出，保持业务逻辑不变
    """
    step = step_counter[0]
    content = parsed.get("content", llm_response.strip())

    yield agent._step_emitter.emit(ChunkStep(step=step, content=content, is_reasoning=False))

    async for event in handle_chunk_buffer_promotion(agent, step, content, chunk_buffer, step_counter):
        yield event


async def handle_chunk_buffer_promotion(agent, step: int, content: str, chunk_buffer, step_counter: list):
    """处理chunk buffer提升
    
    从react_cycle.py第208-226行拷出，保持业务逻辑不变
    """
    if not chunk_buffer:
        return

    chunk_buffer.append(content)
    if not chunk_buffer.should_promote():
        return

    accumulated = chunk_buffer.flush()
    if not accumulated:
        return

    yield agent._step_emitter.emit(ThoughtStep(
        step=step, content=f"Accumulated {len(accumulated)} chunks",
    ))
    yield agent._step_emitter.emit(ChunkStep(
        step=step, content=accumulated,
    ))