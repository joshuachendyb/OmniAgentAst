# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 修复#5 删除 threading.RLock()+@_synchronized(asyncio单线程下是死重, KISS/YAGNI); 修复#2+#8 终态不可变(首终态为准, terminal→terminal 忽略不翻转, 杜绝ValueError崩溃与终态误标)
# 2026-11-03 - 小欧 - 忽略终态翻转日志 WARNING→INFO(竞态守卫已安全忽略, 非故障) — 小欧-2026-11-03
# 2026-11-04 - 小欧 - 删未使用的 typing.Optional(死导入) — 小欧-2026-11-04
# 2026-11-24 - 商量 - 新增 tracker_terminal_status: AgentStatus→task_tracker 终态值唯一映射源(COMPLETED→success/FAILED→failed/CANCELLED→cancelled, 其余按failed);
#   病根: 任务收尾曾用 complete_task(success=(status==COMPLETED)) 二值化, 取消被写成 failed, 与 SSE/chat_tasks 分叉
"""
status_table — Agent状态集中管理

唯一能改得动 agent.status 的地方。纯函数 + 数据表，不用类。
handler 不设状态，只 yield Step → 编排层从 event type 推断状态 → 调 status_table 函数。

chendyg 2026-07-01
"""

from enum import Enum

from app.logger import (
    logger,  # 2026-11-04 小欧: 删未使用的 typing.Optional(死导入) — 小欧-2026-11-04
)
from app.logger.prompt_logger import get_prompt_logger


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SUSPENDED = "suspended"   # 真挂起：用户暂停任务 / HITL 等用户确认（区别于 RETRYING 错误重试）— 小欧 2026-07-12


# 合法状态转换表 — 只保留代码中实际存在的转换路径（KISS-DIRECT：无死代码）
# 实际状态机流程：
# 1. 正常流程：IDLE → THINKING → (EXECUTING → THINKING)* → COMPLETED
# 2. 错误恢复：THINKING/EXECUTING → RETRYING → THINKING（重试）或 FAILED（重试超限）
# 2b. 真挂起：THINKING/EXECUTING → SUSPENDED（用户暂停 / HITL等确认）→ THINKING/EXECUTING（恢复）或 CANCELLED/FAILED
# 3. 终止状态：CANCELLED（用户取消）、FAILED（不可恢复错误）、COMPLETED（成功完成）
# 4. 取消可在任何活跃状态触发：THINKING/EXECUTING/RETRYING/SUSPENDED → CANCELLED
# 5. 失败可在任何活跃状态触发：THINKING/EXECUTING/RETRYING/SUSPENDED → FAILED

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
        AgentStatus.RETRYING,     # 异常：系统重试（_dispatch_handler 检测 seen_types 含 'retrying'）
        AgentStatus.SUSPENDED,    # 异常：真挂起（用户暂停 / HITL等确认）— 小欧 2026-07-12
    },

    # 执行中
    AgentStatus.EXECUTING: {
        AgentStatus.THINKING,      # 正常：执行完成，继续思考
        AgentStatus.COMPLETED,     # 正常：执行完成，任务结束
        AgentStatus.FAILED,        # 异常：不可恢复错误
        AgentStatus.CANCELLED,     # 异常：用户取消
        AgentStatus.RETRYING,     # 异常：系统重试（_dispatch_handler 检测 seen_types 含 'retrying'）
        AgentStatus.SUSPENDED,    # 异常：真挂起（用户暂停 / HITL等确认）— 小欧 2026-07-12
    },

    # 重试（可恢复错误，react循环回THINKING重试）
    AgentStatus.RETRYING: {
        AgentStatus.THINKING,      # 恢复：重试思考（react_cycle重试机制）
        AgentStatus.FAILED,        # 终止：重试超限
        AgentStatus.CANCELLED,     # 终止：用户取消
    },

    # 真挂起（用户暂停任务 / HITL 等用户确认）
    AgentStatus.SUSPENDED: {
        AgentStatus.THINKING,      # 恢复：回到思考
        AgentStatus.EXECUTING,     # 恢复：继续执行（HITL确认后）
        AgentStatus.RETRYING,     # 挂起期间异常→转重试（HITL等待抛错时react_cycle except块置RETRYING）— 小欧 2026-07-12
        AgentStatus.FAILED,        # 终止：挂起期间出错
        AgentStatus.CANCELLED,     # 终止：用户取消
    },

    # 终止状态：不可转换
    AgentStatus.CANCELLED: set(),
    AgentStatus.COMPLETED: set(),
    AgentStatus.FAILED:    set(),
}

