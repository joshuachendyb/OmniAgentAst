# -*- coding: utf-8 -*-
"""
chunk_handler — streaming chunk处理

Author: 小沈 - 2026-06-13
"""
from app.services.agent.steps import ChunkStep


async def handle_chunk(agent, parsed, chunk_buffer):
    """处理streaming chunk — FC-only: 直接emit ChunkStep"""
    step = agent.llm_call_count
    yield agent._step_emitter.emit(ChunkStep(
        step=step,
        content=parsed.get("content", ""),
        thought=parsed.get("thought", ""),
        reasoning=parsed.get("reasoning", ""),
    ))
