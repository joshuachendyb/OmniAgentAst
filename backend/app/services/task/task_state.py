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
