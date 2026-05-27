# -*- coding: utf-8 -*-
"""
LLM策略管理器 - 统一管理策略探测、升级和生命周期

消除策略探测逻辑分散在3处的问题：
1. llm_adapter.py 的 detect_strategy() - FC支持探测
2. react_agent_mixin.py 的策略重探测+升级逻辑
3. _call_llm() 内联的策略判断

Author: 小沈 - 2026-05-27
"""

import asyncio
from typing import Any, Optional

from app.utils.logger import logger


class LLMStrategyManager:
    """
    LLM调用策略管理器
    
    负责统一管理LLM调用策略（text/tools）的探测、升级和生命周期。
    集中处理首次探测、每步重探测、每10步升级等逻辑。
    """
    
    def __init__(self, llm_adapter: Any):
        """
        初始化策略管理器
        
        Args:
            llm_adapter: LLM适配器，用于探测策略
        """
        self._adapter = llm_adapter
        self._current_strategy: Optional[str] = None
        self._call_count: int = 0
    
    async def get_strategy(self) -> str:
        """
        获取当前策略
        
        规则：
        1. 首次调用：探测策略
        2. 每10步重探测：text策略尝试升级到tools
        
        Returns:
            策略字符串（"text" 或 "tools"）
        """
        self._call_count += 1
        
        # 首次探测
        if self._current_strategy is None:
            self._current_strategy = await self._probe_strategy()
            logger.info(f"[策略管理器] 首次探测策略: {self._current_strategy}")
            return self._current_strategy
        
        # 每10步重探测：text策略尝试升级到tools
        if self._call_count % 10 == 0:
            self._current_strategy = await self._auto_upgrade_strategy()
            if self._current_strategy:
                logger.info(f"[策略管理器] 第{self._call_count}步重探测策略: {self._current_strategy}")
        
        return self._current_strategy
    
    async def _probe_strategy(self) -> str:
        """
        探测策略（首次调用）
        
        Returns:
            探测到的策略字符串
        """
        if self._adapter is None:
            logger.warning("[策略管理器] adapter为None，降级到text策略")
            return "text"
        
        try:
            detected = await self._adapter.detect_strategy()
            logger.info(f"[策略管理器] 探测到策略: {detected}")
            return detected
        except Exception as e:
            logger.warning(f"[策略管理器] 探测策略失败: {e}，降级到text策略")
            return "text"
    
    async def _auto_upgrade_strategy(self) -> str:
        """
        自动升级策略（每10步）
        
        规则：
        - 当前是text策略时，尝试探测是否可以升级到tools
        - 如果探测结果不是text，则升级；否则保持text
        
        Returns:
            升级后的策略字符串
        """
        if self._current_strategy != "text":
            # 非text策略不升级
            return self._current_strategy
        
        if self._adapter is None:
            return "text"
        
        try:
            new_strategy = await self._adapter.detect_strategy()
            if new_strategy != "text":
                logger.info(f"[策略管理器] 策略升级: text → {new_strategy}")
                return new_strategy
            return "text"
        except Exception as e:
            logger.warning(f"[策略管理器] 策略探测失败: {e}")
            return "text"
    
    def reset(self):
        """重置策略状态"""
        self._current_strategy = None
        self._call_count = 0
        logger.info("[策略管理器] 策略状态已重置")
    
    @property
    def current_strategy(self) -> Optional[str]:
        """获取当前策略（不触发探测）"""
        return self._current_strategy
    
    @property
    def call_count(self) -> int:
        """获取调用次数"""
        return self._call_count


__all__ = ["LLMStrategyManager"]
