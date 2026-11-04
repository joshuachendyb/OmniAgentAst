# -*- coding: utf-8 -*-
"""
background_tasks — fire-and-forget 后台协程的统一生成口 — 小欧 2026-11-03
病根: 裸 asyncio.create_task 只被事件循环弱引用(CPython 文档明示), 挂起中的任务
     可被 GC 中途销毁, 销毁不走 except → 后台落盘/统计静默丢失。
纪律: 统一走 spawn_bg() 由模块级集合持强引用, done 自动 discard 防集合泄漏。
"""
# 编辑历史:
# 2026-11-03 - 小欧 - 新建: main.py 四处"存引用防 GC"注释立规与 agent_runner._background_tasks
#   (set + done 回调 discard, 2026-07-13 会审产物)同款模式收口为公用件; 首接入 monitoring/middleware.py

import asyncio
from typing import Any, Coroutine

# 在跑的后台任务强引用集合(防 GC 中途销毁); done 由回调自动摘除, 不泄漏
_BG_TASKS: set = set()


def _on_done(task: asyncio.Task) -> None:
    _BG_TASKS.discard(task)
    # 未被 cancel 的任务咬取消化一次 exception(): 防全局 "Task exception was never
    # retrieved" 日志噪音(agent_runner 同款); 消费方协议为任务内自捕获落日志
    if not task.cancelled():
        task.exception()


def spawn_bg(coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
    """生成引用受保护的后台任务 — 代替裸 asyncio.create_task — 小欧 2026-11-03

    语义与 create_task 相同(立即调度, 立即返回), 唯一差异: 本模块集合持强引用,
    done 回调摘除; 挂起中的任务不再可能被 GC 中途销毁。
    """
    task = asyncio.create_task(coro)
    _BG_TASKS.add(task)
    task.add_done_callback(_on_done)
    return task
