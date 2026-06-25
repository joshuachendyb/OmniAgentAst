# -*- coding: utf-8 -*-
"""
_initialize_run_state — 每次运行前初始化Agent状态

职责: 重置steps/message_builder/status/llm_call_count,注入system prompt和task
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, Optional

from app.constants import MAX_CONSECUTIVE_CHUNKS
from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer
from app.utils.prompt_logger import get_prompt_logger


def _inject_conversation_history(agent, context: Optional[Dict[str, Any]]) -> None:
    """注入会话历史(多轮对话支持) — 北京老陈 2026-06-13; 小沈 2026-06-17 参数名self→agent
    小健 2026-06-26: 修复丢失tool消息和带tool_calls的assistant消息的bug(P0-1)，保留FC协议完整性"""
    if not context or not isinstance(context, dict):
        return
    prev = context.get("previous_messages")
    if not prev or not isinstance(prev, list):
        return
    history = agent.message_builder.conversation_history
    for msg in prev:
        role = msg.get("role")
        # 小健 2026-06-26: 保留tool消息，原代码只保留user/assistant导致FC协议对话不一致
        if role == "tool":
            history.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": msg.get("content", ""),
            })
        elif role == "assistant":
            # 小健 2026-06-26: 保留tool_calls字段，原代码只复制content导致带tool_calls的assistant消息丢失
            tc = msg.get("tool_calls")
            if tc:
                history.append({
                    "role": "assistant",
                    "tool_calls": tc,
                    "content": msg.get("content"),
                })
            elif msg.get("content"):
                history.append({"role": "assistant", "content": msg["content"]})
        elif role == "user" and msg.get("content"):
            history.append({"role": "user", "content": msg["content"]})
        elif role == "system" and msg.get("content"):
            history.append({"role": "system", "content": msg["content"]})
    agent.message_builder.conversation_history = history
    agent.message_builder.trim_history()


def initialize_run_state(
    agent, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
) -> ChunkBuffer:
    """初始化每轮运行状态:重置steps/注入system prompt和task — 小沈 2026-06-17 参数名self→agent"""
    agent.steps = []
    agent.message_builder.reset_per_run()
    agent.status = AgentStatus.THINKING
    agent.llm_call_count = 0
    agent._consecutive_truncations = 0
    if task_id:
        agent.task_id = task_id

    agent._on_session_init(task, context)
    sys_prompt = agent._get_system_prompt()

    prompt_logger = get_prompt_logger()
    prompt_logger.log_system_prompt(
        step_name="运行时系统Prompt注入",
        prompt_content=sys_prompt,
        source=f"{agent.__class__.__name__}._get_system_prompt()",
    )
    prompt_logger.log_task_prompt(
        task_content=task,
        context=context if context else None,
        source=f"{agent.__class__.__name__}.initialize_run_state",
    )

    agent._on_before_loop(sys_prompt, task, context)
    agent.message_builder.init_history(sys_prompt, task)
    _inject_conversation_history(agent, context)

    return ChunkBuffer(MAX_CONSECUTIVE_CHUNKS)
