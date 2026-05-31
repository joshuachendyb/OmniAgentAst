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
    """拷贝自 factory.py 第112-125行"""
    if instance is None:
        return
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(instance.close())
        else:
            loop.run_until_complete(instance.close())
    except Exception as e:
        logger.warning(f"[AIServiceFactory] 关闭旧实例出错: {e}")