# 终态集合: 一旦进入即不可逆(首终态为准)。— 北京老陈 2026-07-18
_TERMINAL_STATUSES = {AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED}


def _validate_transition(old_status: AgentStatus, new_status: AgentStatus) -> bool:
    """验证状态转换是否合法 — chendyg 2026-07-01"""
    if old_status == new_status:
        return True
    return new_status in _TRANSITIONS.get(old_status, set())


def set_status(agent, new_status: AgentStatus, reason: str = ""):
    old_status = agent.status
    if old_status == new_status:
        return
    # 【终态不可变】旧态已是终态且新态也是终态 → 忽略(首终态为准)。
    # ① 杜绝"已完成/失败任务被取消→误标cancelled"等终态翻转(#2);
    # ② 避免非法转换 ValueError 在主路径崩溃(#8), 改为安全忽略。— 北京老陈 2026-07-18
    if old_status in _TERMINAL_STATUSES and new_status in _TERMINAL_STATUSES:
        logger.info(f"[Agent] 忽略终态翻转: {old_status} → {new_status} (终态不可变, 保持 {old_status})")  # 2026-11-03 小欧: 竞态守卫已安全忽略, 降 INFO
        return
    if not _validate_transition(old_status, new_status):
        raise ValueError(f"非法转换: {old_status} → {new_status}")
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
        get_prompt_logger().log_status(str(old_status), str(new_status), reason)
    except Exception:
        pass


def set_failed(agent, reason: str = ""):
    set_status(agent, AgentStatus.FAILED, reason)


def set_completed(agent):
    set_status(agent, AgentStatus.COMPLETED)


def set_cancelled(agent):
    set_status(agent, AgentStatus.CANCELLED)


# AgentStatus → task_tracker(tasks.status) 终态值映射, 唯一源 — 商量 2026-11-24
# 取消是独立终态, 不得并入 failed: 原收尾用 complete_task(success=(status==COMPLETED)) 把五态压成二值,
# CANCELLED 被写成 failed, 与 SSE final.outcome / chat_tasks.status 的 cancelled 分叉
# (任务列表与历史把"已取消"显示成"失败")。五态→三态的翻译只此一处, 消费方不得各自再压二值。
_TRACKER_TERMINAL_STATUS = {
    AgentStatus.COMPLETED: "success",
    AgentStatus.FAILED: "failed",
    AgentStatus.CANCELLED: "cancelled",
}


def tracker_terminal_status(status: AgentStatus) -> str:
    """AgentStatus → task_tracker 任务终态值(success/failed/cancelled) — 商量 2026-11-24
    收尾时仍非终态(RETRYING/SUSPENDED/None)按失败落库: 任务未正常完成, 不得误标成功。"""
    return _TRACKER_TERMINAL_STATUS.get(status, "failed")


# AgentStatus → 前端 UI / chat_tasks / SSE final.outcome 口径终态(completed/failed/cancelled)
# 与 _TRACKER_TERMINAL_STATUS 并列, 因为两套词表客观不同(task_tracker 用 success, 其余用 completed);
# 不得合并成一张表再在消费方转换 —— 那正是上一轮"布尔二值化把 cancelled 压成 failed"的同型错误。
_UI_TERMINAL_STATUS = {
    AgentStatus.COMPLETED: "completed",
    AgentStatus.FAILED: "failed",
    AgentStatus.CANCELLED: "cancelled",
}


def ui_terminal_status(status: AgentStatus) -> str:
    """AgentStatus → 前端/chat_tasks 口径终态值(completed/failed/cancelled) — 商量 2026-11-24
    用途: 生命周期广播 task_ended 的 status 字段(前端 isTerminalStatus 只认这三个值)。"""
    return _UI_TERMINAL_STATUS.get(status, "failed")
