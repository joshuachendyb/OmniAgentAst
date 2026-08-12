# -*- coding: utf-8 -*-
"""
test_agent_runner — 验证 SSE 解耦核心（agent 执行与传输分离）

北京老陈 2026-07-12: 验证 StreamBuffer 事件累积 + stream_reader 按 seq 消费 + 缓冲回收。 — 小欧 2026-07-12

不依赖真实 LLM：直接用 StreamBuffer 模拟生产者写事件，stream_reader 模拟消费者读。
"""
import asyncio

from app.services.chat.stream import stream_reader
from app.services.task.task_state import (
    agent_streams,
    create_stream_buffer,
    get_stream_buffer,
    reclaim_stream_buffer,
)


async def _run_producer(buf, count: int):
    """模拟生产者：写入 count 个事件后置 done。"""
    for i in range(count):
        d = {"type": "chunk", "content": f"step-{i}", "step": i + 1}
        d2 = dict(d)
        d2["seq"] = len(buf.event_log)
        buf.event_log.append(d2)
        async with buf.cond:
            buf.cond.notify_all()
    buf.done.set()
    async with buf.cond:
        buf.cond.notify_all()


def test_stream_buffer_append_and_reconnect_read():
    task_id = "test-buf-reconnect-1"
    buf = create_stream_buffer(task_id)
    assert get_stream_buffer(task_id) is buf
    assert task_id in agent_streams

    received = []
    received1 = []
    received2 = []

    async def consumer():
        # 先读前 2 个事件（模拟首次连接中断）
        seq = 0
        async for chunk in stream_reader(buf, task_id, after_seq=seq):
            received.append(chunk)
            received1.append(chunk)
            seq += 1
            if seq >= 2:
                break
        # 中断后重连：从 after_seq=2 续传剩余事件
        async for chunk in stream_reader(buf, task_id, after_seq=seq):
            received.append(chunk)
            received2.append(chunk)

    async def main():
        prod = asyncio.create_task(_run_producer(buf, 3))
        await consumer()
        await prod

    asyncio.run(main())

    # 应收到 3 个事件（首次 2 + 重连续传 1），且重连不重复
    assert len(received1) == 2, f"r1={len(received1)}"
    assert len(received2) == 1, f"r2={len(received2)}"
    assert len(received) == 3, f"total={len(received)}"

    # 回收
    reclaim_stream_buffer(task_id)
    assert task_id not in agent_streams


def test_stream_reader_terminates_on_done():
    task_id = "test-buf-done-1"
    buf = create_stream_buffer(task_id)

    received = []

    async def main():
        asyncio.create_task(_run_producer(buf, 2))
        async for chunk in stream_reader(buf, task_id, after_seq=0):
            received.append(chunk)

    asyncio.run(main())
    assert len(received) == 2
    reclaim_stream_buffer(task_id)
