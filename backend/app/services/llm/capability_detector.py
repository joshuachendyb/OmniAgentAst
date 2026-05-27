# -*- coding: utf-8 -*-
"""
LLM能力探测统一基类

消除LLMAdapter.detect_strategy()和BaseAIService._detect_reasoning_support()
两套"发请求→判断→缓存"模式的重复。

Author: 小沈 - 2026-05-27
"""

import httpx
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger
from app.constants import DEFAULT_PROBE_TIMEOUT


class CapabilityDetector:
    """
    LLM能力探测统一基类

    封装统一探测流程：发请求→判断→缓存→返回。
    detect_strategy（FC能力）和detect_reasoning_support（reasoning_content能力）
    各为子方法，共享缓存和探测请求逻辑。
    """

    def __init__(self, api_base: str, api_key: str, model: str):
        self._api_base = api_base
        self._api_key = api_key
        self._model = model
        self._cache: Dict[str, Any] = {}

    async def _probe_api(self, messages: list = None) -> Optional[Dict]:
        """
        发送探测请求

        Args:
            messages: 可选的自定义消息列表

        Returns:
            API响应JSON，失败返回None
        """
        if messages is None:
            messages = [{"role": "user", "content": "1+1=?"}]
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_PROBE_TIMEOUT) as client:
                response = await client.post(
                    f"{self._api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self._model, "messages": messages, "stream": False},
                )
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"[CapabilityDetector] 探测请求返回{response.status_code}")
                return None
        except Exception as e:
            logger.warning(f"[CapabilityDetector] 探测请求失败: {e}")
            return None

    async def detect_strategy(self, probe_fn: Callable = None) -> str:
        """
        探测LLM调用策略（text/tools）

        Args:
            probe_fn: 自定义探测函数，接收response_json返回策略字符串

        Returns:
            "text" 或 "tools"
        """
        cache_key = "strategy"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if probe_fn is not None:
            result = await probe_fn()
        else:
            result = "text"

        self._cache[cache_key] = result
        logger.info(f"[CapabilityDetector] strategy={result}, model={self._model}")
        return result

    async def detect_reasoning_support(self) -> bool:
        """
        探测LLM是否支持reasoning_content字段

        Returns:
            True如果支持
        """
        cache_key = "reasoning"
        if cache_key in self._cache:
            return self._cache[cache_key]

        response_json = await self._probe_api()
        if response_json is not None:
            message = response_json.get("choices", [{}])[0].get("message", {})
            result = "reasoning_content" in message
        else:
            result = False

        self._cache[cache_key] = result
        logger.info(f"[CapabilityDetector] reasoning_support={result}, model={self._model}")
        return result

    def reset_cache(self):
        """重置缓存"""
        self._cache.clear()

    @property
    def cached_strategy(self) -> Optional[str]:
        """获取缓存的策略（不触发探测）"""
        return self._cache.get("strategy")

    @property
    def cached_reasoning_support(self) -> Optional[bool]:
        """获取缓存的reasoning支持状态"""
        return self._cache.get("reasoning")


__all__ = ["CapabilityDetector"]
