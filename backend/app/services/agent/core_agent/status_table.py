# -*- coding: utf-8 -*-
"""
status_table — Agent状态集中管理

唯一能改得动 agent.status 的地方。纯函数 + 数据表，不用类。
handler 不设状态，只 yield Step → 编排层从 event type 推断状态 → 调 status_table 函数。

chendyg 2026-07-01
"""

import threading
from typing import Optional

from app.services.agent.types import AgentStatus
from app.utils.logger import logger


# 合法状态转换表 — 只保留代码中实际存在的转换路径（KISS-DIRECT：无死代码）
# 实际状态机流程：
# 1. 正常流程：IDLE → THINKING → (EXECUTING → THINKING)* → COMPLETED
# 2. 错误恢复：THINKING/EXECUTING → SUSPENDED → THINKING（重试）或 FAILED（重试超限）
# 3. 终止状态：CANCELLED（用户取消）、FAILED（不可恢复错误）、COMPLETED（成功完成）
# 4. 取消可在任何活跃状态触发：THINKING/EXECUTING/SUSPENDED → CANCELLED
# 5. 失败可在任何活跃状态触发：THINKING/EXECUTING/SUSPENDED → FAILED

_TRANSITIONS = {
    # 初始状态
    AgentStatus.IDLE: {
        AgentStatus.THINKING,      # 正常：开始思考
        AgentStatus.CANCELLED,     # 异常：被取消（run_sse_stream中agent未开始时被取消）
        AgentStatus.FAILED,        # 异常：初始化失败（run_sse_stream中agent未开始时异常）
    },

    # 思考中
    AgentStatus.THINKING: {
        AgentStatus.EXECUTING,     # 正常：决定执行工具
        AgentStatus.COMPLETED,     # 正常：直接回答完成
        AgentStatus.FAILED,        # 异常：不可恢复错误
        AgentStatus.CANCELLED,     # 异常：用户取消
        AgentStatus.SUSPENDED,     # 异常：可恢复错误（_dispatch_handler中recoverable=True）
    },

    # 执行中
    AgentStatus.EXECUTING: {
        AgentStatus.THINKING,      # 正常：执行完成，继续思考
        AgentStatus.COMPLETED,     # 正常：执行完成，任务结束
        AgentStatus.FAILED,        # 异常：不可恢复错误
        AgentStatus.CANCELLED,     # 异常：用户取消
        AgentStatus.SUSPENDED,     # 异常：可恢复错误（_dispatch_handler中recoverable=True）
    },

    # 挂起（可恢复错误）
    AgentStatus.SUSPENDED: {
        AgentStatus.THINKING,      # 恢复：重试思考（react_cycle重试机制）
        AgentStatus.FAILED,        # 终止：重试超限
        AgentStatus.CANCELLED,     # 终止：用户取消
    },

    # 终止状态：不可转换
    AgentStatus.CANCELLED: set(),
    AgentStatus.COMPLETED: set(),
    AgentStatus.FAILED:    set(),
}

_status_lock = threading.RLock()


def _synchronized(func):
    def wrapper(agent, *args, **kwargs):
        with _status_lock:
            return func(agent, *args, **kwargs)
    return wrapper


def _validate_transition(old_status: AgentStatus, new_status: AgentStatus) -> bool:
    """验证状态转换是否合法 — chendyg 2026-07-01"""
    if old_status == new_status:
        return True
    return new_status in _TRANSITIONS.get(old_status, set())


@_synchronized
def set_status(agent, new_status: AgentStatus, reason: str = ""):
    if not _validate_transition(agent.status, new_status):
        raise ValueError(f"非法转换: {agent.status} → {new_status}")
    old_status = agent.status
    agent.status = new_status
    if reason:
        if new_status == AgentStatus.FAILED:
            logger.warning(f"[Agent] {old_status} → {new_status}: {reason}")
        else:
            logger.info(f"[Agent] {old_status} → {new_status}: {reason}")
    else:
        logger.info(f"[Agent] {old_status} → {new_status}")
    # 同时写入 prompt log — 小欧 2026-07-01
    try:
        from app.utils.prompt_logger import get_prompt_logger
        get_prompt_logger().log_status(str(old_status), str(new_status), reason)
    except Exception:
        pass


@_synchronized
def set_failed(agent, reason: str = ""):
    set_status(agent, AgentStatus.FAILED, reason)


@_synchronized
def set_completed(agent):
    set_status(agent, AgentStatus.COMPLETED)


@_synchronized
def set_cancelled(agent):
    set_status(agent, AgentStatus.CANCELLED)