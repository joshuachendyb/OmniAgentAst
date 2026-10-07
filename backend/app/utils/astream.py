# -*- coding: utf-8 -*-
"""异步流收尾工具(全局层)

编辑历史: 2026-10-08 小欧 - 新建: 修复 LLM 流式调用每轮泄漏一个异步生成器
   (llm_call/base_service 的 async for 在 break/return/异常时不关闭上游) — 小欧-2026-10-08
"""
from typing import Any

__all__ = ["aclose_stream"]


async def aclose_stream(stream: Any) -> None:
    """关闭上游异步流(有 aclose 能力才关), 供 async for 提前退出后在 finally 调用

    背景: Python 的 `async for` 在 break / return / 抛异常时**不**关闭异步生成器,
    只有自然耗尽(StopAsyncIteration)或显式 aclose 才会。LLM 流式调用链有三层异步
    生成器(LLMClient → BaseAIService → llm_call), 上层提前退出即下层悬挂:
    httpx 在飞响应(`BaseAIService._current_response`)不归还连接池, 长跑任务下
    连接/FD 堆积; pytest 里 GC 时报 "coroutine method 'aclose' of ... was never awaited"。

    为何不用 contextlib.aclosing: 它无条件 `await stream.aclose()`, 而本仓测试与
    部分第三方流是"只实现 __aiter__/__anext__"的异步迭代器(无 aclose), 直接用会
    AttributeError 打断调用方。故按能力探测: 有则关、无则静默跳过。

    @author 小欧
    @date 2026-10-08
    """
    aclose = getattr(stream, "aclose", None)
    if aclose is None:
        return
    await aclose()