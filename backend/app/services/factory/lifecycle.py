# -*- coding: utf-8 -*-
"""
lifecycle — 服务生命周期管理

合并: close_instance + close_instance_sync + reset
小沈 2026-06-17
"""

from typing import Optional

from app.utils.logger import setup_logger
from app.services.llm import BaseAIService

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
        import asyncio
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
    from app.services.factory.service import reset_instance
    old = reset_instance()
    close_instance_sync(old)
    print("[AIServiceFactory] 工厂状态已重置")