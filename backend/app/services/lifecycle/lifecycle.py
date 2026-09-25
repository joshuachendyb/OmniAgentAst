# -*- coding: utf-8 -*-
"""
lifecycle — 服务生命周期管理

合并: close_instance + close_instance_sync + reset
小沈 2026-06-17
小欧 2026-08-14 llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
小欧 2026-09-25 [70] 新增 shutdown(): 停机收口 = reset() 换代归还 + 逐个退休代 scope.drain(超时放行)
"""

import asyncio
import time  # [70] shutdown 总预算 deadline 计算 — 小欧-2026-09-25
from typing import Optional

from app.logger import setup_logger
from app.llm import BaseAIService

logger = setup_logger(__name__)


async def close_instance(instance: Optional[BaseAIService]) -> None:
    """异步关闭实例 — 小沈 2026-06-08"""
    if instance is None:
        return
    try:
        await instance.close()
    except Exception as e:
        logger.warning(f"[AIServiceFactory] 关闭实例出错: {e}")


def close_instance_sync(instance: Optional[BaseAIService]) -> None:
    """同步关闭实例 — 小沈 2026-06-08
    【修复P0-1 2026-06-09 小沈】get_event_loop→get_running_loop,防止Python 3.10+ DeprecationWarning
    """
    if instance is None:
        return
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            asyncio.ensure_future(instance.close())
        elif loop is not None:
            loop.run_until_complete(instance.close())
        else:
            asyncio.run(instance.close())
    except Exception as e:
        logger.warning(f"[AIServiceFactory] 关闭旧实例出错: {e}")


def reset():
    """重置工厂状态 — 小沈 2026-06-08
    P1-07/P2-07修复: 使用公开reset_instance替代直接操作私有变量
    """
    from app.services.lifecycle.service import reset_instance
    old = reset_instance()
    close_instance_sync(old)
    logger.info("[AIServiceFactory] 工厂状态已重置")


async def shutdown(timeout: float = 30.0) -> None:
    """[70] 停机收口(小欧 2026-09-25): ①reset() 换代归还当前代 owner(阻断新任务混入)+关闭旧实例;
    ②逐个等待退休代池 lease 归零关闭(0.1s 轮询)。v1.4 审核修订: timeout 为**全停机总预算**
    (原按代逐个计, 最坏 代数×timeout 无界上界), 各代按剩余预算 drain, 耗尽即放行不阻塞进程退出。
    main.shutdown_event 调用, 取代原裸 reset()(原调用只清工厂不等池关闭)。"""
    from app.services.lifecycle.service import get_retired_scopes
    reset()
    deadline = time.monotonic() + timeout
    for scope in get_retired_scopes():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            logger.warning(f"[AIServiceFactory] 停机收口预算耗尽({timeout}s), 剩余退休代未等完(放行)")
            break
        await scope.drain(timeout=remaining)
    logger.info("[AIServiceFactory] 停机收口完成(共享池 lease 已归零或超时放行)")
