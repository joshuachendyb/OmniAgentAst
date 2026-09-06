# 编辑历史:
# 2026-09-06 - 小欧 - 步骤1落盘(文档[6]5.2): StreamBuffer 新增 publish 生产者直写——dict()拷贝防调用方副作用
#   + seq=len单调递增 + 持锁cond.notify_all原子唤醒(与agent_runner._append行199-210同模式), 为事件总线
#   paused/resumed 唯一写入入口, 供 C5A真HITL / C1B bypass / C1C沙盘网关 三网关链调用, 支撑文档[6]路径1
# 2026-09-06 - 小欧 - VULN-006加固(task006漏洞分析报告, 北京老陈同意): publish 的 seq=len+event_log.append 移入
#   async with cond 锁内, 与 agent_runner._append 同步收紧, "seq分配+append+notify 持锁原子"注释声明名副其实;
#   防 4C 阶段多生产者直写事件总线时 seq 分配被插入 await 导致重复序号(当前 asyncio 单线程单生产者无实际竞态,
#   seq=len与append间无await点不会协程插队, 属防御性加固零行为变化)
"""
task_state — 运行态任务数据存储 + 只读查询

合并自: task_state_queries
无外部依赖(不导入 task_registry)，专为消除循环导入设计。
小欧 2026-07-10

北京老陈 2026-07-12: 新增 agent_streams/StreamBuffer，将"流态"(事件回放缓冲)
与"控制态"(running_tasks) 分离，支撑前端 SSE 断线重连 — 小欧 2026-07-12
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}


# ============================================================
# 流态缓冲(与控制态 running_tasks 分离) — 北京老陈 2026-07-12 断线重连
# ============================================================

@dataclass
class StreamBuffer:
    """单个任务的事件回放缓冲 — 小欧 2026-07-12

    event_log: append-only 事件列表，每条含 seq(单调递增序号)
    cond: 生产者追加新事件时唤醒消费者
    done: 生产者结束信号
    """
    event_log: List[Dict] = field(default_factory=list)
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)
    done: asyncio.Event = field(default_factory=asyncio.Event)

    async def publish(self, step_dict: dict) -> int:
        """生产者直写：append + seq + 唤醒消费者。返回seq。
        与 agent_runner._append(行199-210) 同模式：先dict()拷贝防调用方副作用，
        seq分配+append+notify 均须持锁原子完成；cond.notify_all 未持锁调用抛 RuntimeError。
        — 小健-2026-09-05；2026-09-06 小欧 步骤1落盘(文档[6]5.2)；2026-09-06 小欧 VULN-006加固(seq+append入锁)"""
        step_dict = dict(step_dict)
        async with self.cond:
            step_dict["seq"] = len(self.event_log)
            self.event_log.append(step_dict)
            self.cond.notify_all()
        return step_dict["seq"]


# 流态缓冲表: task_id -> StreamBuffer(独立于 running_tasks 的生命周期)
agent_streams: dict[str, "StreamBuffer"] = {}


def create_stream_buffer(task_id: str) -> "StreamBuffer":
    """创建并注册任务的流态缓冲 — 小欧 2026-07-12"""
    buf = StreamBuffer()
    agent_streams[task_id] = buf
    return buf


def get_stream_buffer(task_id: str) -> Optional["StreamBuffer"]:
    """获取任务的流态缓冲,不存在返回 None — 小欧 2026-07-12"""
    return agent_streams.get(task_id)


def reclaim_stream_buffer(task_id: str) -> None:
    """回收任务的流态缓冲(任务彻底结束后调用) — 小欧 2026-07-12"""
    agent_streams.pop(task_id, None)


async def check_cancelled(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("cancelled"))


async def check_paused(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("paused"))


async def check_was_paused(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("_was_paused"))


async def get_task_status(task_id: str) -> Optional[str]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("status") if task else None


async def is_task_running(task_id: str) -> bool:
    async with running_tasks_lock:
        return task_id in running_tasks


async def get_cancel_request_time(task_id: str) -> Optional[float]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("cancel_request_time") if task else None


async def get_pause_event(task_id: str) -> Optional[asyncio.Event]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("_pause_event") if task else None


async def get_task_field(task_id: str, field: str) -> Any:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get(field) if task else None


__all__ = [
    "running_tasks_lock", "running_tasks",
    "agent_streams", "StreamBuffer",
    "create_stream_buffer", "get_stream_buffer", "reclaim_stream_buffer",
    "check_cancelled", "check_paused", "check_was_paused",
    "get_task_status", "is_task_running",
    "get_cancel_request_time", "get_pause_event", "get_task_field",
]
