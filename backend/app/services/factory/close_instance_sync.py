# -*- coding: utf-8 -*-
"""
close_instance_sync — 从 factory.py 拷出

拷贝来源: factory.py 第112-125行
"""

from typing import Optional

from app.utils.logger import setup_logger
from app.services.llm_core import BaseAIService

logger = setup_logger("OmniAgentAst.AIServiceFactory")


def close_instance_sync(instance: Optional[BaseAIService]) -> None:
    """拷贝自 factory.py 第112-125行
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
