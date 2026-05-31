# -*- coding: utf-8 -*-
"""
close_instance — 从 factory.py 拷出

拷贝来源: factory.py 第102-110行
"""

from typing import Optional

from app.utils.logger import setup_logger
from app.services.llm_core import BaseAIService

logger = setup_logger("OmniAgentAst.AIServiceFactory")


async def close_instance(instance: Optional[BaseAIService]) -> None:
    """拷贝自 factory.py 第102-110行"""
    if instance is None:
        return
    try:
        await instance.close()
    except Exception as e:
        logger.warning(f"[AIServiceFactory] 关闭实例出错: {e}")
