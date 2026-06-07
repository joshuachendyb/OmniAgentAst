# -*- coding: utf-8 -*-
"""
LLM策略管理器 - 统一管理策略探测、升级和生命周期

重写记录 — 小欧 2026-06-07:
- EXC-31: L81 改为 (httpx/JSON/属性错误) 分类
- EXC-32: L109 改为 (httpx/JSON) 分类
- ARCH-4: 不变(已经是实例属性,_current_strategy 不再是全局单例)

Author: 小欧 - 2026-06-07
"""
import json
import httpx
from typing import Optional

from app.utils.logger import logger
from app.services.llm.capability_detector import CapabilityDetector


class LLMStrategyManager:
    """
    LLM调用策略管理器

    负责统一管理LLM调用策略(text/tools)的探测、升级和生命周期。
    集中处理首次探测、每步重探测、每10步升级等逻辑。
    """

    def __init__(self, capability_detector: CapabilityDetector):
        """
        初始化策略管理器

        Args:
            capability_detector: 能力探测器,用于探测策略
        """
        self._detector = capability_detector
        # ARCH-4: 已经是实例属性(非全局单例)
        self._current_strategy: Optional[str] = None
        self._call_count: int = 0

    async def get_strategy(self) -> str:
        """
        获取当前策略

        规则:
        1. 首次调用:探测策略
        2. 每10步重探测:text策略尝试升级到tools

        Returns:
            策略字符串("text" 或 "tools")
        """
        self._call_count += 1

        # 首次探测
        if self._current_strategy is None:
            self._current_strategy = await self._probe_strategy()
            logger.info(f"[策略管理器] 首次探测策略: {self._current_strategy}")
            return self._current_strategy

        # 每10步重探测:text策略尝试升级到tools
        if self._call_count % 10 == 0:
            self._current_strategy = await self._auto_upgrade_strategy()
            if self._current_strategy:
                logger.info(f"[策略管理器] 第{self._call_count}步重探测策略: {self._current_strategy}")

        return self._current_strategy

    async def _probe_strategy(self) -> str:
        """
        探测策略(首次调用)

        Returns:
            探测到的策略字符串
        """
        if self._detector is None:
            logger.warning("[策略管理器] detector为None,降级到text策略")
            return "text"

        # EXC-31 修复: 异常分类 (httpx/JSON/属性错误)
        try:
            detected = await self._detector.detect_strategy()
            logger.info(f"[策略管理器] 探测到策略: {detected}")
            return detected
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.warning(f"[策略管理器] 探测策略失败(网络/JSON): {e}", exc_info=True)
            return "text"
        except (AttributeError, TypeError) as e:
            logger.warning(f"[策略管理器] 探测策略失败(属性/类型): {e}", exc_info=True)
            return "text"
        except Exception as e:
            logger.warning(f"[策略管理器] 探测策略失败(未分类): {e}", exc_info=True)
            return "text"

    async def _auto_upgrade_strategy(self) -> str:
        """
        自动升级策略(每10步)

        规则:
        - 当前是text策略时,尝试探测是否可以升级到tools
        - 如果探测结果不是text,则升级;否则保持text

        Returns:
            升级后的策略字符串
        """
        if self._current_strategy != "text":
            return self._current_strategy

        if self._detector is None:
            return "text"

        # EXC-32 修复: 异常分类 (httpx/JSON/属性)
        try:
            self._detector.reset_cache()
            new_strategy = await self._detector.detect_strategy()
            if new_strategy != "text":
                logger.info(f"[策略管理器] 策略升级: text → {new_strategy}")
                return new_strategy
            return "text"
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.warning(f"[策略管理器] 策略探测失败(网络/JSON): {e}", exc_info=True)
            return "text"
        except (AttributeError, TypeError) as e:
            logger.warning(f"[策略管理器] 策略探测失败(属性/类型): {e}", exc_info=True)
            return "text"
        except Exception as e:
            logger.warning(f"[策略管理器] 策略探测失败(未分类): {e}", exc_info=True)
            return "text"

    def reset(self):
        """重置策略状态"""
        self._current_strategy = None
        self._call_count = 0
        logger.info("[策略管理器] 策略状态已重置")

    @property
    def current_strategy(self) -> Optional[str]:
        """获取当前策略(不触发探测)"""
        return self._current_strategy

    @property
    def call_count(self) -> int:
        """获取调用次数"""
        return self._call_count


__all__ = ["LLMStrategyManager"]
