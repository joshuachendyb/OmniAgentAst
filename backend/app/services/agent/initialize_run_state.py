# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 【病根】历史重载边界(_inject_conversation_history)把 DB(execution_steps)持久化的 assistant.tool_calls 原样注入 message_builder, 零校验; 若某条 tool_calls 含非dict元素(截断/畸形LLM响应落库), 下轮回传即触发 provider 400("Can only get item pairs from a mapping")并 FC 降级→AgentStatus.FAILED。
#            【解决思路】注入边界对 tool_calls 逐元素 isinstance(t, dict) 校验: list仅留dict元素 / 单dict归一为[dict] / 其余置空回退content分支; 合法 list-of-dict 输入输出100%不变(增强不退化), 调用方零改动。
"""
_initialize_run_state — 每次运行前初始化Agent状态

职责: 重置steps/message_builder/status/llm_call_count,注入system prompt和task
Author: 小沈 - 2026-05-31
更新: 小欧 - 2026-07-16 统一TaskID: _tracked_task_id → agent.task_id
更新: 小欧 - 2026-08-08 新增相同工具死循环检测状态初始化(_consecutive_same_tool_calls/_last_tool_call_sig)
更新: 小欧 - 2026-08-08 v1.6 双阈值升级: 新增纠偏幂等标记初始化(_warned_same_tool_loop=False)
"""

from typing import Any, Dict, Optional

from app.constants import MAX_CONSECUTIVE_CHUNKS
from app.services.agent.status_table import AgentStatus, set_status
from app.services.agent.chunk_buffer import ChunkBuffer
from app.logger import logger
from app.logger.prompt_logger import get_prompt_logger
from app.db import db


def _inject_conversation_history(agent, context: Optional[Dict[str, Any]]) -> None:
    """注入会话历史(多轮对话支持) — 北京老陈 2026-06-13; 小沈 2026-06-17 参数名self→agent
    小健 2026-06-26: 修复丢失tool消息和带tool_calls的assistant消息的bug(P0-1)，保留FC协议完整性
    chendyg 2026-06-30: 修复重复user消息bug——previous_messages中最后一条user与init_history注入的task重复"""
    if not context or not isinstance(context, dict):
        return
    prev = context.get("previous_messages")
    if not prev or not isinstance(prev, list):
        return
    last_user_idx = -1
    for i in range(len(prev) - 1, -1, -1):
        if prev[i].get("role") == "user":
            last_user_idx = i
            break
    history_msgs = []
    for i, msg in enumerate(prev):
        if i == last_user_idx:
            continue
        role = msg.get("role")
        if role == "tool":
            entry = {"role": "tool", "tool_call_id": msg.get("tool_call_id", ""), "content": msg.get("content", "")}
            # M-04: FC协议需要name字段 — 小欧 2026-07-10
            name = msg.get("name")
            if name:
                entry["name"] = name
            history_msgs.append(entry)
        elif role == "assistant":
            tc_raw = msg.get("tool_calls")
            # 历史重载边界校验 — 小欧 2026-07-18
            # 病根: 持久化 assistant.tool_calls 若含非dict元素(截断/畸形LLM响应落库),
            #       原样回传致 provider 400("Can only get item pairs from a mapping")并触发FC降级。
            # 修复: 仅保留dict元素, 非dict一律剥离; 剥离后为空则回退content分支(无退化)。
            if isinstance(tc_raw, list):
                tc = [t for t in tc_raw if isinstance(t, dict)]
            elif isinstance(tc_raw, dict):
                tc = [tc_raw]
            else:
                tc = []
            if tc:
                history_msgs.append({
                    "role": "assistant",
                    "tool_calls": tc,
                    "content": msg.get("content"),
                })
            elif msg.get("content"):
                history_msgs.append({"role": "assistant", "content": msg["content"]})
        elif role == "user" and msg.get("content"):
            history_msgs.append({"role": "user", "content": msg["content"]})
        elif role == "system" and msg.get("content"):
            history_msgs.append({"role": "system", "content": msg["content"]})
    agent.message_builder.inject_history(history_msgs)


def initialize_run_state(
    agent, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
) -> ChunkBuffer:
    """初始化每轮运行状态:重置steps/注入system prompt和task — 小沈 2026-06-17 参数名self→agent"""
    agent.steps = []
    agent.message_builder.reset_per_run()
    set_status(agent, AgentStatus.THINKING)
    agent.llm_call_count = 0
    agent._consecutive_truncations = 0
    agent._retry_count = 0
    # 2026-08-08 - 小欧 - 相同工具调用死循环检测状态初始化(防跨任务残留): 连续相同工具签名计数+上次签名+纠偏幂等标记
    agent._consecutive_same_tool_calls = 0
    agent._last_tool_call_sig = None
    agent._warned_same_tool_loop = False   # v1.6双阈值: 纠偏注入幂等标记, 落码新增字段 — 小欧 2026-08-08
    # 【#42修复】更新tracker任务描述为实际task内容 — chendyg 2026-06-26
    if task and agent._task_tracker and agent.task_id:
        try:
            with db.get_conn("task_tracker") as conn:
                conn.execute(
                    "UPDATE tasks SET task_description = ? WHERE task_id = ?",
                    (task[:200], agent.task_id),
                )
        except Exception:
            logger.error(f"[initialize_run_state] 更新任务描述失败: task_id={agent.task_id}")
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
